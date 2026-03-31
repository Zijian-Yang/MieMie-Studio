"""
视频工作室 API 路由
支持六种任务类型：
1. 图生视频（image_to_video）：基于首帧图生成视频
2. 参考生视频（reference_to_video）：基于参考视频/图片生成新视频
3. 文生视频（text_to_video）：基于文本提示词生成视频
4. 首尾帧生视频（keyframe_to_video）：基于首帧和尾帧图片生成平滑过渡视频
5. 视频重绘（video_repainting）：基于源视频重绘新视频
6. 局部编辑（video_edit）：基于首帧Mask编辑视频局部区域
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import uuid
from copy import deepcopy
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.media import VideoStudioTask
from app.models.gallery import GalleryImage
from app.services.storage import storage_service, get_current_user_id, set_current_user
from app.services.dashscope.image_to_video import ImageToVideoService
from app.services.dashscope.reference_to_video import ReferenceToVideoService
from app.services.dashscope.text_to_video import TextToVideoService
from app.services.dashscope.keyframe_to_video import KeyframeToVideoService
from app.services.dashscope.digital_human import DigitalHumanService
from app.services.dashscope.vace_video_edit import VaceVideoEditService
from app.services.video_adapters import (
    NormalizedVideoTaskRequest,
    VideoSubmitResult,
    get_video_adapter,
    infer_provider,
)
from app.services.video_capabilities import get_video_capabilities, LEGACY_TASK_KIND_MAP
from app.services.oss import oss_service
from app.config import set_user_config_dir, get_user_config_dir, get_provider_key_profile

logger = logging.getLogger(__name__)

router = APIRouter()


class VideoStudioTaskCreateRequest(BaseModel):
    """创建视频生成任务请求
    
    支持六种任务类型：
    1. image_to_video（图生视频）：使用 first_frame_url
    2. reference_to_video（参考生视频）：使用 reference_video_urls（支持视频和图片，总数≤5）
    3. text_to_video（文生视频）：使用 prompt 生成视频
    4. keyframe_to_video（首尾帧生视频）：使用 first_frame_url 和 last_frame_url
    5. video_repainting（视频重绘）：使用 source_video_url，可选 reference_image_url
    6. video_edit（局部编辑）：使用 source_video_url + mask_image_url，可选 reference_image_url
    
    图生视频参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5/2.6 支持 480P/720P/1080P（默认1080P）
    - duration: 视频时长，wan2.6 支持 5/10/15 秒，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - audio: 自动配音（仅 wan2.5/2.6 支持），默认 True
    - audio_url: 自定义音频URL（传入时 audio 参数无效）
    - seed: 随机种子，范围 [0, 2147483647]
    - shot_type: 镜头类型（仅 wan2.6 支持），single/multi
    
    参考生视频参数说明（wan2.6-r2v）：
    - size: 分辨率（宽*高格式，如 1920*1080），默认1080P 16:9
    - duration: 视频时长，2-10秒整数
    - shot_type: 镜头类型，single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    
    文生视频参数说明（wan2.6-t2v）：
    - size: 分辨率（宽*高格式，如 1920*1080），720P/1080P档位
    - duration: 视频时长，wan2.6支持5/10/15秒，wan2.5支持5/10秒，其他固定5秒
    - t2v_prompt_extend: 智能改写，默认 True
    - shot_type: 镜头类型（仅wan2.6支持），single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    - auto_audio: 是否自动配音（仅wan2.5及以上支持），默认True
    - audio_url: 自定义音频URL
    
    首尾帧生视频参数说明（wan2.2-kf2v-flash）：
    - first_frame_url: 首帧图URL（必选）
    - last_frame_url: 尾帧图URL（必选）
    - prompt: 提示词（可选，最多800字符）
    - resolution: 分辨率档位，480P/720P/1080P（默认720P）
    - duration: 固定5秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 是否添加水印，默认 False
    - seed: 随机种子
    """
    project_id: str
    name: str = ""

    # 任务类型: image_to_video, reference_to_video, text_to_video, keyframe_to_video, video_repainting, video_edit
    task_type: str = "image_to_video"
    task_kind: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    narrative_mode: Optional[str] = None
    input_assets: Optional[Dict[str, Any]] = None
    normalized_params: Optional[Dict[str, Any]] = None

    # 图生视频参数
    mode: str = "first_frame"  # first_frame 或 first_last_frame
    first_frame_url: Optional[str] = None  # 首帧图URL
    last_frame_url: Optional[str] = None  # 尾帧图URL（首尾帧模式）
    audio_url: Optional[str] = None  # 自定义音频URL
    
    # 参考生视频参数（支持视频和图片，总数≤5）
    reference_video_urls: List[str] = []  # 参考素材URL列表（视频+图片）

    # VACE 视频编辑参数
    source_video_url: Optional[str] = None
    source_video_preview_url: Optional[str] = None
    reference_image_url: Optional[str] = None
    mask_image_url: Optional[str] = None
    mask_frame_id: Optional[int] = 1

    # 通用参数
    prompt: str = ""
    negative_prompt: str = ""
    model: str = "wan2.5-i2v-preview"
    duration: int = 5
    watermark: bool = False  # 水印
    seed: Optional[int] = None  # 随机种子
    shot_type: Optional[str] = None  # 镜头类型
    auto_audio: bool = True  # 自动配音
    
    # 图生视频专用
    resolution: str = "1080P"  # 默认1080P
    prompt_extend: bool = True  # 智能改写

    # 参考生视频专用
    size: Optional[str] = None  # 分辨率（宽*高格式）

    # 文生视频专用
    t2v_prompt_extend: bool = True  # 文生视频的智能改写，默认开启

    # VACE 专用
    control_condition: Optional[str] = None
    strength: Optional[float] = None
    mask_type: Optional[str] = None
    expand_ratio: Optional[float] = None
    expand_mode: Optional[str] = None

    group_count: int = 1


class VideoStudioTaskUpdateRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    selected_video_url: Optional[str] = None
    task_type: Optional[str] = None  # 任务类型: image_to_video / reference_to_video / text_to_video
    task_kind: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    narrative_mode: Optional[str] = None
    input_assets: Optional[Dict[str, Any]] = None
    normalized_params: Optional[Dict[str, Any]] = None
    # 支持编辑的字段
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    resolution: Optional[str] = None
    duration: Optional[int] = None
    prompt_extend: Optional[bool] = None
    watermark: Optional[bool] = None
    seed: Optional[int] = None
    auto_audio: Optional[bool] = None
    shot_type: Optional[str] = None  # 镜头类型
    first_frame_url: Optional[str] = None
    audio_url: Optional[str] = None
    reference_video_urls: Optional[List[str]] = None  # 参考素材URL列表（视频+图片）
    size: Optional[str] = None  # 参考生视频/文生视频分辨率
    t2v_prompt_extend: Optional[bool] = None  # 文生视频的智能改写
    group_count: Optional[int] = None  # 生成组数
    source_video_url: Optional[str] = None
    source_video_preview_url: Optional[str] = None
    reference_image_url: Optional[str] = None
    mask_image_url: Optional[str] = None
    mask_frame_id: Optional[int] = None
    control_condition: Optional[str] = None
    strength: Optional[float] = None
    mask_type: Optional[str] = None
    expand_ratio: Optional[float] = None
    expand_mode: Optional[str] = None


class PrepareSourceVideoRequest(BaseModel):
    """准备源视频首帧与元数据"""
    project_id: str
    video_url: str


VACE_REPAINTING_CONTROL_CONDITIONS = {"posebodyface", "posebody", "depth", "scribble"}
VACE_EDIT_CONTROL_CONDITIONS = {"posebodyface", "depth"}
VACE_EDIT_MASK_TYPES = {"tracking", "fixed"}
VACE_EDIT_EXPAND_MODES = {"hull", "bbox", "original"}
VACE_EDIT_SIZES = {"1280*720", "720*1280", "960*960", "832*1088", "1088*832"}
VACE_MODEL_NAME = "wanx2.1-vace-plus"
VACE_MASK_FRAME_ID = 1
TASK_KIND_TO_LEGACY_TASK_TYPE = {
    "image_to_video": "image_to_video",
    "reference_to_video": "reference_to_video",
    "text_to_video": "text_to_video",
    "keyframe_to_video": "keyframe_to_video",
    "video_repainting": "video_repainting",
    "video_edit_local": "video_edit",
    "video_edit_global": "video_edit_global",
}


def _resolve_task_kind(task_type: Optional[str], task_kind: Optional[str]) -> str:
    if task_kind:
        return task_kind
    return LEGACY_TASK_KIND_MAP.get(task_type or "image_to_video", task_type or "image_to_video")


def _default_model_for_task_kind(task_kind: str) -> str:
    defaults = {
        "image_to_video": "wan2.6-i2v-flash",
        "reference_to_video": "wan2.6-r2v-flash",
        "text_to_video": "wan2.6-t2v",
        "keyframe_to_video": "wan2.2-kf2v-flash",
        "video_repainting": VACE_MODEL_NAME,
        "video_edit_local": VACE_MODEL_NAME,
        "video_edit_global": "kling/kling-v3-omni-video-generation",
    }
    return defaults.get(task_kind, "wan2.6-i2v-flash")


def _split_reference_assets(urls: List[str]) -> tuple[List[str], List[str]]:
    image_urls: List[str] = []
    video_urls: List[str] = []
    for url in urls:
        lowered = url.lower()
        if any(ext in lowered for ext in [".mp4", ".mov", ".avi", ".m4v", ".webm"]):
            video_urls.append(url)
        else:
            image_urls.append(url)
    return image_urls, video_urls


def _normalize_request(request: VideoStudioTaskCreateRequest) -> NormalizedVideoTaskRequest:
    task_kind = _resolve_task_kind(request.task_type, request.task_kind)
    legacy_task_type = TASK_KIND_TO_LEGACY_TASK_TYPE.get(task_kind, task_kind)
    model_id = request.model_id or request.model or _default_model_for_task_kind(task_kind)
    provider = request.provider or infer_provider(model_id, task_kind)
    key_profile = get_provider_key_profile(provider)

    if request.input_assets is not None:
        input_assets = deepcopy(request.input_assets)
    else:
        reference_images, reference_videos = _split_reference_assets(request.reference_video_urls or [])
        input_assets: Dict[str, Any] = {
            "first_frame": [request.first_frame_url] if request.first_frame_url else [],
            "last_frame": [request.last_frame_url] if request.last_frame_url else [],
            "audio": [request.audio_url] if request.audio_url else [],
            "reference_images": reference_images + ([request.reference_image_url] if request.reference_image_url else []),
            "reference_videos": reference_videos,
            "source_video": [request.source_video_url] if request.source_video_url else [],
            "base_video": [request.source_video_url] if request.source_video_url and task_kind == "video_edit_global" else [],
            "mask_image": [request.mask_image_url] if request.mask_image_url else [],
        }

    normalized_params = deepcopy(request.normalized_params or {})
    normalized_params.setdefault("resolution", request.resolution)
    normalized_params.setdefault("size", request.size)
    normalized_params.setdefault("duration", request.duration)
    normalized_params.setdefault("prompt_extend", request.prompt_extend if task_kind != "text_to_video" else request.t2v_prompt_extend)
    normalized_params.setdefault("watermark", request.watermark)
    normalized_params.setdefault("seed", request.seed)
    normalized_params.setdefault("audio", request.auto_audio)
    normalized_params.setdefault("shot_type", request.shot_type)
    normalized_params.setdefault("control_condition", request.control_condition)
    normalized_params.setdefault("strength", request.strength)
    normalized_params.setdefault("mask_type", request.mask_type)
    normalized_params.setdefault("expand_ratio", request.expand_ratio)
    normalized_params.setdefault("expand_mode", request.expand_mode)
    normalized_params.setdefault("mask_frame_id", request.mask_frame_id or VACE_MASK_FRAME_ID)

    if task_kind == "video_edit_global":
        input_assets.setdefault("base_video", input_assets.get("base_video") or input_assets.get("source_video") or [])
    if task_kind in {"video_edit_local", "video_repainting"}:
        input_assets.setdefault("source_video", input_assets.get("source_video") or [])

    return NormalizedVideoTaskRequest(
        project_id=request.project_id,
        task_kind=task_kind,
        provider=provider,
        key_profile=key_profile,
        model_id=model_id,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        narrative_mode=request.narrative_mode or request.shot_type or "single",
        input_assets=input_assets,
        normalized_params=normalized_params,
    )


def _apply_normalized_fields_to_task(task: VideoStudioTask, normalized: NormalizedVideoTaskRequest) -> None:
    params = normalized.normalized_params
    assets = normalized.input_assets
    task.task_kind = normalized.task_kind
    task.task_type = TASK_KIND_TO_LEGACY_TASK_TYPE.get(normalized.task_kind, normalized.task_kind)
    task.provider = normalized.provider
    task.key_profile = normalized.key_profile
    task.model_id = normalized.model_id
    task.model = normalized.model_id
    task.narrative_mode = normalized.narrative_mode
    task.input_assets = deepcopy(assets)
    task.normalized_params = deepcopy(params)

    task.first_frame_url = (assets.get("first_frame") or [None])[0]
    task.last_frame_url = (assets.get("last_frame") or [None])[0]
    task.audio_url = (assets.get("audio") or [None])[0]
    task.reference_video_urls = list(assets.get("reference_videos") or []) + list(assets.get("reference_images") or [])
    source_video = assets.get("source_video") or assets.get("base_video") or []
    task.source_video_url = source_video[0] if source_video else None
    task.reference_image_url = (assets.get("reference_images") or [None])[0]
    task.mask_image_url = (assets.get("mask_image") or [None])[0]
    task.mask_frame_id = params.get("mask_frame_id") if normalized.task_kind == "video_edit_local" else None
    task.prompt = normalized.prompt
    task.negative_prompt = normalized.negative_prompt
    task.duration = int(params.get("duration") or task.duration)
    task.watermark = bool(params.get("watermark", task.watermark))
    task.seed = params.get("seed")
    task.auto_audio = bool(params.get("audio", task.auto_audio))
    task.prompt_extend = bool(params.get("prompt_extend", task.prompt_extend))
    task.t2v_prompt_extend = bool(params.get("prompt_extend", task.t2v_prompt_extend))
    task.shot_type = params.get("shot_type")
    task.resolution = params.get("resolution") or task.resolution
    task.size = params.get("size") or task.size
    task.control_condition = params.get("control_condition")
    task.strength = params.get("strength")
    task.mask_type = params.get("mask_type")
    task.expand_ratio = params.get("expand_ratio")
    task.expand_mode = params.get("expand_mode")


def _normalized_request_from_task(task: VideoStudioTask) -> NormalizedVideoTaskRequest:
    raw_task_type = getattr(task, "task_type", "image_to_video")
    raw_task_kind = getattr(task, "task_kind", None)
    if raw_task_kind and not (raw_task_kind == "image_to_video" and raw_task_type != "image_to_video"):
        resolved_task_kind = raw_task_kind
    else:
        resolved_task_kind = _resolve_task_kind(raw_task_type, None)
    resolved_model_id = getattr(task, "model_id", None) or getattr(task, "model", None) or _default_model_for_task_kind(resolved_task_kind)
    resolved_provider = getattr(task, "provider", None) or infer_provider(resolved_model_id, resolved_task_kind)
    resolved_key_profile = getattr(task, "key_profile", None) or get_provider_key_profile(resolved_provider)
    input_assets = deepcopy(getattr(task, "input_assets", {}) or {})
    if not input_assets:
        reference_images, reference_videos = _split_reference_assets(getattr(task, "reference_video_urls", []) or [])
        input_assets = {
            "first_frame": [task.first_frame_url] if task.first_frame_url else [],
            "last_frame": [task.last_frame_url] if task.last_frame_url else [],
            "audio": [task.audio_url] if task.audio_url else [],
            "reference_images": reference_images + ([task.reference_image_url] if task.reference_image_url else []),
            "reference_videos": reference_videos,
            "source_video": [task.source_video_url] if task.source_video_url else [],
            "base_video": [task.source_video_url] if resolved_task_kind == "video_edit_global" and task.source_video_url else [],
            "mask_image": [task.mask_image_url] if task.mask_image_url else [],
        }
    normalized_params = deepcopy(getattr(task, "normalized_params", {}) or {})
    if not normalized_params:
        normalized_size = task.size
        if resolved_task_kind == "video_edit_local" and normalized_size not in VACE_EDIT_SIZES:
            normalized_size = None
        normalized_params = {
            "resolution": task.resolution,
            "size": normalized_size,
            "duration": task.duration,
            "prompt_extend": task.prompt_extend if getattr(task, "task_type", "") != "text_to_video" else getattr(task, "t2v_prompt_extend", True),
            "watermark": task.watermark,
            "seed": task.seed,
            "audio": task.auto_audio,
            "shot_type": task.shot_type,
            "control_condition": task.control_condition,
            "strength": task.strength,
            "mask_type": task.mask_type,
            "expand_ratio": task.expand_ratio,
            "expand_mode": task.expand_mode,
            "mask_frame_id": task.mask_frame_id or VACE_MASK_FRAME_ID,
        }
    return NormalizedVideoTaskRequest(
        project_id=task.project_id,
        task_kind=resolved_task_kind,
        provider=resolved_provider,
        key_profile=resolved_key_profile,
        model_id=resolved_model_id,
        prompt=task.prompt,
        negative_prompt=task.negative_prompt,
        narrative_mode=getattr(task, "narrative_mode", "single"),
        input_assets=input_assets,
        normalized_params=normalized_params,
    )


def _merge_update_request_into_normalized_request(
    task: VideoStudioTask,
    request: VideoStudioTaskUpdateRequest,
) -> NormalizedVideoTaskRequest:
    normalized = _normalized_request_from_task(task)
    provided_fields = request.model_fields_set

    if "task_kind" in provided_fields or "task_type" in provided_fields:
        normalized.task_kind = _resolve_task_kind(
            request.task_type if "task_type" in provided_fields else task.task_type,
            request.task_kind if "task_kind" in provided_fields else normalized.task_kind,
        )

    if "model_id" in provided_fields and request.model_id is not None:
        normalized.model_id = request.model_id
    elif "model" in provided_fields and request.model is not None:
        normalized.model_id = request.model

    if "provider" in provided_fields and request.provider is not None:
        normalized.provider = request.provider
    else:
        normalized.provider = infer_provider(normalized.model_id, normalized.task_kind)
    if normalized.provider == getattr(task, "provider", None):
        normalized.key_profile = getattr(task, "key_profile", None) or get_provider_key_profile(normalized.provider)
    else:
        normalized.key_profile = get_provider_key_profile(normalized.provider)

    if "narrative_mode" in provided_fields and request.narrative_mode is not None:
        normalized.narrative_mode = request.narrative_mode
    elif "shot_type" in provided_fields and request.shot_type is not None:
        normalized.narrative_mode = request.shot_type

    if "prompt" in provided_fields and request.prompt is not None:
        normalized.prompt = request.prompt
    if "negative_prompt" in provided_fields and request.negative_prompt is not None:
        normalized.negative_prompt = request.negative_prompt

    if "input_assets" in provided_fields and request.input_assets is not None:
        normalized.input_assets = deepcopy(request.input_assets)
    else:
        assets = deepcopy(normalized.input_assets)
        if "first_frame_url" in provided_fields:
            assets["first_frame"] = [request.first_frame_url] if request.first_frame_url else []
        if "audio_url" in provided_fields:
            assets["audio"] = [request.audio_url] if request.audio_url else []
        if "reference_video_urls" in provided_fields:
            reference_images, reference_videos = _split_reference_assets(request.reference_video_urls or [])
            assets["reference_images"] = reference_images
            assets["reference_videos"] = reference_videos
        if "source_video_url" in provided_fields:
            assets["source_video"] = [request.source_video_url] if request.source_video_url else []
            if normalized.task_kind == "video_edit_global":
                assets["base_video"] = [request.source_video_url] if request.source_video_url else []
        if "reference_image_url" in provided_fields:
            assets["reference_images"] = [request.reference_image_url] if request.reference_image_url else []
        if "mask_image_url" in provided_fields:
            assets["mask_image"] = [request.mask_image_url] if request.mask_image_url else []
        normalized.input_assets = assets

    if "normalized_params" in provided_fields and request.normalized_params is not None:
        normalized.normalized_params = deepcopy(request.normalized_params)
    else:
        params = deepcopy(normalized.normalized_params)
        if "resolution" in provided_fields:
            params["resolution"] = request.resolution
        if "duration" in provided_fields:
            params["duration"] = request.duration
        if "prompt_extend" in provided_fields:
            params["prompt_extend"] = request.prompt_extend
        if "watermark" in provided_fields:
            params["watermark"] = request.watermark
        if "seed" in provided_fields:
            params["seed"] = request.seed
        if "auto_audio" in provided_fields:
            params["audio"] = request.auto_audio
        if "shot_type" in provided_fields:
            params["shot_type"] = request.shot_type
        if "size" in provided_fields:
            params["size"] = request.size
        if "t2v_prompt_extend" in provided_fields:
            params["prompt_extend"] = request.t2v_prompt_extend
        if "control_condition" in provided_fields:
            params["control_condition"] = request.control_condition
        if "strength" in provided_fields:
            params["strength"] = request.strength
        if "mask_type" in provided_fields:
            params["mask_type"] = request.mask_type
        if "expand_ratio" in provided_fields:
            params["expand_ratio"] = request.expand_ratio
        if "expand_mode" in provided_fields:
            params["expand_mode"] = request.expand_mode
        if "mask_frame_id" in provided_fields:
            params["mask_frame_id"] = request.mask_frame_id
        normalized.normalized_params = params

    return normalized


def _get_vace_task_duration(source_metadata: dict) -> int:
    duration = float(source_metadata.get("duration") or 5)
    duration = min(max(duration, 1.0), 5.0)
    return max(1, int(round(duration)))


async def _validate_vace_task_request(request: VideoStudioTaskCreateRequest) -> dict:
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="VACE任务需要启用OSS，请先在设置中配置并启用OSS")

    if not request.prompt:
        raise HTTPException(status_code=400, detail="请输入提示词")
    if len(request.prompt) > 800:
        raise HTTPException(status_code=400, detail="提示词长度不能超过800字符")
    if request.seed is not None and not (0 <= request.seed <= 2147483647):
        raise HTTPException(status_code=400, detail="随机种子必须在0到2147483647之间")

    service = VaceVideoEditService()

    if not request.source_video_url:
        raise HTTPException(status_code=400, detail="请选择源视频")
    try:
        source_metadata = await service.validate_source_video(request.source_video_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.reference_image_url:
        try:
            await service.validate_reference_image(request.reference_image_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    requested_model = request.model
    if requested_model in {"", "wan2.5-i2v-preview"}:
        requested_model = VACE_MODEL_NAME

    if request.task_type == "video_repainting":
        if requested_model != VACE_MODEL_NAME:
            raise HTTPException(status_code=400, detail="视频重绘仅支持 wanx2.1-vace-plus")
        if request.control_condition not in VACE_REPAINTING_CONTROL_CONDITIONS:
            raise HTTPException(status_code=400, detail="视频重绘的控制条件不合法")
        if request.strength is not None and not (0.0 <= request.strength <= 1.0):
            raise HTTPException(status_code=400, detail="视频重绘强度必须在0到1之间")

    elif request.task_type == "video_edit":
        if requested_model != VACE_MODEL_NAME:
            raise HTTPException(status_code=400, detail="局部编辑仅支持 wanx2.1-vace-plus")
        if not request.mask_image_url:
            raise HTTPException(status_code=400, detail="局部编辑任务需要上传Mask")
        if request.mask_frame_id not in (None, VACE_MASK_FRAME_ID):
            raise HTTPException(status_code=400, detail="当前仅支持首帧Mask，mask_frame_id固定为1")
        if request.control_condition and request.control_condition not in VACE_EDIT_CONTROL_CONDITIONS:
            raise HTTPException(status_code=400, detail="局部编辑的控制条件不合法")

        mask_type = request.mask_type or "tracking"
        if mask_type not in VACE_EDIT_MASK_TYPES:
            raise HTTPException(status_code=400, detail="局部编辑的mask_type不合法")
        if request.size and request.size not in VACE_EDIT_SIZES:
            raise HTTPException(status_code=400, detail="局部编辑的输出分辨率不合法")

        if mask_type == "tracking":
            if request.expand_ratio is not None and not (0.0 <= request.expand_ratio <= 1.0):
                raise HTTPException(status_code=400, detail="expand_ratio必须在0到1之间")
            if request.expand_mode and request.expand_mode not in VACE_EDIT_EXPAND_MODES:
                raise HTTPException(status_code=400, detail="expand_mode不合法")
        else:
            if request.expand_ratio is not None:
                raise HTTPException(status_code=400, detail="fixed模式下不支持expand_ratio")
            if request.expand_mode is not None:
                raise HTTPException(status_code=400, detail="fixed模式下不支持expand_mode")

        try:
            await service.validate_mask_image(
                request.mask_image_url,
                source_metadata["width"],
                source_metadata["height"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return source_metadata


@router.get("")
async def list_tasks(project_id: str):
    """获取项目所有视频工作室任务"""
    tasks = storage_service.get_video_studio_tasks(project_id)
    return {"tasks": tasks}


@router.get("/capabilities")
async def get_capabilities():
    """获取视频工作室能力 schema"""
    return get_video_capabilities()


@router.post("/prepare-source-video")
async def prepare_source_video(request: PrepareSourceVideoRequest):
    """提取源视频首帧并返回元数据与预览"""
    service = VaceVideoEditService()
    try:
        result = await service.prepare_source_video(request.project_id, request.video_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"[视频工作室] 准备源视频失败: {exc}")
        raise HTTPException(status_code=500, detail=f"准备源视频失败: {str(exc)}") from exc
    return result


@router.post("/upload-mask")
async def upload_mask(
    project_id: str = Form(...),
    source_video_url: str = Form(...),
    mask_file: UploadFile = File(...),
):
    """上传并规范化局部编辑Mask"""
    service = VaceVideoEditService()
    try:
        mask_bytes = await mask_file.read()
        result = await service.upload_mask(project_id, source_video_url, mask_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"[视频工作室] 上传Mask失败: {exc}")
        raise HTTPException(status_code=500, detail=f"上传Mask失败: {str(exc)}") from exc
    return result


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取单个任务"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("")
async def create_task(request: VideoStudioTaskCreateRequest):
    """创建并启动视频生成任务（兼容旧 task_type 与新 task_kind 协议）"""
    normalized = _normalize_request(request)
    adapter = get_video_adapter(normalized.provider)
    try:
        await adapter.validate(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_duration = int(normalized.normalized_params.get("duration") or request.duration or 5)
    if normalized.task_kind in {"video_repainting", "video_edit_local"}:
        source_video = (normalized.input_assets.get("source_video") or [None])[0]
        source_metadata = await VaceVideoEditService().validate_source_video(source_video)
        task_duration = _get_vace_task_duration(source_metadata)
        normalized.normalized_params["duration"] = task_duration

    task = VideoStudioTask(
        project_id=request.project_id,
        name=request.name or f"视频任务 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        task_type=TASK_KIND_TO_LEGACY_TASK_TYPE.get(normalized.task_kind, normalized.task_kind),
        task_kind=normalized.task_kind,
        provider=normalized.provider,
        key_profile=normalized.key_profile,
        model_id=normalized.model_id,
        narrative_mode=normalized.narrative_mode,
        input_assets=deepcopy(normalized.input_assets),
        normalized_params=deepcopy(normalized.normalized_params),
        prompt=normalized.prompt,
        negative_prompt=normalized.negative_prompt,
        model=normalized.model_id,
        duration=task_duration,
        group_count=request.group_count,
        status="processing",
    )
    _apply_normalized_fields_to_task(task, normalized)
    if normalized.task_kind in {"video_repainting", "video_edit_local"}:
        task.source_video_preview_url = request.source_video_preview_url

    storage_service.save_video_studio_task(task)

    # 捕获用户上下文（后台任务需要）
    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()

    # 后台执行 API 调用，不阻塞请求
    asyncio.create_task(_background_create_video_tasks(task, normalized, user_id, user_config_dir))

    return {"task": task}


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "processing":
        return {"task": task}

    if not task.task_ids:
        return {"task": task}

    normalized = _normalized_request_from_task(task)
    adapter = get_video_adapter(normalized.provider)
    all_succeeded = True
    all_finished = True
    video_urls = []
    provider_meta = deepcopy(task.provider_result_meta or {})

    for api_task_id in task.task_ids:
        result = await adapter.fetch(normalized, api_task_id)
        provider_meta[api_task_id] = {
            "provider": normalized.provider,
            "key_profile": result.key_profile or normalized.key_profile,
            "request_id": result.request_id,
            "usage": result.usage,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "raw_output": result.raw_output,
            "finished_at": datetime.now().isoformat(),
        }
        normalized_status = str(result.status).upper()
        if normalized_status == "SUCCEEDED" and result.video_url:
            video_urls.append(result.video_url)
        elif normalized_status == "FAILED":
            all_succeeded = False
            if result.error_message:
                task.error_message = result.error_message
        elif normalized_status in {"PENDING", "RUNNING", "UNKNOWN"}:
            all_finished = False
        else:
            all_succeeded = False
            task.error_message = result.error_message or f"未知任务状态: {result.status}"
    
    # 更新任务状态
    task.video_urls = video_urls
    task.provider_result_meta = provider_meta
    
    if all_finished:
        if not video_urls and not task.task_ids:
            pass
        elif all_succeeded and video_urls and len(video_urls) == len(task.task_ids):
            task.status = "succeeded"
        else:
            task.status = "failed"
            if not task.error_message:
                failed_count = len(task.task_ids) - len(video_urls)
                task.error_message = f"视频生成失败（{failed_count}/{len(task.task_ids)} 个失败）"
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return {"task": task}


@router.put("/{task_id}")
async def update_task(task_id: str, request: VideoStudioTaskUpdateRequest):
    """更新任务信息"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if request.name is not None:
        task.name = request.name
    if request.selected_video_url is not None:
        task.selected_video_url = request.selected_video_url

    provided_fields = request.model_fields_set
    if "source_video_preview_url" in provided_fields:
        task.source_video_preview_url = request.source_video_preview_url
    if request.group_count is not None:
        task.group_count = request.group_count

    canonical_update_fields = {
        "task_type",
        "task_kind",
        "provider",
        "model_id",
        "model",
        "narrative_mode",
        "input_assets",
        "normalized_params",
        "prompt",
        "negative_prompt",
        "resolution",
        "duration",
        "prompt_extend",
        "watermark",
        "seed",
        "auto_audio",
        "shot_type",
        "first_frame_url",
        "audio_url",
        "reference_video_urls",
        "size",
        "t2v_prompt_extend",
        "source_video_url",
        "reference_image_url",
        "mask_image_url",
        "mask_frame_id",
        "control_condition",
        "strength",
        "mask_type",
        "expand_ratio",
        "expand_mode",
    }
    if canonical_update_fields & provided_fields:
        normalized = _merge_update_request_into_normalized_request(task, request)
        adapter = get_video_adapter(normalized.provider)
        try:
            await adapter.validate(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _apply_normalized_fields_to_task(task, normalized)
    
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)
    
    return task


