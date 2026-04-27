"""
图片工作室 API 路由

支持的模型：
- wan2.5-i2i-preview: 万相图生图（风格迁移）
- qwen-image-edit-plus/max: 通义千问图像编辑（单图编辑/多图融合）
- qwen-image-2.0-pro/2.0: 千问图像2.0（文生图+图像编辑融合）

架构说明：
- /generate 端点通过 asyncio.create_task() 在后台执行生成，立即返回 generating 状态
- 前端通过轮询 GET /{task_id} 获取生成进度和结果
- 底层 API 差异由各 generate_with_* 函数内部处理
"""

import asyncio
import copy
import logging
import math
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Any, Tuple, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.studio import StudioTask, StudioTaskImage, ReferenceItem
from app.models.gallery import GalleryImage
from app.services.storage import storage_service, set_current_user, get_current_user_id
from app.services.dashscope.image_to_image import ImageToImageService
from app.services.oss import oss_service
from app.services.remote_media_validation import inspect_remote_image
from app.config import get_config, get_provider_api_key, get_provider_key_profile, set_user_config_dir, get_user_config_dir

logger = logging.getLogger(__name__)

router = APIRouter()
WAN27_IMAGE_INSPECT_RETRY_DELAYS = (0.5, 1.5)
STUDIO_OSS_AUTO_RETRY_DELAYS = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=3),
    timedelta(hours=6),
)
STUDIO_LOCAL_FALLBACK_CLEANUP_TTL = timedelta(days=7)
_studio_retrying_task_ids: set[str] = set()
_studio_retrying_lock = threading.Lock()
_studio_generating_task_ids: set[str] = set()
_studio_generating_lock = threading.Lock()


def _try_acquire_generation_slot(task_id: str) -> bool:
    with _studio_generating_lock:
        if task_id in _studio_generating_task_ids:
            return False
        _studio_generating_task_ids.add(task_id)
        return True


def _release_generation_slot(task_id: str) -> None:
    with _studio_generating_lock:
        _studio_generating_task_ids.discard(task_id)


def _summarize_media_url(url: str) -> str:
    if not url:
        return "空 URL"
    if url.startswith("data:"):
        header = url.split(",", 1)[0]
        return f"{header},..."
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url[:120]
    path_parts = [part for part in parsed.path.split("/") if part]
    short_path = "/".join(path_parts[-3:])
    return f"{parsed.scheme}://{parsed.netloc}/{short_path}" if short_path else f"{parsed.scheme}://{parsed.netloc}"


def _clear_image_storage_retry_state(image: StudioTaskImage) -> None:
    image.storage_warning = None
    image.retry_count = 0
    image.last_retry_error = None
    image.last_retry_at = None
    image.next_retry_at = None
    image.fallback_created_at = None


def _mark_image_as_local_fallback(
    image: StudioTaskImage,
    warning: str,
    error: Optional[str],
    now: datetime,
) -> None:
    image.storage_source = "local_fallback"
    image.storage_warning = warning
    image.last_retry_error = error
    image.last_retry_at = None
    image.retry_count = 0
    image.next_retry_at = now + STUDIO_OSS_AUTO_RETRY_DELAYS[0]
    image.fallback_created_at = now


def _update_image_retry_failure_state(
    image: StudioTaskImage,
    warning: str,
    error: Optional[str],
    now: datetime,
    retryable: bool,
) -> None:
    image.storage_source = "local_fallback"
    image.storage_warning = warning
    image.last_retry_error = error
    image.last_retry_at = now
    image.retry_count = max(0, int(image.retry_count or 0)) + 1
    image.fallback_created_at = image.fallback_created_at or now

    if retryable and image.retry_count < len(STUDIO_OSS_AUTO_RETRY_DELAYS):
        image.next_retry_at = now + STUDIO_OSS_AUTO_RETRY_DELAYS[image.retry_count]
    else:
        image.next_retry_at = None


def _mark_image_as_local_expired(
    image: StudioTaskImage,
    warning: str,
    error: Optional[str],
    now: datetime,
) -> None:
    image.url = None
    image.storage_source = "local_expired"
    image.storage_warning = warning
    image.last_retry_error = error
    image.last_retry_at = now
    image.next_retry_at = None


def _build_task_storage_warnings(task: StudioTask) -> List[str]:
    warnings: List[str] = []
    for image in task.images:
        if image.storage_source in {"local_fallback", "local_expired"} and image.storage_warning:
            warnings.append(f"第 {image.group_index + 1} 张图片：{image.storage_warning}")
    return list(dict.fromkeys(warnings))


def _count_retriable_local_fallback_images(task: StudioTask) -> int:
    return sum(
        1
        for image in task.images
        if image.storage_source == "local_fallback" and bool(image.url)
    )


def _is_local_fallback_retry_due(image: StudioTaskImage, now: datetime) -> bool:
    if image.storage_source != "local_fallback" or not image.url:
        return False
    if image.next_retry_at is None:
        return False
    return image.next_retry_at <= now


def _expire_local_fallback_images(task: StudioTask, now: Optional[datetime] = None) -> bool:
    current_time = now or datetime.now()
    changed = False
    for image in task.images:
        if image.storage_source != "local_fallback":
            continue
        created_at = image.fallback_created_at
        if created_at is None:
            continue
        if created_at + STUDIO_LOCAL_FALLBACK_CLEANUP_TTL > current_time:
            continue
        local_url = image.url or ""
        if local_url:
            oss_service.cleanup_local_asset_url(local_url)
        _mark_image_as_local_expired(
            image,
            "本地回退文件已超过 7 天，已自动清理；如仍需使用，请重新生成。",
            image.last_retry_error or "本地回退文件已过期清理",
            current_time,
        )
        changed = True
    return changed


def _cleanup_task_local_assets(task: StudioTask) -> None:
    for image in task.images:
        if image.storage_source == "local_fallback" and image.url:
            oss_service.cleanup_local_asset_url(image.url)


async def _retry_task_local_fallback_images(
    task: StudioTask,
    *,
    due_only: bool,
    reason: str,
) -> Dict[str, int]:
    current_time = datetime.now()
    summary = {
        "retried_image_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "paused_count": 0,
        "expired_count": 0,
    }

    changed = _expire_local_fallback_images(task, current_time)

    for image in task.images:
        if image.storage_source != "local_fallback":
            continue
        if not image.url:
            continue
        if due_only and not _is_local_fallback_retry_due(image, current_time):
            continue

        summary["retried_image_count"] += 1
        result = await oss_service.retry_local_fallback_image_to_oss_async(
            image.url,
            task.project_id,
        )

        if result.storage_source == "oss":
            image.url = result.url
            image.storage_source = "oss"
            _clear_image_storage_retry_state(image)
            summary["success_count"] += 1
            changed = True
            logger.info(
                "[OSS][studio] local fallback upload recovered task_id=%s project_id=%s image_id=%s reason=%s",
                task.id,
                task.project_id,
                image.id,
                reason,
            )
            continue

        if result.storage_source == "local_expired":
            _mark_image_as_local_expired(
                image,
                result.warning or "本地回退文件不存在，无法继续上传到 OSS。",
                result.error,
                current_time,
            )
            summary["failed_count"] += 1
            summary["expired_count"] += 1
            summary["paused_count"] += 1
            changed = True
            continue

        _update_image_retry_failure_state(
            image,
            result.warning or "重新上传到 OSS 失败，已保留本地回退图片。",
            result.error,
            current_time,
            retryable=result.retryable,
        )
        summary["failed_count"] += 1
        if image.next_retry_at is None:
            summary["paused_count"] += 1
        changed = True

    task.warnings = _build_task_storage_warnings(task)
    if changed:
        storage_service.save_studio_task(task)
    return summary


async def _background_retry_task_local_fallbacks(
    task_id: str,
    user_id: Optional[str],
    user_config_dir: Optional[str],
    *,
    due_only: bool,
    reason: str,
) -> None:
    with _studio_retrying_lock:
        if task_id in _studio_retrying_task_ids:
            return
        _studio_retrying_task_ids.add(task_id)

    try:
        set_current_user(user_id)
        set_user_config_dir(user_config_dir)
        task = storage_service.get_studio_task(task_id)
        if not task:
            return
        await _retry_task_local_fallback_images(task, due_only=due_only, reason=reason)
    except Exception:
        logger.exception("[OSS][studio] 背景重传本地回退图片失败 task_id=%s reason=%s", task_id, reason)
    finally:
        with _studio_retrying_lock:
            _studio_retrying_task_ids.discard(task_id)


def _schedule_due_local_fallback_retries(
    tasks: List[StudioTask],
    user_id: Optional[str],
    user_config_dir: Optional[str],
) -> None:
    current_time = datetime.now()
    for task in tasks:
        if not any(_is_local_fallback_retry_due(image, current_time) for image in task.images):
            continue
        with _studio_retrying_lock:
            if task.id in _studio_retrying_task_ids:
                continue
        asyncio.create_task(
            _background_retry_task_local_fallbacks(
                task.id,
                user_id,
                user_config_dir,
                due_only=True,
                reason="auto",
            )
        )


async def _ensure_generated_images_persisted(
    images: List[StudioTaskImage],
    project_id: str,
    model_id: str = "",
    request_ids: Optional[List[str]] = None,
    task_ids: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """在写入任务前统一将生成结果转存到当前 OSS。"""
    if not images:
        return {"errors": [], "warnings": []}

    migrated_url_cache: Dict[str, Dict[str, Optional[str]]] = {}
    failed_url_cache: Dict[str, str] = {}
    errors: List[str] = []
    current_time = datetime.now()

    for image in images:
        original_url = image.url
        if not original_url:
            continue
        if not oss_service.should_persist_generated_url(original_url):
            image.storage_source = "oss" if oss_service.is_current_oss_url(original_url) else "remote"
            _clear_image_storage_retry_state(image)
            continue
        if original_url in migrated_url_cache:
            cached_result = migrated_url_cache[original_url]
            image.url = cached_result["url"]
            image.storage_source = cached_result["storage_source"] or "remote"
            image.storage_warning = cached_result["warning"]
            if image.storage_source == "local_fallback":
                _mark_image_as_local_fallback(
                    image,
                    cached_result["warning"] or "图片结果转存 OSS 连续失败，已暂时回退为服务器本地文件。",
                    None,
                    current_time,
                )
            else:
                _clear_image_storage_retry_state(image)
            continue
        if original_url in failed_url_cache:
            image.url = None
            image.storage_source = "remote"
            _clear_image_storage_retry_state(image)
            continue

        try:
            persisted_result = await oss_service.persist_generated_image_with_fallback_async(
                original_url,
                project_id,
            )
            migrated_url_cache[original_url] = {
                "url": persisted_result.url,
                "storage_source": persisted_result.storage_source,
                "warning": persisted_result.warning,
            }
            image.url = persisted_result.url
            image.storage_source = persisted_result.storage_source
            image.storage_warning = persisted_result.warning
            if persisted_result.warning:
                _mark_image_as_local_fallback(
                    image,
                    persisted_result.warning,
                    persisted_result.error,
                    current_time,
                )
                parsed = urlparse(original_url)
                logger.warning(
                    "[OSS][studio] persist fallback model_id=%s project_id=%s request_ids=%s task_ids=%s original_host=%s fallback_url=%s reason=%s",
                    model_id or "unknown",
                    project_id or "_global",
                    ",".join(request_ids or []) or "-",
                    ",".join(task_ids or []) or "-",
                    parsed.netloc or "unknown",
                    persisted_result.url,
                    persisted_result.error or persisted_result.warning,
                )
            else:
                _clear_image_storage_retry_state(image)
        except Exception as exc:
            failed_url_cache[original_url] = str(exc)
            image.url = None
            image.storage_source = "remote"
            _clear_image_storage_retry_state(image)
            parsed = urlparse(original_url)
            logger.warning(
                "[OSS][studio] persist failed model_id=%s project_id=%s request_ids=%s task_ids=%s original_host=%s oss_enabled=%s reason=%s",
                model_id or "unknown",
                project_id or "_global",
                ",".join(request_ids or []) or "-",
                ",".join(task_ids or []) or "-",
                parsed.netloc or "unknown",
                oss_service.is_enabled(),
                str(exc),
            )
            errors.append(str(exc))

    warning_messages = []
    for image in images:
        if image.storage_source == "local_fallback":
            warning_messages.append(f"第 {image.group_index + 1} 张图片 OSS 转存连续失败，已暂时回退为服务器本地文件。")
    return {"errors": errors, "warnings": list(dict.fromkeys(warning_messages))}


class ReferenceItemInput(BaseModel):
    """参考素材输入"""
    type: str  # character, scene, prop, gallery, style
    id: str


class ColorPaletteItemInput(BaseModel):
    """颜色主题输入"""
    hex: str
    ratio: str


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    project_id: str
    name: str
    description: str = ""
    model: str = "wan2.5-i2i-preview"
    prompt: str = ""
    negative_prompt: str = ""
    task_kind: Optional[str] = None
    n: int = 1  # 每次请求生成的图片数量
    group_count: int = 3  # 并发请求数
    size: Optional[str] = None
    prompt_extend: Optional[bool] = True
    watermark: Optional[bool] = False
    seed: Optional[int] = None
    enable_interleave: Optional[bool] = False
    max_images: Optional[int] = 5
    enable_sequential: Optional[bool] = False
    thinking_mode: Optional[bool] = None
    bbox_list: Optional[List[List[List[int]]]] = None
    color_palette: Optional[List[ColorPaletteItemInput]] = None
    size_mode: Optional[str] = None
    size_preset: Optional[str] = None
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None
    output_format: Optional[str] = None
    web_search: Optional[bool] = False
    references: List[ReferenceItemInput] = []


class TaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    task_kind: Optional[str] = None
    n: Optional[int] = None  # 每次请求生成的图片数量
    group_count: Optional[int] = None  # 并发请求数
    references: Optional[List[ReferenceItemInput]] = None
    # 高级生成参数
    size: Optional[str] = None  # 输出尺寸
    prompt_extend: Optional[bool] = None  # 智能改写
    watermark: Optional[bool] = None  # 水印
    seed: Optional[int] = None  # 随机种子
    # wan2.6-image 专用参数
    enable_interleave: Optional[bool] = None  # 图文混合模式
    max_images: Optional[int] = None  # 图文混合模式下最大生成图数
    # wan2.7 专用参数
    enable_sequential: Optional[bool] = None
    thinking_mode: Optional[bool] = None
    bbox_list: Optional[List[List[List[int]]]] = None
    color_palette: Optional[List[ColorPaletteItemInput]] = None
    size_mode: Optional[str] = None
    size_preset: Optional[str] = None
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None
    output_format: Optional[str] = None
    web_search: Optional[bool] = None


class TaskGenerateRequest(BaseModel):
    """生成图片请求"""
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    n: Optional[int] = None  # 每次请求生成的图片数量
    group_count: Optional[int] = None  # 并发请求数（总图片数 = n * group_count）
    task_kind: Optional[str] = None
    # 通用参数
    size: Optional[str] = None  # 输出尺寸
    prompt_extend: Optional[bool] = True  # 智能改写
    watermark: Optional[bool] = False  # 水印
    seed: Optional[int] = None  # 随机种子
    # wan2.6-image 专用参数
    enable_interleave: Optional[bool] = False  # 是否启用图文混合模式
    max_images: Optional[int] = 5  # 图文混合模式下最大生成图片数（1-5）
    # wan2.7 专用参数
    enable_sequential: Optional[bool] = False
    thinking_mode: Optional[bool] = None
    bbox_list: Optional[List[List[List[int]]]] = None
    color_palette: Optional[List[ColorPaletteItemInput]] = None
    size_mode: Optional[str] = None
    size_preset: Optional[str] = None
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None
    output_format: Optional[str] = None
    web_search: Optional[bool] = False


class PreviewPayloadRequest(TaskGenerateRequest):
    """开发者模式 payload 预览请求"""
    project_id: str
    model: str
    references: List[ReferenceItemInput] = []


class SaveToGalleryRequest(BaseModel):
    """保存到图库请求"""
    image_ids: List[str]  # 要保存的图片ID列表


def get_reference_url(ref_type: str, ref_id: str) -> tuple[str, str]:
    """获取参考素材的URL和名称"""
    if ref_type == "character":
        character = storage_service.get_character(ref_id)
        if character and character.image_groups:
            selected_idx = character.selected_group_index
            if selected_idx < len(character.image_groups):
                group = character.image_groups[selected_idx]
                return group.front_url or "", character.name
    elif ref_type == "scene":
        scene = storage_service.get_scene(ref_id)
        if scene and scene.image_groups:
            selected_idx = scene.selected_group_index
            if selected_idx < len(scene.image_groups):
                return scene.image_groups[selected_idx].url or "", scene.name
    elif ref_type == "prop":
        prop = storage_service.get_prop(ref_id)
        if prop and prop.image_groups:
            selected_idx = prop.selected_group_index
            if selected_idx < len(prop.image_groups):
                return prop.image_groups[selected_idx].url or "", prop.name
    elif ref_type == "gallery":
        image = storage_service.get_gallery_image(ref_id)
        if image:
            return image.url, image.name
    elif ref_type == "style":
        style = storage_service.get_style(ref_id)
        if style:
            if style.style_type == "image" and style.image_groups:
                selected_idx = style.selected_group_index
                if selected_idx < len(style.image_groups):
                    group = style.image_groups[selected_idx]
                    return group.url or "", style.name
            return "", style.name
    return "", ""


WAN27_MODELS = {"wan2.7-image-pro", "wan2.7-image"}
SEEDREAM_MODELS = {"doubao-seedream-5.0-lite", "doubao-seedream-4.5"}
WAN_IMAGE_MODELS = {"wan2.6-t2i", "wan2.6-image", "wan2.5-t2i-preview", "wan2.5-i2i-preview", *WAN27_MODELS}
QWEN_IMAGE_MODELS = {
    "qwen-image-max",
    "qwen-image-plus",
    "qwen-image-edit-plus",
    "qwen-image-edit-max",
    "qwen-image-2.0-pro",
    "qwen-image-2.0",
}
VOLCENGINE_IMAGE_MODELS = {*SEEDREAM_MODELS}

IMAGE_TEMPLATE_RATIOS: List[Tuple[str, str, float]] = [
    ("1:1", "方图", 1.0),
    ("4:3", "横版", 4 / 3),
    ("3:4", "竖版", 3 / 4),
    ("16:9", "横版", 16 / 9),
    ("9:16", "竖版", 9 / 16),
    ("21:9", "横版", 21 / 9),
]

WAN25_T2I_MIN_PIXELS = 768 * 768
WAN25_T2I_MAX_PIXELS = 1440 * 1440
WAN25_T2I_MIN_RATIO = 0.25
WAN25_T2I_MAX_RATIO = 4.0

WAN25_I2I_MIN_PIXELS = 768 * 768
WAN25_I2I_MAX_PIXELS = 1280 * 1280
WAN25_I2I_MIN_RATIO = 0.25
WAN25_I2I_MAX_RATIO = 4.0

WAN27_ALLOWED_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "BMP", "WEBP"}
WAN27_MIN_TOTAL_PIXELS = 768 * 768
WAN27_PRO_MAX_TOTAL_PIXELS = 4096 * 4096
WAN27_STANDARD_MAX_TOTAL_PIXELS = 2048 * 2048
WAN27_MIN_IMAGE_DIM = 240
WAN27_MAX_IMAGE_DIM = 8000
WAN27_MAX_IMAGE_BYTES = 20 * 1024 * 1024
WAN27_MIN_RATIO = 0.125
WAN27_MAX_RATIO = 8.0
WAN27_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
WAN27_RATIO_PATTERN = re.compile(r"^(?:100|[0-9]{1,2})\.[0-9]{2}%$")

IMAGE_TASK_KIND_SUPPORT: Dict[str, List[str]] = {
    "wan2.7-image-pro": ["text_to_image", "image_edit", "interactive_edit", "sequential_generation"],
    "wan2.7-image": ["text_to_image", "image_edit", "interactive_edit", "sequential_generation"],
    "wan2.6-image": ["text_to_image", "image_edit"],
    "wan2.6-t2i": ["text_to_image"],
    "wan2.5-t2i-preview": ["text_to_image"],
    "wan2.5-i2i-preview": ["image_edit"],
    "qwen-image-max": ["text_to_image"],
    "qwen-image-plus": ["text_to_image"],
    "qwen-image-edit-plus": ["image_edit"],
    "qwen-image-edit-max": ["image_edit"],
    "qwen-image-2.0-pro": ["text_to_image", "image_edit"],
    "qwen-image-2.0": ["text_to_image", "image_edit"],
    "doubao-seedream-5.0-lite": ["text_to_image", "image_edit", "sequential_generation"],
    "doubao-seedream-4.5": ["text_to_image", "image_edit", "sequential_generation"],
}


def _get_image_size_ui_mode(model_id: str) -> str:
    if model_id in {"wan2.7-image-pro", "wan2.7-image", "wan2.5-t2i-preview", "wan2.5-i2i-preview"}:
        return "preset_plus_custom_with_templates"
    return "preset_only"


def _get_image_model_provider(model_name: str) -> str:
    if model_name in VOLCENGINE_IMAGE_MODELS:
        return "volcengine"
    return "wan"


@dataclass
class NormalizedStudioRequest:
    project_id: str
    task_kind: str
    provider: str
    model_id: str
    prompt: str
    negative_prompt: str
    input_assets: Dict[str, Any]
    normalized_params: Dict[str, Any]


def _serialize_color_palette(items: Optional[List[Any]]) -> List[Dict[str, str]]:
    if not items:
        return []
    normalized: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append({"hex": str(item.get("hex", "")), "ratio": str(item.get("ratio", ""))})
        else:
            normalized.append({"hex": str(item.hex), "ratio": str(item.ratio)})
    return normalized


def _resolve_reference_items(ref_inputs: List[ReferenceItemInput]) -> List[ReferenceItem]:
    references: List[ReferenceItem] = []
    for ref in ref_inputs:
        url, name = get_reference_url(ref.type, ref.id)
        references.append(
            ReferenceItem(
                type=ref.type,
                id=ref.id,
                name=name,
                url=url,
            )
        )
    return references


def _infer_task_kind(
    model_name: str,
    task_kind: Optional[str],
    ref_urls: List[str],
    enable_sequential: bool,
    bbox_list: Optional[List[List[List[int]]]],
) -> str:
    if task_kind:
        return task_kind
    if model_name in SEEDREAM_MODELS:
        if enable_sequential:
            return "sequential_generation"
        if ref_urls:
            return "image_edit"
        return "text_to_image"
    if model_name in WAN27_MODELS:
        if enable_sequential:
            return "sequential_generation"
        if _bbox_list_has_boxes(bbox_list):
            return "interactive_edit"
        if ref_urls:
            return "image_edit"
        return "text_to_image"
    if model_name in {"wan2.6-image", "wan2.5-i2i-preview", "qwen-image-edit-plus", "qwen-image-edit-max"}:
        return "image_edit"
    if model_name in {"qwen-image-2.0-pro", "qwen-image-2.0"}:
        return "image_edit" if ref_urls else "text_to_image"
    return "text_to_image"


def _bbox_list_has_boxes(bbox_list: Optional[List[List[List[int]]]]) -> bool:
    return any(bool(group) for group in (bbox_list or []))


def _bbox_list_for_task_kind(
    task_kind: str,
    bbox_list: Optional[List[List[List[int]]]],
) -> Optional[List[List[List[int]]]]:
    return bbox_list if task_kind == "interactive_edit" else None


def _validate_model_task_kind(model_name: str, task_kind: str) -> None:
    supported = IMAGE_TASK_KIND_SUPPORT.get(model_name)
    if supported and task_kind not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"模型 {model_name} 不支持任务类型 {task_kind}",
        )


def _build_wan27_size(
    model_name: str,
    task_kind: str,
    size: Optional[str],
    size_mode: Optional[str],
    size_preset: Optional[str],
    custom_width: Optional[int],
    custom_height: Optional[int],
    has_images: bool,
) -> str:
    if size_mode == "custom":
        if custom_width is None or custom_height is None:
            raise HTTPException(status_code=400, detail="自定义尺寸需要同时填写宽度和高度")
        return f"{custom_width}*{custom_height}"
    if size_mode == "preset":
        return size_preset or "2K"
    if custom_width is not None and custom_height is not None:
        return f"{custom_width}*{custom_height}"
    if size_preset:
        return size_preset
    if size:
        return size
    if model_name == "wan2.7-image-pro" and task_kind == "text_to_image" and not has_images:
        return "2K"
    return "2K"


def _resolve_preset_or_custom_size(
    *,
    size: Optional[str],
    size_mode: Optional[str],
    size_preset: Optional[str],
    custom_width: Optional[int],
    custom_height: Optional[int],
    default_size: str,
) -> str:
    if size_mode == "custom":
        if custom_width is None or custom_height is None:
            raise HTTPException(status_code=400, detail="自定义尺寸需要同时填写宽度和高度")
        return f"{custom_width}*{custom_height}"
    if size_mode == "preset":
        if size_preset:
            return size_preset
        return default_size
    if custom_width is not None and custom_height is not None:
        return f"{custom_width}*{custom_height}"
    if size_preset:
        return size_preset
    return size or default_size