class VideoMarkerRequest(BaseModel):
    """更新视频标记"""
    video_url: str
    markers: List[str]  # star, flag, check, cross


@router.post("/{task_id}/markers")
async def update_video_markers(task_id: str, request: VideoMarkerRequest):
    """更新任务中某个视频的标记"""
    VALID_MARKERS = {"star", "flag", "check", "cross"}
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if request.video_url not in task.video_urls:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not hasattr(task, 'video_markers') or task.video_markers is None:
        task.video_markers = {}
    task.video_markers[request.video_url] = [m for m in request.markers if m in VALID_MARKERS]
    storage_service.save_video_studio_task(task)
    return {"success": True, "video_markers": task.video_markers}


@router.post("/{task_id}/regenerate")
async def regenerate_task(task_id: str):
    """重新生成任务视频"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    normalized = _normalized_request_from_task(task)
    adapter = get_video_adapter(normalized.provider)
    try:
        await adapter.validate(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 捕获用户上下文
    user_id = get_current_user_id()
    user_config_dir = get_user_config_dir()

    # 重置任务状态
    task.status = "processing"
    task.video_urls = []
    task.error_message = None
    task.task_ids = []
    task.request_ids = []
    task.provider_result_meta = {}
    task.updated_at = datetime.now()
    storage_service.save_video_studio_task(task)

    asyncio.create_task(_background_create_video_tasks(task, normalized, user_id, user_config_dir))

    return {"task": task}


@router.post("/{task_id}/save-to-library")
async def save_to_library(task_id: str, video_url: str, name: str = ""):
    """保存视频到视频库"""
    from app.models.media import VideoItem
    
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if video_url not in task.video_urls:
        raise HTTPException(status_code=400, detail="视频URL不属于此任务")
    
    # 创建视频库记录
    video = VideoItem(
        project_id=task.project_id,
        name=name or f"工作室视频 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        url=video_url,
        file_type="mp4",
        duration=task.duration
    )
    
    storage_service.save_video_item(video)
    
    return {"message": "已保存到视频库", "video": video}


class ExtractLastFrameRequest(BaseModel):
    """提取视频尾帧请求"""
    video_url: str
    name: Optional[str] = None


@router.post("/{task_id}/extract-last-frame")
async def extract_last_frame(task_id: str, request: ExtractLastFrameRequest):
    """
    使用 ffmpeg 提取视频工作室任务中某个视频的最后一帧，保存到图库
    """
    if not oss_service.is_enabled():
        raise HTTPException(status_code=400, detail="OSS未启用，请先在设置中配置并启用OSS")

    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if request.video_url not in task.video_urls:
        raise HTTPException(status_code=400, detail="视频URL不属于此任务")

    try:
        image_bytes = await _ffmpeg_extract_last_frame(request.video_url)

        filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        oss_url = oss_service.upload_bytes(image_bytes, f"gallery/{task.project_id}/{filename}")

        image_name = request.name or f"{task.name}_尾帧"
        gallery_image = GalleryImage(
            project_id=task.project_id,
            name=image_name,
            description=f"从视频工作室任务《{task.name}》提取的尾帧",
            url=oss_url,
            source="video_studio",
            tags=["尾帧", "视频提取"],
        )
        storage_service.save_gallery_image(gallery_image)

        return {"message": "尾帧已保存到图库", "image": gallery_image}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[视频尾帧提取] 错误: {e}")
        raise HTTPException(status_code=500, detail=f"提取尾帧失败: {str(e)}")


async def _ffmpeg_extract_last_frame(video_url: str) -> bytes:
    """下载视频并用 ffmpeg 提取最后一帧，返回 JPEG 字节"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(video_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"无法下载视频: HTTP {resp.status_code}")
        video_content = resp.content

    tmp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_output = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_video.write(video_content)
    tmp_video.close()
    tmp_output.close()

    try:
        # 用 ffprobe 获取视频时长
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', tmp_video.name],
            capture_output=True, text=True
        )
        if probe.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {probe.stderr}")
        duration = float(probe.stdout.strip())

        # -ss 定位到末尾前 2s，-update 1 持续覆盖输出，最终文件即为最后一帧
        seek_time = max(0, duration - 2)
        # format=yuvj420p: ffmpeg 8.x MJPEG 编码器要求全范围 YUV
        result = subprocess.run(
            ['ffmpeg', '-ss', str(seek_time), '-i', tmp_video.name,
             '-vf', 'format=yuvj420p',
             '-q:v', '2', '-update', '1',
             '-y', tmp_output.name],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 提取失败: {result.stderr}")

        with open(tmp_output.name, 'rb') as f:
            image_data = f.read()
        if not image_data:
            raise RuntimeError("ffmpeg 未输出任何图像数据")
        return image_data
    finally:
        os.unlink(tmp_video.name)
        os.unlink(tmp_output.name)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    task = storage_service.get_video_studio_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    storage_service.delete_video_studio_task(task_id)
    return {"message": "任务已删除"}


@router.delete("")
async def delete_all_tasks(project_id: str):
    """删除项目所有任务"""
    tasks = storage_service.get_video_studio_tasks(project_id)
    for task in tasks:
        storage_service.delete_video_studio_task(task.id)
    return {"message": f"已删除 {len(tasks)} 个任务"}


# ──────────────────────────────────────
# 后台任务处理（asyncio.create_task 调度）
# ──────────────────────────────────────

async def _background_create_video_tasks(
    task: VideoStudioTask,
    request: NormalizedVideoTaskRequest,
    user_id: Optional[str],
    user_config_dir: Optional[str],
):
    """后台创建视频 API 任务——由 asyncio.create_task 调度，不阻塞请求"""
    # 恢复用户上下文（后台协程运行在不同的上下文中）
    set_current_user(user_id)
    if user_config_dir:
        set_user_config_dir(user_config_dir)

    try:
        task_ids = await _submit_api_tasks(task, request)
        task.task_ids = list(task_ids)
        task.updated_at = datetime.now()
        storage_service.save_video_studio_task(task)
        logger.info(f"[视频工作室] 任务 {task.id} 已提交 {len(task_ids)} 个 API 任务")
    except Exception as e:
        logger.error(f"[视频工作室] 任务 {task.id} 提交失败: {e}")
        task.status = "failed"
        task.error_message = str(e)
        task.updated_at = datetime.now()
        storage_service.save_video_studio_task(task)


async def _submit_api_tasks(
    task: VideoStudioTask,
    request: NormalizedVideoTaskRequest,
) -> list:
    """并发提交所有 group 的 API 任务，返回 task_id 列表"""

    adapter = get_video_adapter(request.provider)

    async def create_one(idx: int) -> VideoSubmitResult:
        return await adapter.submit(request, seed_offset=idx)

    results = list(await asyncio.gather(*[create_one(i) for i in range(task.group_count)]))
    task.request_ids = [result.request_id for result in results if result.request_id]
    if results:
        task.provider_payload_snapshot = results[0].provider_payload
        task.key_profile = results[0].key_profile or request.key_profile
    task.provider_result_meta = {
        result.task_id: {
            "provider": request.provider,
            "key_profile": result.key_profile or request.key_profile,
            "request_id": result.request_id,
            "submitted_at": datetime.now().isoformat(),
        }
        for result in results
    }
    return [result.task_id for result in results]