def _parse_custom_size(size_value: str) -> Tuple[int, int]:
    try:
        width_text, height_text = size_value.split("*", 1)
        width = int(width_text)
        height = int(height_text)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="自定义尺寸格式必须为 宽*高") from exc
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="自定义尺寸宽高必须为正整数")
    return width, height


def _validate_custom_size(
    *,
    size_value: str,
    min_pixels: int,
    max_pixels: int,
    min_ratio: float,
    max_ratio: float,
    error_prefix: str,
) -> Tuple[int, int]:
    width, height = _parse_custom_size(size_value)
    ratio = width / height if height else 0
    if ratio < min_ratio or ratio > max_ratio:
        raise HTTPException(
            status_code=400,
            detail=f"{error_prefix}宽高比必须在 {min_ratio:.2f} 到 {max_ratio:.2f} 之间",
        )
    pixels = width * height
    if pixels < min_pixels or pixels > max_pixels:
        raise HTTPException(
            status_code=400,
            detail=f"{error_prefix}总像素必须在 {min_pixels} 到 {max_pixels} 之间",
        )
    return width, height


def _normalize_seedream_size(size_value: Optional[str]) -> str:
    value = (size_value or "2048x2048").strip()
    if "*" in value:
        value = value.replace("*", "x")
    return value


def _validate_seedream_request(
    *,
    model_name: str,
    task_kind: str,
    ref_urls: List[str],
    size_value: str,
    n: int,
    output_format: Optional[str],
    web_search: bool,
) -> None:
    if len(ref_urls) > 14:
        raise HTTPException(status_code=400, detail="Seedream 最多支持 14 张参考图片")
    if task_kind == "text_to_image" and ref_urls:
        raise HTTPException(status_code=400, detail="Seedream 文生图模式不支持输入图片")
    if task_kind == "image_edit" and not ref_urls:
        raise HTTPException(status_code=400, detail="Seedream 图像编辑模式至少需要 1 张输入图片")
    if task_kind == "sequential_generation" and len(ref_urls) + max(1, int(n or 1)) > 15:
        raise HTTPException(status_code=400, detail="Seedream 组图模式要求参考图数量 + 最终生成图片数量不超过 15")
    if task_kind != "sequential_generation" and max(1, int(n or 1)) != 1:
        raise HTTPException(status_code=400, detail="Seedream 非组图模式一次只生成 1 张图片，请用并发组数控制总量")
    if output_format and model_name != "doubao-seedream-5.0-lite":
        raise HTTPException(status_code=400, detail="output_format 仅 doubao-seedream-5.0-lite 支持")
    if output_format and output_format not in {"jpeg", "png"}:
        raise HTTPException(status_code=400, detail="Seedream output_format 仅支持 jpeg / png")
    if web_search and model_name != "doubao-seedream-5.0-lite":
        raise HTTPException(status_code=400, detail="web_search 仅 doubao-seedream-5.0-lite 支持")

    allowed_presets = {"2K", "4K"} | ({"3K"} if model_name == "doubao-seedream-5.0-lite" else set())
    if size_value in allowed_presets:
        return
    if size_value in {"1K", "3K", "4K"} and size_value not in allowed_presets:
        raise HTTPException(status_code=400, detail=f"{model_name} 不支持尺寸档位 {size_value}")

    try:
        width_text, height_text = size_value.split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Seedream 尺寸必须是 2K/3K/4K 或 宽x高") from exc
    ratio = width / height if height else 0
    if ratio < 1 / 16 or ratio > 16:
        raise HTTPException(status_code=400, detail="Seedream 自定义尺寸宽高比必须在 1:16 到 16:1 之间")
    pixels = width * height
    if pixels < 2560 * 1440 or pixels > 4096 * 4096:
        raise HTTPException(status_code=400, detail="Seedream 自定义尺寸总像素必须在 2560×1440 到 4096×4096 之间")


def get_image_size_templates(
    *,
    model_name: str,
    task_kind: str,
    has_images: bool,
    enable_sequential: bool = False,
) -> List[Dict[str, Any]]:
    if model_name == "wan2.7-image-pro":
        max_pixels = WAN27_PRO_MAX_TOTAL_PIXELS if task_kind == "text_to_image" and not has_images and not enable_sequential else WAN27_STANDARD_MAX_TOTAL_PIXELS
        min_pixels = WAN27_MIN_TOTAL_PIXELS
        min_ratio = WAN27_MIN_RATIO
        max_ratio = WAN27_MAX_RATIO
    elif model_name == "wan2.7-image":
        max_pixels = WAN27_STANDARD_MAX_TOTAL_PIXELS
        min_pixels = WAN27_MIN_TOTAL_PIXELS
        min_ratio = WAN27_MIN_RATIO
        max_ratio = WAN27_MAX_RATIO
    elif model_name == "wan2.5-t2i-preview":
        max_pixels = WAN25_T2I_MAX_PIXELS
        min_pixels = WAN25_T2I_MIN_PIXELS
        min_ratio = WAN25_T2I_MIN_RATIO
        max_ratio = WAN25_T2I_MAX_RATIO
    elif model_name == "wan2.5-i2i-preview":
        max_pixels = WAN25_I2I_MAX_PIXELS
        min_pixels = WAN25_I2I_MIN_PIXELS
        min_ratio = WAN25_I2I_MIN_RATIO
        max_ratio = WAN25_I2I_MAX_RATIO
    else:
        return []

    templates: List[Dict[str, Any]] = []
    for ratio_text, orientation, ratio in IMAGE_TEMPLATE_RATIOS:
        if ratio < min_ratio or ratio > max_ratio:
            continue
        width = max(1, int(math.sqrt(max_pixels * ratio)))
        height = max(1, int(math.sqrt(max_pixels / ratio)))
        pixels = width * height
        while pixels > max_pixels and width > 1 and height > 1:
            width -= 1
            height -= 1
            pixels = width * height
        if pixels < min_pixels:
            continue
        templates.append(
            {
                "ratio": ratio_text,
                "orientation": orientation,
                "width": width,
                "height": height,
                "label": f"{ratio_text} {orientation} {width}×{height}",
            }
        )
    return templates


def get_wan27_size_mode_parameters() -> List[Dict[str, Any]]:
    return [
        {
            "name": "size_mode",
            "label": "尺寸定义方式",
            "type": "select",
            "description": "选择规格档位或自定义宽高像素。",
            "default": "custom",
            "group": "size",
            "order": 1,
            "constraint": {
                "options": [
                    {"value": "custom", "label": "自定义宽高（指定比例）"},
                    {"value": "preset", "label": "规格档位（跟随输入图/默认正方形）"},
                ]
            },
        },
        {
            "name": "size_preset",
            "label": "规格档位",
            "type": "select",
            "description": "1K/2K/4K 档位。有输入图时跟随最后一张输入图比例，无输入图时默认正方形。",
            "default": "2K",
            "group": "size",
            "order": 2,
            "constraint": {
                "depends_on": "size_mode",
                "depends_value": "preset",
                "options": [
                    {"value": "1K", "label": "1K"},
                    {"value": "2K", "label": "2K"},
                    {"value": "4K", "label": "4K（仅 wan2.7-image-pro 纯文生图）"},
                ],
            },
        },
        {
            "name": "custom_width",
            "label": "自定义宽度",
            "type": "integer",
            "description": "自定义像素宽度。",
            "default": 2048,
            "group": "size",
            "order": 3,
            "constraint": {"min_value": 1, "max_value": 12000, "depends_on": "size_mode", "depends_value": "custom"},
        },
        {
            "name": "custom_height",
            "label": "自定义高度",
            "type": "integer",
            "description": "自定义像素高度。",
            "default": 2048,
            "group": "size",
            "order": 4,
            "constraint": {"min_value": 1, "max_value": 12000, "depends_on": "size_mode", "depends_value": "custom"},
        },
    ]


async def _inspect_and_validate_wan27_images(ref_urls: List[str]) -> List[Dict[str, Any]]:
    metadata_list: List[Dict[str, Any]] = []
    for index, url in enumerate(ref_urls, start=1):
        last_error: Optional[Exception] = None
        for attempt in range(len(WAN27_IMAGE_INSPECT_RETRY_DELAYS) + 1):
            try:
                metadata = await inspect_remote_image(url)
                break
            except Exception as exc:
                last_error = exc
                if attempt < len(WAN27_IMAGE_INSPECT_RETRY_DELAYS):
                    await asyncio.sleep(WAN27_IMAGE_INSPECT_RETRY_DELAYS[attempt])
        else:
            url_summary = _summarize_media_url(url)
            raise HTTPException(status_code=400, detail=f"第 {index} 张输入图片无法读取（{url_summary}）: {last_error}") from last_error

        image_format = (metadata.get("format") or "").upper()
        width = int(metadata.get("width") or 0)
        height = int(metadata.get("height") or 0)
        ratio = float(metadata.get("aspect_ratio") or 0)
        file_size = int(metadata.get("file_size") or 0)

        if image_format not in WAN27_ALLOWED_IMAGE_FORMATS:
            raise HTTPException(status_code=400, detail=f"第 {index} 张输入图片格式不支持，仅支持 JPEG/JPG/PNG/BMP/WEBP")
        if not (WAN27_MIN_IMAGE_DIM <= width <= WAN27_MAX_IMAGE_DIM and WAN27_MIN_IMAGE_DIM <= height <= WAN27_MAX_IMAGE_DIM):
            raise HTTPException(status_code=400, detail=f"第 {index} 张输入图片宽高需在 {WAN27_MIN_IMAGE_DIM} 到 {WAN27_MAX_IMAGE_DIM} 像素之间")
        if ratio < WAN27_MIN_RATIO or ratio > WAN27_MAX_RATIO:
            raise HTTPException(status_code=400, detail=f"第 {index} 张输入图片宽高比需在 1:8 到 8:1 之间")
        if file_size > WAN27_MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail=f"第 {index} 张输入图片大小不能超过 20MB")

        metadata_list.append(metadata)
    return metadata_list


def _normalize_bbox_list(
    bbox_list: Optional[List[List[List[int]]]],
    image_metadata: List[Dict[str, Any]],
) -> Optional[List[List[List[int]]]]:
    if bbox_list is None:
        return None
    if len(bbox_list) != len(image_metadata):
        raise HTTPException(status_code=400, detail="bbox_list 长度必须与输入图片数量一致")

    normalized_bbox_list: List[List[List[int]]] = []
    for box_group, metadata in zip(bbox_list, image_metadata):
        width = int(metadata.get("width") or 0)
        height = int(metadata.get("height") or 0)
        normalized_group: List[List[int]] = []
        for box in box_group:
            if len(box) != 4:
                raise HTTPException(status_code=400, detail="框选坐标格式必须为 [x1, y1, x2, y2]")
            left, right = sorted((int(round(box[0])), int(round(box[2]))))
            top, bottom = sorted((int(round(box[1])), int(round(box[3]))))
            left = max(0, min(left, width))
            right = max(0, min(right, width))
            top = max(0, min(top, height))
            bottom = max(0, min(bottom, height))
            if right <= left or bottom <= top:
                raise HTTPException(status_code=400, detail="框选区域无效，请重新绘制")
            normalized_group.append([left, top, right, bottom])
        normalized_bbox_list.append(normalized_group)
    return normalized_bbox_list


def _validate_wan27_request(
    model_name: str,
    task_kind: str,
    ref_urls: List[str],
    size_value: str,
    n: int,
    enable_sequential: bool,
    thinking_mode: Optional[bool],
    bbox_list: Optional[List[List[List[int]]]],
    color_palette: List[Dict[str, str]],
) -> List[str]:
    warnings: List[str] = []
    if len(ref_urls) > 9:
        raise HTTPException(status_code=400, detail="wan2.7 最多支持 9 张输入图片")

    if enable_sequential:
        if not 1 <= n <= 12:
            raise HTTPException(status_code=400, detail="wan2.7 组图模式下 n 必须在 1-12 之间")
        if thinking_mode:
            warnings.append("组图模式下 thinking_mode 不生效，已忽略")
        if color_palette:
            raise HTTPException(status_code=400, detail="wan2.7 组图模式下不支持颜色主题")
    else:
        if not 1 <= n <= 4:
            raise HTTPException(status_code=400, detail="wan2.7 普通模式下 n 必须在 1-4 之间")
        if thinking_mode and ref_urls:
            warnings.append("有输入图片时 thinking_mode 不生效，已忽略")

    if task_kind == "interactive_edit":
        if not ref_urls:
            raise HTTPException(status_code=400, detail="交互式编辑至少需要 1 张输入图片")
        if bbox_list is None:
            raise HTTPException(status_code=400, detail="交互式编辑需要 bbox_list")
        if len(bbox_list) != len(ref_urls):
            raise HTTPException(status_code=400, detail="bbox_list 长度必须与输入图片数量一致")
        for box_group in bbox_list:
            if len(box_group) > 2:
                raise HTTPException(status_code=400, detail="单张图片最多支持 2 个框选区域")
            for box in box_group:
                if len(box) != 4:
                    raise HTTPException(status_code=400, detail="框选坐标格式必须为 [x1, y1, x2, y2]")

    if color_palette:
        if len(color_palette) < 3 or len(color_palette) > 10:
            raise HTTPException(status_code=400, detail="颜色主题必须包含 3-10 种颜色")
        total_ratio = 0.0
        for item in color_palette:
            hex_value = (item.get("hex") or "").strip()
            ratio_text = (item.get("ratio") or "").strip()
            if not WAN27_HEX_COLOR_PATTERN.match(hex_value):
                raise HTTPException(status_code=400, detail="颜色主题 hex 必须是 #RRGGBB 格式")
            if not WAN27_RATIO_PATTERN.match(ratio_text):
                raise HTTPException(status_code=400, detail="颜色主题比例必须是两位小数百分比格式，例如 25.00%")
            total_ratio += float(ratio_text[:-1])
        if abs(total_ratio - 100.0) > 0.01:
            raise HTTPException(status_code=400, detail="颜色主题比例总和必须为 100.00%")

    if size_value == "4K" and (model_name != "wan2.7-image-pro" or ref_urls or task_kind == "sequential_generation"):
        raise HTTPException(status_code=400, detail="4K 仅支持 wan2.7-image-pro 的纯文生图场景")

    if "*" in size_value:
        try:
            width, height = (int(part) for part in size_value.split("*", 1))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="自定义尺寸格式必须为 宽*高") from exc
        ratio = width / height if height else 0
        if ratio < 0.125 or ratio > 8:
            raise HTTPException(status_code=400, detail="自定义尺寸宽高比必须在 1:8 到 8:1 之间")
        pixels = width * height
        max_pixels = 4096 * 4096 if (model_name == "wan2.7-image-pro" and not ref_urls and task_kind == "text_to_image") else 2048 * 2048
        if pixels < 768 * 768 or pixels > max_pixels:
            raise HTTPException(status_code=400, detail="自定义尺寸总像素不符合当前模型或模式限制")
    elif size_value not in {"1K", "2K", "4K"}:
        raise HTTPException(status_code=400, detail="wan2.7 尺寸只支持 1K / 2K / 4K 或自定义像素")

    return warnings


def _build_provider_payload(
    *,
    model_name: str,
    prompt: str,
    negative_prompt: str,
    task_kind: str,
    ref_urls: List[str],
    n: int,
    size: Optional[str],
    prompt_extend: bool,
    watermark: bool,
    seed: Optional[int],
    enable_interleave: bool,
    max_images: int,
    enable_sequential: bool,
    thinking_mode: Optional[bool],
    bbox_list: Optional[List[List[List[int]]]],
    color_palette: List[Dict[str, str]],
    size_mode: Optional[str],
    size_preset: Optional[str],
    custom_width: Optional[int],
    custom_height: Optional[int],
    output_format: Optional[str] = None,
    web_search: bool = False,
) -> Tuple[NormalizedStudioRequest, Dict[str, Any], List[str]]:
    provider = _get_image_model_provider(model_name)
    task_kind_resolved = _infer_task_kind(model_name, task_kind, ref_urls, enable_sequential, bbox_list)
    _validate_model_task_kind(model_name, task_kind_resolved)
    normalized_params: Dict[str, Any] = {
        "n": n,
        "watermark": watermark,
    }
    warnings: List[str] = []

    if model_name in SEEDREAM_MODELS:
        final_size = _normalize_seedream_size(size)
        final_n = max(1, int(n or 1))
        normalized_output_format = output_format or ("jpeg" if model_name == "doubao-seedream-5.0-lite" else None)
        _validate_seedream_request(
            model_name=model_name,
            task_kind=task_kind_resolved,
            ref_urls=ref_urls,
            size_value=final_size,
            n=final_n,
            output_format=normalized_output_format,
            web_search=bool(web_search),
        )
        normalized_params.update(
            {
                "size": final_size,
                "prompt_extend": prompt_extend,
                "sequential_image_generation": "auto" if task_kind_resolved == "sequential_generation" else "disabled",
                "max_images": final_n if task_kind_resolved == "sequential_generation" else None,
                "output_format": normalized_output_format,
                "web_search": bool(web_search),
            }
        )
        input_assets = {"images": ref_urls}
        provider_payload = {
            "model": "doubao-seedream-5-0-260128"
            if model_name == "doubao-seedream-5.0-lite"
            else "doubao-seedream-4-5-251128",
            "prompt": prompt,
            "size": final_size,
            "sequential_image_generation": "auto" if task_kind_resolved == "sequential_generation" else "disabled",
            "response_format": "url",
            "stream": False,
            "watermark": watermark,
        }
        if ref_urls:
            provider_payload["image"] = ref_urls[0] if len(ref_urls) == 1 else ref_urls
        if task_kind_resolved == "sequential_generation":
            provider_payload["sequential_image_generation_options"] = {"max_images": final_n}
        if prompt_extend:
            provider_payload["optimize_prompt_options"] = {"mode": "standard"}
        if normalized_output_format and model_name == "doubao-seedream-5.0-lite":
            provider_payload["output_format"] = normalized_output_format
        if web_search and model_name == "doubao-seedream-5.0-lite":
            provider_payload["tools"] = [{"type": "web_search"}]
    elif model_name in WAN27_MODELS:
        effective_bbox_list = _bbox_list_for_task_kind(task_kind_resolved, bbox_list)
        final_size = _build_wan27_size(
            model_name=model_name,
            task_kind=task_kind_resolved,
            size=size,
            size_mode=size_mode,
            size_preset=size_preset,
            custom_width=custom_width,
            custom_height=custom_height,
            has_images=bool(ref_urls),
        )
        warnings = _validate_wan27_request(
            model_name=model_name,
            task_kind=task_kind_resolved,
            ref_urls=ref_urls,
            size_value=final_size,
            n=n,
            enable_sequential=enable_sequential,
            thinking_mode=thinking_mode,
            bbox_list=effective_bbox_list,
            color_palette=color_palette,
        )
        normalized_params.update(
            {
                "size": final_size,
                "enable_sequential": enable_sequential,
                "thinking_mode": thinking_mode,
                "color_palette": color_palette,
                "size_mode": size_mode or ("custom" if "*" in final_size else "preset"),
                "size_preset": size_preset or (final_size if "*" not in final_size else None),
                "custom_width": custom_width,
                "custom_height": custom_height,
                "seed": seed,
            }
        )
        if effective_bbox_list is not None:
            normalized_params["bbox_list"] = effective_bbox_list
        input_assets = {
            "images": ref_urls,
        }
        provider_payload = {
            "model": model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{ "image": url } for url in ref_urls] + [{"text": prompt}],
                    }
                ]
            },
            "parameters": {
                "size": final_size,
                "n": n,
                "watermark": watermark,
            },
        }
        if enable_sequential:
            provider_payload["parameters"]["enable_sequential"] = True
        elif thinking_mode is not None and not ref_urls:
            provider_payload["parameters"]["thinking_mode"] = thinking_mode
        if effective_bbox_list:
            provider_payload["parameters"]["bbox_list"] = effective_bbox_list
        if color_palette:
            provider_payload["parameters"]["color_palette"] = color_palette
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
    elif model_name == "wan2.6-image":
        if task_kind_resolved == "image_edit" and not ref_urls and not enable_interleave:
            raise HTTPException(status_code=400, detail="wan2.6-image 的图像编辑模式至少需要 1 张输入图片")
        if not enable_interleave and not ref_urls:
            raise HTTPException(status_code=400, detail="wan2.6-image 在非图文混合模式下至少需要 1 张参考图")
        if enable_interleave and len(ref_urls) > 1:
            raise HTTPException(status_code=400, detail="wan2.6-image 图文混合模式下最多 1 张参考图")
        normalized_params.update(
            {
                "size": size or "1280*1280",
                "prompt_extend": False if enable_interleave else prompt_extend,
                "seed": seed,
                "enable_interleave": enable_interleave,
                "max_images": max_images,
            }
        )
        input_assets = {"images": ref_urls}
        provider_payload = {
            "model": model_name,
            "input": {
                "prompt": prompt,
                "images": ref_urls or None,
            },
            "parameters": {
                "size": size or "1280*1280",
                "n": 1 if enable_interleave else max(1, min(n, 4)),
                "prompt_extend": False if enable_interleave else prompt_extend,
                "watermark": watermark,
            },
        }
        if negative_prompt:
            provider_payload["input"]["negative_prompt"] = negative_prompt
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
        if enable_interleave:
            provider_payload["parameters"]["enable_interleave"] = True
            provider_payload["parameters"]["max_images"] = max_images
    elif model_name == "wan2.6-t2i":
        if ref_urls:
            raise HTTPException(status_code=400, detail=f"{model_name} 不支持输入图片")
        normalized_params.update({"size": size or "1024*1024", "prompt_extend": prompt_extend, "seed": seed})
        input_assets = {"images": []}
        provider_payload = {
            "model": model_name,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": size or "1024*1024",
                "n": max(1, min(n, 4)),
                "prompt_extend": prompt_extend,
                "watermark": watermark,
            },
        }
        if negative_prompt:
            provider_payload["input"]["negative_prompt"] = negative_prompt
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
    elif model_name == "wan2.5-t2i-preview":
        if ref_urls:
            raise HTTPException(status_code=400, detail="wan2.5-t2i-preview 不支持输入图片")
        final_size = _resolve_preset_or_custom_size(
            size=size,
            size_mode=size_mode,
            size_preset=size_preset,
            custom_width=custom_width,
            custom_height=custom_height,
            default_size="1024*1024",
        )
        _validate_custom_size(
            size_value=final_size,
            min_pixels=WAN25_T2I_MIN_PIXELS,
            max_pixels=WAN25_T2I_MAX_PIXELS,
            min_ratio=WAN25_T2I_MIN_RATIO,
            max_ratio=WAN25_T2I_MAX_RATIO,
            error_prefix="wan2.5-t2i-preview 自定义尺寸",
        )
        normalized_params.update({
            "size": final_size,
            "prompt_extend": prompt_extend,
            "seed": seed,
            "size_mode": size_mode or ("custom" if "*" in final_size else "preset"),
            "size_preset": size_preset or (final_size if "*" not in final_size else None),
            "custom_width": custom_width,
            "custom_height": custom_height,
        })
        input_assets = {"images": []}
        provider_payload = {
            "model": model_name,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": final_size,
                "n": max(1, min(n, 4)),
                "prompt_extend": prompt_extend,
                "watermark": watermark,
            },
        }
        if negative_prompt:
            provider_payload["input"]["negative_prompt"] = negative_prompt
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
    elif model_name == "wan2.5-i2i-preview":
        if not ref_urls:
            raise HTTPException(status_code=400, detail="wan2.5-i2i-preview 需要至少 1 张参考图")
        final_size = _resolve_preset_or_custom_size(
            size=size,
            size_mode=size_mode,
            size_preset=size_preset,
            custom_width=custom_width,
            custom_height=custom_height,
            default_size="1024*1024",
        )
        _validate_custom_size(
            size_value=final_size,
            min_pixels=WAN25_I2I_MIN_PIXELS,
            max_pixels=WAN25_I2I_MAX_PIXELS,
            min_ratio=WAN25_I2I_MIN_RATIO,
            max_ratio=WAN25_I2I_MAX_RATIO,
            error_prefix="wan2.5-i2i-preview 自定义尺寸",
        )
        normalized_params.update({
            "size": final_size,
            "prompt_extend": prompt_extend,
            "seed": seed,
            "size_mode": size_mode or ("custom" if "*" in final_size else "preset"),
            "size_preset": size_preset or (final_size if "*" not in final_size else None),
            "custom_width": custom_width,
            "custom_height": custom_height,
        })
        input_assets = {"images": ref_urls}
        provider_payload = {
            "model": model_name,
            "input": {
                "prompt": prompt,
                "images": ref_urls,
            },
            "parameters": {
                "size": final_size,
                "n": max(1, min(n, 4)),
                "prompt_extend": prompt_extend,
            },
        }
        if negative_prompt:
            provider_payload["input"]["negative_prompt"] = negative_prompt
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
    elif model_name in QWEN_IMAGE_MODELS:
        if model_name in {"qwen-image-max", "qwen-image-plus"} and ref_urls:
            raise HTTPException(status_code=400, detail=f"{model_name} 不支持输入图片")
        if model_name in {"qwen-image-edit-plus", "qwen-image-edit-max"} and not ref_urls:
            raise HTTPException(status_code=400, detail=f"{model_name} 需要至少 1 张输入图片")
        if model_name in {"qwen-image-edit-plus", "qwen-image-edit-max"} and size and n > 1:
            raise HTTPException(status_code=400, detail=f"{model_name} 的 size 仅在 n=1 时生效")
        if model_name in {"qwen-image-2.0-pro", "qwen-image-2.0"} and task_kind_resolved == "image_edit" and not ref_urls:
            raise HTTPException(status_code=400, detail=f"{model_name} 的图像编辑模式至少需要 1 张输入图片")
        input_assets = {"images": ref_urls}
        normalized_params.update({"size": size, "prompt_extend": prompt_extend, "seed": seed})
        content = [{"image": url} for url in ref_urls] + [{"text": prompt}]
        provider_payload = {
            "model": model_name,
            "input": {
                "messages": [{"role": "user", "content": content}],
            },
            "parameters": {
                "n": max(1, min(n, 6 if "edit" in model_name or "2.0" in model_name else 1)),
                "watermark": watermark,
                "prompt_extend": prompt_extend,
            },
        }
        if size:
            provider_payload["parameters"]["size"] = size
        if negative_prompt:
            provider_payload["parameters"]["negative_prompt"] = negative_prompt
        if seed is not None:
            provider_payload["parameters"]["seed"] = seed
    else:
        raise HTTPException(status_code=400, detail=f"暂不支持模型 {model_name}")

    canonical = NormalizedStudioRequest(
        project_id="",
        task_kind=task_kind_resolved,
        provider=provider,
        model_id=model_name,
        prompt=prompt,
        negative_prompt=negative_prompt,
        input_assets=input_assets,
        normalized_params=normalized_params,
    )
    return canonical, provider_payload, warnings


@router.get("")
async def list_studio_tasks(project_id: str):
    """获取项目所有图片工作室任务"""
    tasks = storage_service.get_studio_tasks_by_project(project_id)
    changed_tasks: List[StudioTask] = []
    for task in tasks:
        if _expire_local_fallback_images(task):
            changed_tasks.append(task)
        next_warnings = _build_task_storage_warnings(task)
        if task.warnings != next_warnings:
            task.warnings = next_warnings
            changed_tasks.append(task)
    for task in {task.id: task for task in changed_tasks}.values():
        storage_service.save_studio_task(task)
    _schedule_due_local_fallback_retries(tasks, get_current_user_id(), get_user_config_dir())
    return {"tasks": tasks}


@router.post("")
async def create_studio_task(request: TaskCreateRequest):
    """创建图片工作室任务"""
    references = _resolve_reference_items(request.references)
    ref_urls = [ref.url for ref in references if ref.url]
    task_kind = _infer_task_kind(
        request.model,
        request.task_kind,
        ref_urls,
        bool(request.enable_sequential),
        request.bbox_list,
    )
    bbox_list = _bbox_list_for_task_kind(task_kind, request.bbox_list)
    color_palette = _serialize_color_palette(request.color_palette)

    task = StudioTask(
        project_id=request.project_id,
        name=request.name,
        description=request.description,
        model=request.model,
        model_id=request.model,
        provider=_get_image_model_provider(request.model),
        task_kind=task_kind,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        n=request.n,
        group_count=request.group_count,
        size=request.size,
        prompt_extend=request.prompt_extend if request.prompt_extend is not None else True,
        watermark=bool(request.watermark),
        seed=request.seed,
        enable_interleave=bool(request.enable_interleave),
        max_images=request.max_images or 5,
        enable_sequential=bool(request.enable_sequential),
        thinking_mode=request.thinking_mode,
        bbox_list=bbox_list or [],
        color_palette=color_palette,
        size_mode=request.size_mode,
        size_preset=request.size_preset,
        custom_width=request.custom_width,
        custom_height=request.custom_height,
        output_format=request.output_format,
        web_search=bool(request.web_search),
        references=references,
        input_assets={"images": ref_urls},
        normalized_params={
            "size": request.size,
            "prompt_extend": request.prompt_extend if request.prompt_extend is not None else True,
            "watermark": bool(request.watermark),
            "seed": request.seed,
            "enable_interleave": bool(request.enable_interleave),
            "max_images": request.max_images or 5,
            "enable_sequential": bool(request.enable_sequential),
            "thinking_mode": request.thinking_mode,
            **({"bbox_list": bbox_list or []} if task_kind == "interactive_edit" else {}),
            "color_palette": color_palette,
            "size_mode": request.size_mode,
            "size_preset": request.size_preset,
            "custom_width": request.custom_width,
            "custom_height": request.custom_height,
            "output_format": request.output_format,
            "web_search": bool(request.web_search),
        },
        status="pending"
    )
    storage_service.save_studio_task(task)
    return task


@router.get("/{task_id}")
async def get_studio_task(task_id: str):
    """获取任务详情"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.provider_payload_snapshot:
        try:
            ref_urls = [ref.url for ref in task.references if ref.url]
            canonical, provider_payload, _ = _build_provider_payload(
                model_name=task.model,
                prompt=task.prompt,
                negative_prompt=task.negative_prompt,
                task_kind=task.task_kind,
                ref_urls=ref_urls,
                n=task.n,
                size=task.size,
                prompt_extend=task.prompt_extend,
                watermark=task.watermark,
                seed=task.seed,
                enable_interleave=task.enable_interleave,
                max_images=task.max_images,
                enable_sequential=task.enable_sequential,
                thinking_mode=task.thinking_mode,
                bbox_list=task.bbox_list,
                color_palette=task.color_palette,
                size_mode=task.size_mode,
                size_preset=task.size_preset,
                custom_width=task.custom_width,
                custom_height=task.custom_height,
                output_format=task.output_format,
                web_search=task.web_search,
            )
            canonical.project_id = task.project_id
            task.provider_payload_snapshot = provider_payload
            task.model_id = task.model
            task.provider = canonical.provider
            task.task_kind = canonical.task_kind
            task.input_assets = canonical.input_assets
            task.normalized_params = canonical.normalized_params
            storage_service.save_studio_task(task)
        except Exception:
            logger.debug("回填图片工作室 payload 快照失败", exc_info=True)
    changed = _expire_local_fallback_images(task)
    next_warnings = _build_task_storage_warnings(task)
    if task.warnings != next_warnings:
        task.warnings = next_warnings
        changed = True
    if changed:
        storage_service.save_studio_task(task)
    _schedule_due_local_fallback_retries([task], get_current_user_id(), get_user_config_dir())
    return task


@router.post("/preview-payload")
async def preview_payload(request: PreviewPayloadRequest):
    """预览当前草稿对应的 canonical request 与厂商 payload"""
    references = _resolve_reference_items(request.references)
    ref_urls = [ref.url for ref in references if ref.url]
    task_kind = _infer_task_kind(
        request.model,
        request.task_kind,
        ref_urls,
        bool(request.enable_sequential),
        request.bbox_list,
    )
    bbox_list = _bbox_list_for_task_kind(task_kind, request.bbox_list)
    if request.model in WAN27_MODELS and ref_urls:
        image_metadata = await _inspect_and_validate_wan27_images(ref_urls)
        if task_kind == "interactive_edit":
            bbox_list = _normalize_bbox_list(bbox_list, image_metadata)
    canonical, provider_payload, warnings = _build_provider_payload(
        model_name=request.model,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt or "",
        task_kind=task_kind,
        ref_urls=ref_urls,
        n=request.n or 1,
        size=request.size,
        prompt_extend=request.prompt_extend if request.prompt_extend is not None else True,
        watermark=bool(request.watermark),
        seed=request.seed,
        enable_interleave=bool(request.enable_interleave),
        max_images=request.max_images or 5,
        enable_sequential=bool(request.enable_sequential),
        thinking_mode=request.thinking_mode,
        bbox_list=bbox_list,
        color_palette=_serialize_color_palette(request.color_palette),
        size_mode=request.size_mode,
        size_preset=request.size_preset,
        custom_width=request.custom_width,
        custom_height=request.custom_height,
        output_format=request.output_format,
        web_search=bool(request.web_search),
    )
    canonical.project_id = request.project_id
    return {
        "canonical_request": asdict(canonical),
        "provider_payload": provider_payload,
        "validation_warnings": warnings,
    }


@router.put("/{task_id}")
async def update_studio_task(task_id: str, request: TaskUpdateRequest):
    """更新任务信息"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = request.model_dump(exclude_unset=True)
    nullable_fields = {
        "negative_prompt",
        "size",
        "seed",
        "thinking_mode",
        "size_mode",
        "size_preset",
        "custom_width",
        "custom_height",
        "output_format",
    }
    
    # 如果更新了参考素材，需要重新获取URL
    if "references" in update_data and update_data["references"] is not None:
        references = []
        for ref in update_data["references"]:
            ref_type = ref["type"] if isinstance(ref, dict) else ref.type
            ref_id = ref["id"] if isinstance(ref, dict) else ref.id
            url, name = get_reference_url(ref_type, ref_id)
            references.append(ReferenceItem(type=ref_type, id=ref_id, name=name, url=url))
        task.references = references
        del update_data["references"]

    if "color_palette" in update_data:
        task.color_palette = _serialize_color_palette(update_data["color_palette"]) if update_data["color_palette"] is not None else []
        del update_data["color_palette"]

    if "bbox_list" in update_data and update_data["bbox_list"] is None:
        task.bbox_list = []
        del update_data["bbox_list"]

    for key, value in update_data.items():
        if value is not None or key in nullable_fields:
            setattr(task, key, value)

    ref_urls = [ref.url for ref in task.references if ref.url]
    task.model_id = task.model
    task.provider = _get_image_model_provider(task.model)
    task.task_kind = _infer_task_kind(task.model, task.task_kind, ref_urls, task.enable_sequential, task.bbox_list)
    task.bbox_list = _bbox_list_for_task_kind(task.task_kind, task.bbox_list) or []
    task.input_assets = {"images": ref_urls}
    task.normalized_params = {
        "size": task.size,
        "prompt_extend": task.prompt_extend,
        "watermark": task.watermark,
        "seed": task.seed,
        "enable_interleave": task.enable_interleave,
        "max_images": task.max_images,
        "enable_sequential": task.enable_sequential,
        "thinking_mode": task.thinking_mode,
        **({"bbox_list": task.bbox_list} if task.task_kind == "interactive_edit" else {}),
        "color_palette": task.color_palette,
        "size_mode": task.size_mode,
        "size_preset": task.size_preset,
        "custom_width": task.custom_width,
        "custom_height": task.custom_height,
        "output_format": task.output_format,
        "web_search": task.web_search,
    }

    storage_service.save_studio_task(task)
    return task


class ImageMarkerRequest(BaseModel):
    """更新图片标记"""
    image_id: str
    markers: List[str]  # star, flag, check, cross


@router.post("/{task_id}/markers")
async def update_image_markers(task_id: str, request: ImageMarkerRequest):
    """更新任务中某张图片的标记"""
    VALID_MARKERS = {"star", "flag", "check", "cross"}
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    for img in task.images:
        if img.id == request.image_id:
            img.markers = [m for m in request.markers if m in VALID_MARKERS]
            storage_service.save_studio_task(task)
            return {"success": True, "markers": img.markers}
    raise HTTPException(status_code=404, detail="图片不存在")


@router.post("/{task_id}/retry-oss")
async def retry_task_oss_fallbacks(task_id: str):
    """手动重传当前任务中的本地回退图片到 OSS。"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS 未启用或配置不完整，无法重传")

    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    summary = await _retry_task_local_fallback_images(task, due_only=False, reason="manual_task")
    latest_task = storage_service.get_studio_task(task_id) or task
    return {"task": latest_task, "summary": summary}


@router.post("/project/{project_id}/retry-oss")
async def retry_project_oss_fallbacks(project_id: str):
    """手动重传项目内所有本地回退图片到 OSS。"""
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS 未启用或配置不完整，无法重传")

    tasks = storage_service.get_studio_tasks_by_project(project_id)
    total_summary = {
        "retried_task_count": 0,
        "retried_image_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "paused_count": 0,
        "expired_count": 0,
    }

    for task in tasks:
        if _count_retriable_local_fallback_images(task) <= 0:
            continue
        total_summary["retried_task_count"] += 1
        summary = await _retry_task_local_fallback_images(task, due_only=False, reason="manual_project")
        for key in ("retried_image_count", "success_count", "failed_count", "paused_count", "expired_count"):
            total_summary[key] += summary.get(key, 0)

    latest_tasks = storage_service.get_studio_tasks_by_project(project_id)
    return {"tasks": latest_tasks, "summary": total_summary}


@router.post("/{task_id}/generate")
async def generate_task_images(task_id: str, request: TaskGenerateRequest):
    """启动图片生成（立即返回，后台执行）

    前端通过轮询 GET /{task_id} 获取生成进度和结果。
    """
    from app.config import IMAGE_MODELS

    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status == "generating":
        return {"task": task}
    if not _try_acquire_generation_slot(task_id):
        latest_task = storage_service.get_studio_task(task_id) or task
        return {"task": latest_task}

    try:
        provided_fields = request.model_fields_set

        # 更新任务参数
        if "prompt" in provided_fields and request.prompt is not None:
            task.prompt = request.prompt
        if "negative_prompt" in provided_fields:
            task.negative_prompt = request.negative_prompt
        if "n" in provided_fields and request.n is not None:
            task.n = request.n
        if "group_count" in provided_fields and request.group_count is not None:
            task.group_count = request.group_count
        if "task_kind" in provided_fields and request.task_kind is not None:
            task.task_kind = request.task_kind
        if "size" in provided_fields:
            task.size = request.size
        if "prompt_extend" in provided_fields and request.prompt_extend is not None:
            task.prompt_extend = request.prompt_extend
        if "watermark" in provided_fields and request.watermark is not None:
            task.watermark = request.watermark
        if "seed" in provided_fields:
            task.seed = request.seed
        if "enable_interleave" in provided_fields and request.enable_interleave is not None:
            task.enable_interleave = request.enable_interleave
        if "max_images" in provided_fields and request.max_images is not None:
            task.max_images = request.max_images
        if "enable_sequential" in provided_fields and request.enable_sequential is not None:
            task.enable_sequential = request.enable_sequential
        if "thinking_mode" in provided_fields:
            task.thinking_mode = request.thinking_mode
        if "bbox_list" in provided_fields:
            task.bbox_list = request.bbox_list or []
        if "color_palette" in provided_fields:
            task.color_palette = _serialize_color_palette(request.color_palette) if request.color_palette is not None else []
        if "size_mode" in provided_fields:
            task.size_mode = request.size_mode
        if "size_preset" in provided_fields:
            task.size_preset = request.size_preset
        if "custom_width" in provided_fields:
            task.custom_width = request.custom_width
        if "custom_height" in provided_fields:
            task.custom_height = request.custom_height
        if "output_format" in provided_fields:
            task.output_format = request.output_format
        if "web_search" in provided_fields and request.web_search is not None:
            task.web_search = bool(request.web_search)

        model_name = task.model or "wan2.5-i2i-preview"
        is_text_to_image = model_name in IMAGE_MODELS
        ref_urls = [ref.url for ref in task.references if ref.url]
        normalized_bbox_list = request.bbox_list if request.bbox_list is not None else task.bbox_list
        normalized_bbox_list = _bbox_list_for_task_kind(task.task_kind, normalized_bbox_list)

        # --- 同步验证（在返回前完成）---
        enable_interleave = task.enable_interleave
        if model_name == "wan2.6-image" and not enable_interleave and not ref_urls:
            raise HTTPException(
                status_code=400,
                detail="wan2.6-image 在非图文混合模式下需要参考图，请添加参考素材或开启图文混合模式"
            )
        if not is_text_to_image and model_name not in (
            "wan2.6-image", "qwen-image-max", "qwen-image-plus",
            "qwen-image-edit-plus", "qwen-image-edit-max",
            "qwen-image-2.0-pro", "qwen-image-2.0",
            "wan2.7-image-pro", "wan2.7-image",
            "doubao-seedream-5.0-lite", "doubao-seedream-4.5",
        ) and not ref_urls:
            raise HTTPException(status_code=400, detail="该模型需要参考素材图片")

        color_palette = task.color_palette or []
        canonical, provider_payload, validation_warnings = _build_provider_payload(
            model_name=model_name,
            prompt=task.prompt,
            negative_prompt=task.negative_prompt or "",
            task_kind=task.task_kind,
            ref_urls=ref_urls,
            n=task.n,
            size=task.size,
            prompt_extend=task.prompt_extend,
            watermark=task.watermark,
            seed=task.seed,
            enable_interleave=task.enable_interleave,
            max_images=task.max_images,
            enable_sequential=task.enable_sequential,
            thinking_mode=task.thinking_mode,
            bbox_list=normalized_bbox_list,
            color_palette=color_palette,
            size_mode=task.size_mode,
            size_preset=task.size_preset,
            custom_width=task.custom_width,
            custom_height=task.custom_height,
            output_format=task.output_format,
            web_search=task.web_search,
        )
        canonical.project_id = task.project_id
        canonical_size = (canonical.normalized_params or {}).get("size") or (provider_payload.get("parameters") or {}).get("size") or task.size
        task.size = canonical_size
        task.task_kind = canonical.task_kind
        task.provider = canonical.provider
        task.model_id = canonical.model_id
        task.input_assets = canonical.input_assets
        task.normalized_params = canonical.normalized_params
        task.bbox_list = normalized_bbox_list or []
        task.provider_payload_snapshot = provider_payload
        task.provider_result_meta = {}
        task.task_ids = []
        task.request_ids = []

        # 设置生成状态
        task.status = "generating"
        task.images = []
        task.error_message = "；".join(validation_warnings) if validation_warnings else None
        task.warnings = []
        storage_service.save_studio_task(task)

        # 捕获用户上下文（后台任务需要）
        user_id = get_current_user_id()
        user_config_dir = get_user_config_dir()
        size = canonical_size

        # 后台执行生成，立即返回
        asyncio.create_task(_background_generate(
            task_id=task.id,
            user_id=user_id,
            user_config_dir=user_config_dir,
        ))

        return {"task": task}
    except Exception:
        _release_generation_slot(task_id)
        raise


async def _background_generate(
    task_id: str,
    user_id: Optional[str],
    user_config_dir: Optional[str],
):
    """后台生成任务——由 asyncio.create_task 调度，不阻塞请求。"""
    # 恢复用户上下文，使 storage_service / get_config 使用正确的用户目录
    set_current_user(user_id)
    set_user_config_dir(user_config_dir)

    try:
        from app.config import IMAGE_MODELS

        task = storage_service.get_studio_task(task_id)
        if not task:
            logger.warning("后台生成任务已不存在，跳过 task_id=%s", task_id)
            return

        model_name = task.model or "wan2.5-i2i-preview"
        is_text_to_image = model_name in IMAGE_MODELS
        ref_urls = [ref.url for ref in task.references if ref.url]
        normalized_bbox_list = _bbox_list_for_task_kind(task.task_kind, task.bbox_list)
        if model_name in WAN27_MODELS and ref_urls:
            image_metadata = await _inspect_and_validate_wan27_images(ref_urls)
            if task.task_kind == "interactive_edit":
                normalized_bbox_list = _normalize_bbox_list(normalized_bbox_list, image_metadata)

        canonical, provider_payload, validation_warnings = _build_provider_payload(
            model_name=model_name,
            prompt=task.prompt,
            negative_prompt=task.negative_prompt or "",
            task_kind=task.task_kind,
            ref_urls=ref_urls,
            n=task.n,
            size=task.size,
            prompt_extend=task.prompt_extend,
            watermark=task.watermark,
            seed=task.seed,
            enable_interleave=task.enable_interleave,
            max_images=task.max_images,
            enable_sequential=task.enable_sequential,
            thinking_mode=task.thinking_mode,
            bbox_list=normalized_bbox_list,
            color_palette=task.color_palette or [],
            size_mode=task.size_mode,
            size_preset=task.size_preset,
            custom_width=task.custom_width,
            custom_height=task.custom_height,
            output_format=task.output_format,
            web_search=task.web_search,
        )
        canonical.project_id = task.project_id
        canonical_size = (
            (canonical.normalized_params or {}).get("size")
            or (provider_payload.get("parameters") or {}).get("size")
            or task.size
        )
        task.size = canonical_size
        task.task_kind = canonical.task_kind
        task.provider = canonical.provider
        task.model_id = canonical.model_id
        task.input_assets = canonical.input_assets
        task.normalized_params = canonical.normalized_params
        task.bbox_list = normalized_bbox_list or []
        task.provider_payload_snapshot = provider_payload
        task.provider_result_meta = {}
        task.error_message = "；".join(validation_warnings) if validation_warnings else None
        storage_service.save_studio_task(task)

        request_ids: List[str] = []
        task_ids: List[str] = []
        provider_meta: Dict[str, Any] = {}
        provider_api_key = get_provider_api_key(canonical.provider)
        config = get_config()
        size = canonical_size
        prompt_extend = task.prompt_extend
        watermark = task.watermark
        seed = task.seed
        enable_interleave = task.enable_interleave
        max_images = task.max_images
        enable_sequential = task.enable_sequential
        thinking_mode = task.thinking_mode
        color_palette = task.color_palette or []
        bbox_list = normalized_bbox_list
        output_format = task.output_format
        web_search = task.web_search

        if model_name in SEEDREAM_MODELS:
            images, request_ids, provider_meta = await generate_with_seedream_image(
                task=task,
                api_key=provider_api_key,
                ref_urls=ref_urls,
                size=size,
                output_format=output_format,
                web_search=web_search,
                prompt_extend=prompt_extend,
                watermark=watermark,
            )
        elif model_name in WAN27_MODELS:
            images, task_ids, request_ids, provider_meta = await generate_with_wan27_image(
                task=task,
                api_key=provider_api_key,
                base_url=config.base_url,
                ref_urls=ref_urls,
                size=size,
                enable_sequential=enable_sequential,
                thinking_mode=thinking_mode,
                bbox_list=bbox_list,
                color_palette=color_palette,
                watermark=watermark,
                seed=seed,
            )
        elif model_name == "wan2.6-image":
            images, request_ids = await generate_with_wan26_image(
                task=task,
                ref_urls=ref_urls if ref_urls else None,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                enable_interleave=enable_interleave,
                max_images=max_images,
            )
        elif is_text_to_image:
            images, request_ids = await generate_with_text_to_image(
                task=task,
                model_name=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                size=size,
            )
        elif model_name in ("qwen-image-max", "qwen-image-plus"):
            images, request_ids = await generate_with_qwen_image(
                task=task,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        elif model_name in ("qwen-image-edit-plus", "qwen-image-edit-max"):
            images, request_ids = await generate_with_qwen_image_edit(
                task=task,
                ref_urls=ref_urls,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        elif model_name in ("qwen-image-2.0-pro", "qwen-image-2.0"):
            images, request_ids = await generate_with_qwen_image_2(
                task=task,
                ref_urls=ref_urls,
                api_key=provider_api_key,
                base_url=config.base_url,
                model_name=model_name,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
        else:
            images, request_ids = await generate_with_wanx_i2i(
                task=task,
                ref_urls=ref_urls,
                size=size,
                prompt_extend=prompt_extend,
                seed=seed,
            )

        persist_report = await _ensure_generated_images_persisted(
            images,
            task.project_id,
            model_id=task.model,
            request_ids=request_ids,
            task_ids=task_ids or task.task_ids,
        )
        persist_errors = persist_report["errors"]
        if persist_errors:
            existing_errors = getattr(task, "_group_errors", [])
            task._group_errors = existing_errors + persist_errors

        task.images = images
        task.warnings = _build_task_storage_warnings(task)
        task.task_ids = task_ids or task.task_ids or ([task.last_task_id] if task.last_task_id else [])
        task.request_ids = request_ids
        task.provider_payload_snapshot = provider_payload
        if provider_meta:
            task.provider_result_meta = provider_meta

        valid_images = [img for img in images if img.url]
        group_errors = getattr(task, '_group_errors', [])
        error_detail = ""
        if group_errors:
            unique_errors = list(set(group_errors))
            error_detail = unique_errors[0] if len(unique_errors) == 1 else "; ".join(unique_errors[:3])

        if not images:
            task.status = "failed"
            task.error_message = error_detail or "未生成任何图片，请检查参数或参考图后重试"
        elif not valid_images:
            task.status = "failed"
            task.error_message = error_detail or "所有生成任务均失败，请检查参数或参考图后重试"
        elif len(valid_images) < len(images):
            task.status = "completed"
            task.error_message = (
                f"部分生成失败（{len(valid_images)}/{len(images)} 张成功）: {error_detail}"
                if error_detail
                else f"部分生成失败：{len(valid_images)}/{len(images)} 张成功"
            )
        else:
            task.status = "completed"
            task.error_message = None

    except Exception as e:
        logger.error(f"后台生成失败 [{task.id}]: {e}", exc_info=True)
        task.status = "failed"
        task.error_message = str(e)
        task.warnings = []
    finally:
        storage_service.save_studio_task(task)
        _release_generation_slot(task_id)


async def generate_with_wan27_image(
    task: StudioTask,
    api_key: str,
    base_url: str,
    ref_urls: List[str],
    size: Optional[str],
    enable_sequential: bool,
    thinking_mode: Optional[bool],
    bbox_list: Optional[List[List[List[int]]]],
    color_palette: List[Dict[str, str]],
    watermark: bool,
    seed: Optional[int],
) -> Tuple[List[StudioTaskImage], List[str], List[str], Dict[str, Any]]:
    """使用万相 2.7 图像模型生成"""
    from app.models_registry.image.wan27_image import (
        WAN27_MODEL_INFO,
        WAN27_PRO_MODEL_INFO,
        Wan27ImageService,
    )

    model_info = WAN27_PRO_MODEL_INFO if task.model == "wan2.7-image-pro" else WAN27_MODEL_INFO

    async def generate_single_group(group_index: int):
        service = Wan27ImageService(model_info)
        service.configure(api_key, base_url)

        try:
            external_task_id = await service.create_task(
                prompt=task.prompt,
                images=ref_urls or None,
                size=size or "2K",
                n=max(1, task.n),
                enable_sequential=enable_sequential,
                thinking_mode=thinking_mode,
                color_palette=color_palette or None,
                bbox_list=bbox_list,
                watermark=watermark,
                seed=seed,
            )
        except Exception as exc:
            submit_request_id = service.last_request_id
            error_message = service.last_error_message or str(exc)
            error_code = service.last_error_code or exc.__class__.__name__
            meta_key = submit_request_id or f"submit_error_group_{group_index}"
            meta = {
                meta_key: {
                    "provider": "wan",
                    "key_profile": get_provider_key_profile("wan"),
                    "submit_request_id": submit_request_id,
                    "request_id": submit_request_id,
                    "usage": service.last_usage or {},
                    "error_code": error_code,
                    "error_message": error_message,
                    "raw_output": service.last_raw_output or {},
                    "stage": "submit",
                }
            }
            return [], [], [rid for rid in [submit_request_id] if rid], meta, error_message

        submit_request_id = service.last_request_id

        elapsed = 0
        while elapsed < 300:
            try:
                status = await service.get_task_status(external_task_id)
            except Exception as exc:
                error_message = str(exc)
                meta = {
                    external_task_id: {
                        "provider": "wan",
                        "key_profile": get_provider_key_profile("wan"),
                        "submit_request_id": submit_request_id,
                        "request_id": None,
                        "usage": {},
                        "error_code": exc.__class__.__name__,
                        "error_message": error_message,
                        "raw_output": {},
                        "stage": "poll",
                    }
                }
                return [], [external_task_id], [rid for rid in [submit_request_id] if rid], meta, error_message

            if status.status.value == "succeeded":
                final_urls: List[str] = []
                for url in status.result or []:
                    final_url = url
                    if oss_service.is_enabled():
                        final_url = await oss_service.upload_image_async(url, task.project_id)
                        if final_url == url and oss_service.should_persist_generated_url(url):
                            parsed = urlparse(url)
                            logger.warning(
                                "[OSS][studio] initial persist fallback model_id=%s project_id=%s request_ids=%s task_ids=%s original_host=%s oss_enabled=%s reason=%s",
                                task.model or "unknown",
                                task.project_id or "_global",
                                ",".join([rid for rid in [submit_request_id, (status.metadata or {}).get("request_id")] if rid]) or "-",
                                external_task_id,
                                parsed.netloc or "unknown",
                                oss_service.is_enabled(),
                                "upload_image_async returned original url",
                            )
                    final_urls.append(final_url)

                images = [
                    StudioTaskImage(
                        group_index=group_index * max(1, task.n) + idx,
                        url=url,
                        prompt_used=task.prompt,
                    )
                    for idx, url in enumerate(final_urls)
                ]
                meta = {
                    external_task_id: {
                        "provider": "wan",
                        "key_profile": get_provider_key_profile("wan"),
                        "submit_request_id": submit_request_id,
                        "request_id": (status.metadata or {}).get("request_id"),
                        "usage": (status.metadata or {}).get("usage") or {},
                        "error_code": (status.metadata or {}).get("error_code"),
                        "error_message": (status.metadata or {}).get("error_message"),
                        "raw_output": (status.metadata or {}).get("raw_output") or {},
                    }
                }
                request_ids = [rid for rid in [submit_request_id, (status.metadata or {}).get("request_id")] if rid]
                return images, [external_task_id], request_ids, meta, None

            if status.status.value in {"failed", "cancelled"}:
                meta = {
                    external_task_id: {
                        "provider": "wan",
                        "key_profile": get_provider_key_profile("wan"),
                        "submit_request_id": submit_request_id,
                        "request_id": (status.metadata or {}).get("request_id"),
                        "usage": (status.metadata or {}).get("usage") or {},
                        "error_code": (status.metadata or {}).get("error_code"),
                        "error_message": status.error_message,
                        "raw_output": (status.metadata or {}).get("raw_output") or {},
                    }
                }
                request_ids = [rid for rid in [submit_request_id, (status.metadata or {}).get("request_id")] if rid]
                return [], [external_task_id], request_ids, meta, status.error_message or "万相2.7 生成失败"

            await asyncio.sleep(2)
            elapsed += 2

        return [], [external_task_id], [rid for rid in [submit_request_id] if rid], {
            external_task_id: {
                "provider": "wan",
                "key_profile": get_provider_key_profile("wan"),
                "submit_request_id": submit_request_id,
                "request_id": None,
                "usage": {},
                "error_code": "Timeout",
                "error_message": "万相2.7 生成超时",
                "raw_output": {},
            }
        }, "万相2.7 生成超时"

    all_images: List[StudioTaskImage] = []
    all_task_ids: List[str] = []
    all_request_ids: List[str] = []
    all_meta: Dict[str, Any] = {}
    group_errors: List[str] = []

    group_count = max(1, task.group_count or 1)
    group_tasks = [generate_single_group(group_index) for group_index in range(group_count)]
    for images, task_ids, request_ids, meta, error in await asyncio.gather(*group_tasks):
        all_images.extend(images)
        all_task_ids.extend(task_ids)
        all_request_ids.extend(request_ids)
        all_meta.update(meta)
        if error:
            group_errors.append(error)

    if group_errors:
        task._group_errors = group_errors

    return all_images, all_task_ids, all_request_ids, all_meta


async def generate_with_seedream_image(
    task: StudioTask,
    api_key: str,
    ref_urls: List[str],
    size: Optional[str],
    output_format: Optional[str],
    web_search: bool,
    prompt_extend: bool,
    watermark: bool,
) -> Tuple[List[StudioTaskImage], List[str], Dict[str, Any]]:
    """使用火山引擎 Seedream 图片模型生成。"""
    from app.models_registry.image.seedream import (
        SEEDREAM_45_MODEL_INFO,
        SEEDREAM_5_LITE_MODEL_INFO,
        SeedreamImageService,
    )

    model_info = (
        SEEDREAM_5_LITE_MODEL_INFO
        if task.model == "doubao-seedream-5.0-lite"
        else SEEDREAM_45_MODEL_INFO
    )
    expected_count = max(1, int(task.n or 1)) if task.task_kind == "sequential_generation" else 1

    async def generate_single_group(group_index: int):
        service = SeedreamImageService(model_info)
        service.configure(api_key)
        try:
            urls, request_id, meta = await service.generate(
                prompt=task.prompt,
                images=ref_urls,
                size=size or "2048x2048",
                n=expected_count,
                task_kind=task.task_kind,
                prompt_extend=prompt_extend,
                watermark=watermark,
                output_format=output_format,
                web_search=web_search,
            )
        except Exception as exc:
            error_message = str(exc)
            meta_key = f"submit_error_group_{group_index}"
            meta = {
                meta_key: {
                    "provider": "volcengine",
                    "key_profile": "volcengine_api_key",
                    "request_id": None,
                    "usage": {},
                    "tools": [],
                    "item_errors": [],
                    "error_code": exc.__class__.__name__,
                    "error_message": error_message,
                    "raw_response": {},
                    "stage": "submit",
                }
            }
            placeholders = [
                StudioTaskImage(
                    group_index=group_index * expected_count + idx,
                    url=None,
                    prompt_used=task.prompt,
                )
                for idx in range(expected_count)
            ]
            return placeholders, [], meta, error_message

        images: List[StudioTaskImage] = []
        group_errors: List[str] = []
        data_items = (meta.get("raw_response") or {}).get("data") or []
        if data_items:
            for idx, item in enumerate(data_items):
                item_error = item.get("error") or {}
                images.append(
                    StudioTaskImage(
                        group_index=group_index * expected_count + idx,
                        url=item.get("url"),
                        prompt_used=task.prompt,
                    )
                )
                if item_error:
                    group_errors.append(
                        item_error.get("message")
                        or item_error.get("code")
                        or "Seedream 单图生成失败"
                    )
        else:
            images.extend(
                StudioTaskImage(
                    group_index=group_index * expected_count + idx,
                    url=url,
                    prompt_used=task.prompt,
                )
                for idx, url in enumerate(urls)
            )

        if not images:
            images = [
                StudioTaskImage(
                    group_index=group_index * expected_count,
                    url=None,
                    prompt_used=task.prompt,
                )
            ]
            group_errors.append("Seedream 未返回有效图片")

        meta_key = request_id or f"group_{group_index}"
        provider_meta = {
            meta_key: {
                "provider": "volcengine",
                "key_profile": "volcengine_api_key",
                "request_id": request_id,
                "usage": meta.get("usage") or {},
                "tools": meta.get("tools") or [],
                "item_errors": meta.get("item_errors") or [],
                "error_code": None,
                "error_message": "; ".join(dict.fromkeys(group_errors)) if group_errors else None,
                "raw_response": meta.get("raw_response") or {},
            }
        }
        return images, [request_id] if request_id else [], provider_meta, provider_meta[meta_key]["error_message"]

    all_images: List[StudioTaskImage] = []
    all_request_ids: List[str] = []
    all_meta: Dict[str, Any] = {}
    group_errors: List[str] = []

    group_count = max(1, int(task.group_count or 1))
    results = await asyncio.gather(*(generate_single_group(group_index) for group_index in range(group_count)))
    for images, request_ids, meta, error in results:
        all_images.extend(images)
        all_request_ids.extend(request_ids)
        all_meta.update(meta)
        if error:
            group_errors.append(error)

    if group_errors:
        task._group_errors = group_errors
    all_images.sort(key=lambda image: image.group_index)
    return all_images, all_request_ids, all_meta


async def generate_with_text_to_image(
    task: StudioTask,
    model_name: str,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    size: Optional[str] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用文生图模型生成
    
    支持模型：wan2.6-t2i, wan2.5-t2i-preview
    
    Returns:
        (images, request_ids)
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 1
    group_count = task.group_count or 3
    
    logger.info(f"[文生图] 开始生成: n={n}, group_count={group_count}, total={n * group_count}")
    
    width = None
    height = None
    if size:
        try:
            parts = size.split('*')
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
        except ValueError:
            pass
    
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> tuple[List[StudioTaskImage], bool, str, str, str]:
        """Returns: (图片列表, 是否成功, 错误信息, task_id, request_id)"""
        try:
            result = await t2i_service.generate_batch(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt or "",
                width=width,
                height=height,
                n=n,
                model=model_name,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                project_id=task.project_id
            )
            
            images = []
            for i, url in enumerate(result.urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images, True, "", result.task_id or "", result.request_id or ""
        except Exception as e:
            import traceback
            error_msg = str(e)
            logger.error(f"文生图生成失败 (组{group_index}): {e}")
            traceback.print_exc()
            return [], False, error_msg, "", ""
    
    logger.info(f"[文生图] 开始并发生成 {group_count} 组...")
    group_tasks = [generate_single_group(i) for i in range(group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    failed_groups = []
    
    for i, (images, success, error_msg, tid, rid) in enumerate(results):
        if success:
            all_images.extend(images)
            if rid:
                collected_request_ids.append(rid)
        else:
            failed_groups.append((i, error_msg))
    
    if failed_groups:
        logger.info(f"[文生图] {len(failed_groups)} 个组失败，回退到串行重试...")
        max_retries = 3
        
        for group_index, original_error in failed_groups:
            retry_success = False
            
            for retry in range(max_retries):
                wait_time = 2 * (retry + 1)
                logger.info(f"[文生图] 组{group_index} 等待 {wait_time}s 后重试 ({retry + 1}/{max_retries})...")
                await asyncio.sleep(wait_time)
                
                images, success, error_msg, tid, rid = await generate_single_group(group_index)
                if success:
                    all_images.extend(images)
                    retry_success = True
                    if rid:
                        collected_request_ids.append(rid)
                    logger.info(f"[文生图] 组{group_index} 重试成功")
                    break
            
            if not retry_success:
                logger.error(f"[文生图] 组{group_index} 重试全部失败")
                for i in range(n):
                    all_images.append(StudioTaskImage(
                        group_index=group_index * n + i,
                        url=None,
                        prompt_used=task.prompt
                    ))
    
    all_images.sort(key=lambda img: img.group_index)
    
    success_count = sum(1 for img in all_images if img.url)
    logger.info(f"[文生图] 生成完成: 共 {len(all_images)} 张图片，成功 {success_count} 张")
    logger.info(f"[文生图] request_ids: {collected_request_ids}")
    return all_images, collected_request_ids


async def generate_with_wan26_image(
    task: StudioTask,
    ref_urls: Optional[List[str]] = None,
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    enable_interleave: bool = False,
    max_images: int = 5
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用 wan2.6-image 模型生成

    Returns:
        (images, request_ids)
    """
    from app.services.dashscope.text_to_image import TextToImageService
    
    t2i_service = TextToImageService()
    n = task.n or 4
    
    if enable_interleave:
        n = 1
        prompt_extend = False
    else:
        n = min(n, 4)
    
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await t2i_service.generate_with_wan26_image(
                prompt=task.prompt,
                image_urls=ref_urls,
                negative_prompt=task.negative_prompt or "",
                n=n,
                size=size or "1280*1280",
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                enable_interleave=enable_interleave,
                max_images=max_images,
                project_id=task.project_id
            )
            if rid:
                collected_request_ids.append(rid)
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            import traceback
            logger.error(f"wan2.6-image 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_wanx_i2i(
    task: StudioTask,
    ref_urls: List[str],
    size: Optional[str] = None,
    prompt_extend: bool = True,
    seed: Optional[int] = None,
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用万相图生图模型生成

    Returns:
        (images, request_ids)
    """
    i2i_service = ImageToImageService()
    n = task.n or 1
    
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            width = None
            height = None
            if size:
                try:
                    width_text, height_text = size.split("*", 1)
                    width = int(width_text)
                    height = int(height_text)
                except ValueError:
                    width = None
                    height = None
            urls, rid = await i2i_service.generate_with_multi_images(
                prompt=task.prompt,
                image_urls=ref_urls,
                negative_prompt=task.negative_prompt,
                width=width,
                height=height,
                model=task.model,
                prompt_extend=prompt_extend,
                seed=seed,
                n=n,
                project_id=task.project_id
            )
            if rid:
                collected_request_ids.append(rid)
            if isinstance(urls, str):
                urls = [urls]
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    group_tasks = [generate_single_group(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    all_images = []
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image_edit(
    task: StudioTask,
    ref_urls: List[str],
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-edit-max",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用通义千问图像编辑模型生成（plus/max 共用）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image_edit import (
        QwenImageEditService, QWEN_IMAGE_EDIT_PLUS_MODEL_INFO, QWEN_IMAGE_EDIT_MAX_MODEL_INFO
    )
    
    if len(ref_urls) > 3:
        raise ValueError(f"{model_name} 最多支持3张输入图片")
    
    model_info = QWEN_IMAGE_EDIT_MAX_MODEL_INFO if model_name == "qwen-image-edit-max" else QWEN_IMAGE_EDIT_PLUS_MODEL_INFO
    service = QwenImageEditService(model_info)
    service.configure(api_key, base_url)
    
    n = task.n or 1
    if n > 6:
        n = 6
    
    all_images = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single_group(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                images=ref_urls,
                negative_prompt=task.negative_prompt,
                n=n,
                size=size,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                project_id=task.project_id
            )
            if rid:
                collected_request_ids.append(rid)
            
            images = []
            for i, url in enumerate(urls):
                images.append(StudioTaskImage(
                    group_index=group_index * n + i,
                    url=url,
                    prompt_used=task.prompt
                ))
            return images
        except Exception as e:
            import traceback
            logger.error(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index * n + i,
                url=None,
                prompt_used=task.prompt
            ) for i in range(n)]
    
    for group_idx in range(task.group_count):
        group_images = await generate_single_group(group_idx)
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image(
    task: StudioTask,
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-max",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用千问文生图模型生成（max/plus 共用）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image import (
        QwenImageService, QWEN_IMAGE_MAX_MODEL_INFO, QWEN_IMAGE_PLUS_MODEL_INFO
    )
    
    model_info = QWEN_IMAGE_MAX_MODEL_INFO if model_name == "qwen-image-max" else QWEN_IMAGE_PLUS_MODEL_INFO
    service = QwenImageService(model_info)
    service.configure(api_key, base_url)
    
    all_images = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []
    
    async def generate_single(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                negative_prompt=task.negative_prompt or "",
                size=size or "1664*928",
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
            if rid:
                collected_request_ids.append(rid)
            
            final_urls = []
            for url in urls:
                if oss_service.is_enabled():
                    try:
                        import httpx as _httpx
                        async with _httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                success, oss_url = oss_service.upload_from_bytes(
                                    resp.content, "image", "png", task.project_id
                                )
                                if success:
                                    final_urls.append(oss_url)
                                    continue
                    except Exception as e:
                        logger.warning(f"OSS 上传失败，使用原始 URL: {e}")
                final_urls.append(url)

            return [StudioTaskImage(
                group_index=group_index,
                url=u,
                prompt_used=task.prompt
            ) for u in final_urls]
        except Exception as e:
            import traceback
            logger.error(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [StudioTaskImage(
                group_index=group_index,
                url=None,
                prompt_used=task.prompt
            )]
    
    group_tasks = [generate_single(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)
    
    for group_images in results:
        all_images.extend(group_images)
    
    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


async def generate_with_qwen_image_2(
    task: StudioTask,
    ref_urls: List[str],
    api_key: str,
    base_url: str = "",
    model_name: str = "qwen-image-2.0-pro",
    size: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
) -> Tuple[List[StudioTaskImage], List[str]]:
    """使用千问图像 2.0 模型生成（文生图 + 图像编辑融合）

    Returns:
        (images, request_ids)
    """
    from app.models_registry.image.qwen_image_2 import (
        QwenImage2Service, QWEN_IMAGE_2_PRO_MODEL_INFO, QWEN_IMAGE_2_MODEL_INFO
    )

    model_info = (
        QWEN_IMAGE_2_PRO_MODEL_INFO
        if model_name == "qwen-image-2.0-pro"
        else QWEN_IMAGE_2_MODEL_INFO
    )
    service = QwenImage2Service(model_info)
    service.configure(api_key, base_url)

    n = task.n or 1
    if n > 6:
        n = 6

    all_images: List[StudioTaskImage] = []
    group_errors: List[str] = []
    collected_request_ids: List[str] = []

    images_input = ref_urls if ref_urls else None

    async def generate_single(group_index: int) -> List[StudioTaskImage]:
        try:
            urls, rid = await service.generate(
                prompt=task.prompt,
                images=images_input,
                negative_prompt=task.negative_prompt or "",
                n=n,
                size=size or None,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
            )
            if rid:
                collected_request_ids.append(rid)

            final_urls: list[str] = []
            for url in urls:
                if oss_service.is_enabled():
                    try:
                        import httpx as _httpx
                        async with _httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                success, oss_url = oss_service.upload_from_bytes(
                                    resp.content, "image", "png", task.project_id
                                )
                                if success:
                                    final_urls.append(oss_url)
                                    continue
                    except Exception as e:
                        logger.warning(f"OSS 上传失败，使用原始 URL: {e}")
                final_urls.append(url)

            return [
                StudioTaskImage(
                    group_index=group_index, url=u, prompt_used=task.prompt
                )
                for u in final_urls
            ]
        except Exception as e:
            import traceback
            logger.error(f"{model_name} 生成失败: {e}")
            traceback.print_exc()
            group_errors.append(str(e))
            return [
                StudioTaskImage(
                    group_index=group_index, url=None, prompt_used=task.prompt
                )
            ]

    group_tasks = [generate_single(i) for i in range(task.group_count)]
    results = await asyncio.gather(*group_tasks)

    for group_images in results:
        all_images.extend(group_images)

    if group_errors:
        task._group_errors = group_errors
    return all_images, collected_request_ids


@router.post("/{task_id}/save-to-gallery")
async def save_task_images_to_gallery(task_id: str, request: SaveToGalleryRequest):
    """将任务中的图片保存到图库"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    saved_images = []
    for image in task.images:
        if image.id in request.image_ids and image.url:
            if image.storage_source != "oss" and image.storage_source in {"local_fallback", "local_expired"}:
                raise HTTPException(
                    status_code=409,
                    detail="所选图片仍处于本地回退状态，请先重传到 OSS 后再保存到图库",
                )
            gallery_image = GalleryImage(
                project_id=task.project_id,
                name=f"{task.name} - 第{image.group_index + 1}组",
                description=task.description,
                url=image.url,
                prompt_used=image.prompt_used,
                source="studio",
                task_id=task_id
            )
            storage_service.save_gallery_image(gallery_image)
            saved_images.append(gallery_image)
            
            # 标记为已选中
            image.is_selected = True
    
    storage_service.save_studio_task(task)
    return {"saved_images": saved_images}


@router.delete("/{task_id}")
async def delete_studio_task(task_id: str):
    """删除任务"""
    task = storage_service.get_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    _cleanup_task_local_assets(task)
    storage_service.delete_studio_task(task_id)
    return {"message": "任务已删除"}


@router.delete("/project/{project_id}/all")
async def delete_all_studio_tasks(project_id: str):
    """删除项目所有任务"""
    tasks = storage_service.get_studio_tasks_by_project(project_id)
    for task in tasks:
        _cleanup_task_local_assets(task)
        storage_service.delete_studio_task(task.id)
    return {"message": f"已删除 {len(tasks)} 个任务"}


@router.get("/models/available")
async def get_available_models():
    """获取可用的图片工作室模型列表
    
    返回支持的模型：
    - 图生图模型：wan2.5-i2i-preview, qwen-image-edit-plus, qwen-image-edit-max
    - 文生图模型：wan2.6-t2i, wan2.5-t2i-preview
    """
    from app.models_registry import registry, ModelType
    from app.config import IMAGE_MODELS
    
    result = {}
    
    # 获取所有图生图模型（从 registry）
    i2i_models = registry.list_models(ModelType.IMAGE_TO_IMAGE)
    for model in i2i_models:
        result[model.id] = {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "description": model.description,
            "model_type": "image_to_image",
            "capabilities": model.capabilities.model_dump() if model.capabilities else {},
            "parameters": [p.model_dump() for p in model.parameters] if model.parameters else [],
            "common_sizes": model.get_common_sizes_for_frontend(),
            "supported_task_kinds": IMAGE_TASK_KIND_SUPPORT.get(model.id, ["image_edit"]),
            "size_ui_mode": _get_image_size_ui_mode(model.id),
        }
    
    # 获取 registry 中的文生图模型
    t2i_models = registry.list_models(ModelType.TEXT_TO_IMAGE)
    for model in t2i_models:
        result[model.id] = {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "description": model.description,
            "model_type": "text_to_image",
            "capabilities": model.capabilities.model_dump() if model.capabilities else {},
            "parameters": [p.model_dump() for p in model.parameters] if model.parameters else [],
            "common_sizes": model.get_common_sizes_for_frontend(),
            "supported_task_kinds": IMAGE_TASK_KIND_SUPPORT.get(model.id, ["text_to_image"]),
            "size_ui_mode": _get_image_size_ui_mode(model.id),
        }
    
    # 添加文生图模型（从 IMAGE_MODELS 配置，兼容旧代码）
    for model_id, model_info in IMAGE_MODELS.items():
        if model_id in result:
            continue
        # 判断模型类型
        if model_info.get("supports_reference_images"):
            model_type = "image_generation"  # wan2.6-image 支持参考图和文生图
        else:
            model_type = "text_to_image"
        
        result[model_id] = {
            "id": model_id,
            "name": model_info.get("name", model_id),
            "provider": _get_image_model_provider(model_id),
            "description": model_info.get("description", ""),
            "model_type": model_type,
            "capabilities": {
                "supports_prompt_extend": model_info.get("supports_prompt_extend", True),
                "supports_watermark": model_info.get("supports_watermark", True),
                "supports_seed": model_info.get("supports_seed", True),
                "supports_negative_prompt": model_info.get("supports_negative_prompt", True),
                "max_n": model_info.get("max_n", 4),
                "supports_reference_images": model_info.get("supports_reference_images", False),
                "supports_interleave": model_info.get("supports_interleave", False),
                "max_reference_images": model_info.get("max_reference_images", 0),
            },
            "parameters": [],
            "common_sizes": model_info.get("common_sizes", []),
            "supported_task_kinds": IMAGE_TASK_KIND_SUPPORT.get(model_id, ["text_to_image"]),
            "size_ui_mode": _get_image_size_ui_mode(model_id),
        }
    
    return {"models": result}
