"""
视频工作室多厂商适配层

负责：
1. 统一不同厂商的参数校验
2. 构建厂商请求体
3. 提交异步视频生成任务
4. 查询任务状态并统一结果结构
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_config, get_provider_api_key, get_provider_key_profile
from app.services.remote_media_validation import (
    inspect_remote_audio,
    inspect_remote_image,
    inspect_remote_video,
)
from app.services.dashscope.digital_human import DigitalHumanService
from app.services.dashscope.image_to_video import ImageToVideoService
from app.services.dashscope.keyframe_to_video import KeyframeToVideoService
from app.services.dashscope.reference_to_video import ReferenceToVideoService
from app.services.dashscope.text_to_video import TextToVideoService
from app.services.dashscope.vace_video_edit import VaceVideoEditService
from app.services.oss import oss_service


logger = logging.getLogger(__name__)
KLANG_DOC_MAX_PROMPT = 2500
VIDU_DOC_MAX_PROMPT = 5000
SEED_MAX = 2147483647
KLING_MODE_VALUES = {"pro", "std"}
KLING_ASPECT_RATIO_VALUES = {"16:9", "9:16", "1:1"}
VIDU_RESOLUTION_VALUES = {"540P", "720P", "1080P"}
VACE_MASK_FRAME_ID = 1
VACE_REPAINTING_CONTROL_CONDITIONS = {"posebodyface", "posebody", "depth", "scribble"}
VACE_EDIT_CONTROL_CONDITIONS = {"posebodyface", "depth"}
VACE_EDIT_MASK_TYPES = {"tracking", "fixed"}
VACE_EDIT_EXPAND_MODES = {"hull", "bbox", "original"}
VACE_EDIT_SIZES = {"1280*720", "720*1280", "960*960", "832*1088", "1088*832"}
WAN27_I2V_RESOLUTIONS = {"720P", "1080P"}
WAN27_T2V_RESOLUTIONS = {"720P", "1080P"}
WAN27_R2V_RESOLUTIONS = {"720P", "1080P"}
WAN27_VIDEOEDIT_RESOLUTIONS = {"720P", "1080P"}
WAN27_COMMON_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4"}
WAN27_VIDEOEDIT_RATIOS = WAN27_COMMON_RATIOS
WAN27_VIDEOEDIT_AUDIO_SETTINGS = {"auto", "origin"}
WAN27_I2V_MODEL_IDS = {"wan2.7-i2v", "wan2.7-i2v-2026-04-25"}
WAN27_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "BMP", "WEBP"}
WAN27_VIDEO_FORMATS = {"mp4", "mov"}
WAN27_AUDIO_FORMATS = {"wav", "mp3"}

VIDU_COMMON_SIZE_OPTIONS = {
    "540P": {"960*528", "528*960", "720*720", "816*608", "608*816"},
    "720P": {"1280*720", "720*1280", "960*960", "1104*816", "816*1104"},
    "1080P": {"1920*1080", "1080*1920", "1440*1440", "1674*1238", "1238*1674"},
}
VIDU_REFERENCE_SIZE_OPTIONS = {
    "540P": {"960*540", "720*540", "540*540", "540*720", "540*960"},
    "720P": {"1280*720", "960*720", "720*720", "720*960", "720*1280"},
    "1080P": {"1920*1080", "1440*1080", "1080*1080", "1080*1440", "1080*1920"},
}

KLING_IMAGE_FORMATS = {"JPEG", "JPG", "PNG"}
KLING_VIDEO_FORMATS = {"mp4", "mov"}
VIDU_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}
VIDU_VIDEO_FORMATS = {"mp4", "avi", "mov"}
HAPPYHORSE_RESOLUTIONS = {"720P", "1080P"}
HAPPYHORSE_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4"}
HAPPYHORSE_DURATIONS = set(range(3, 16))
HAPPYHORSE_PROMPT_MAX_UNITS = 5000
HAPPYHORSE_PROMPT_CJK_UNIT = 2
HAPPYHORSE_PROMPT_NON_CJK_UNIT = 1
HAPPYHORSE_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}
HAPPYHORSE_MIN_IMAGE_SIDE = 300
HAPPYHORSE_MIN_REFERENCE_SHORT_SIDE = 400
HAPPYHORSE_MAX_IMAGE_BYTES = 10 * 1024 * 1024
HAPPYHORSE_MIN_ASPECT_RATIO = 1 / 2.5
HAPPYHORSE_MAX_ASPECT_RATIO = 2.5
HAPPYHORSE_VIDEO_EDIT_VIDEO_FORMATS = {"mp4", "mov"}
HAPPYHORSE_VIDEO_EDIT_AUDIO_SETTINGS = {"auto", "origin"}
HAPPYHORSE_VIDEO_EDIT_MAX_VIDEO_BYTES = 100 * 1024 * 1024
HAPPYHORSE_VIDEO_EDIT_MAX_LONG_SIDE = 2160
HAPPYHORSE_VIDEO_EDIT_MIN_SHORT_SIDE = 320
HAPPYHORSE_VIDEO_EDIT_MIN_FPS = 8.0


def _is_cjk_unified_ideograph(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2A6DF
        or 0x2A700 <= codepoint <= 0x2B73F
        or 0x2B740 <= codepoint <= 0x2B81F
        or 0x2B820 <= codepoint <= 0x2CEAF
        or 0x2CEB0 <= codepoint <= 0x2EBEF
        or 0x30000 <= codepoint <= 0x3134F
    )


def _count_cjk_weighted_units(text: str, *, cjk_unit: int = 2, non_cjk_unit: int = 1) -> int:
    return sum(cjk_unit if _is_cjk_unified_ideograph(char) else non_cjk_unit for char in text)


def _parse_element_ids(raw_value: Any) -> List[int]:
    if raw_value in (None, "", []):
        return []

    values = raw_value if isinstance(raw_value, list) else [raw_value]
    result: List[int] = []
    seen = set()

    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
        else:
            parts = [value]
        for part in parts:
            try:
                item = int(part)
            except (TypeError, ValueError) as exc:
                raise ValueError("主体ID必须为正整数") from exc
            if item <= 0:
                raise ValueError("主体ID必须为正整数")
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


async def _validate_kling_image(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_image(url)
    if metadata["format"] not in KLING_IMAGE_FORMATS:
        raise ValueError(f"{label}格式仅支持 JPG/JPEG/PNG")
    if metadata["file_size"] > 10 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过10MB")
    if not (300 <= metadata["width"] <= 8000 and 300 <= metadata["height"] <= 8000):
        raise ValueError(f"{label}宽高需在300到8000像素之间")
    if metadata["has_alpha"]:
        raise ValueError(f"{label}不支持透明通道，请使用不带透明的 PNG/JPG")
    return metadata


async def _validate_kling_video(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_video(url)
    if metadata["format"] not in KLING_VIDEO_FORMATS:
        raise ValueError(f"{label}格式仅支持 MP4/MOV")
    if metadata["file_size"] > 200 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过200MB")
    if not (3.0 <= metadata["duration"] <= 10.0):
        raise ValueError(f"{label}时长需在3到10秒之间")
    if not (24.0 <= metadata["fps"] <= 60.0):
        raise ValueError(f"{label}帧率需在24到60FPS之间")
    if not (720 <= metadata["width"] <= 2160 and 720 <= metadata["height"] <= 2160):
        raise ValueError(f"{label}宽高需在720到2160像素之间")
    return metadata


async def _validate_vidu_image(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_image(url)
    if metadata["format"] not in VIDU_IMAGE_FORMATS:
        raise ValueError(f"{label}格式仅支持 JPG/JPEG/PNG/WEBP")
    if metadata["file_size"] > 50 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过50MB")
    if not (0.25 <= metadata["aspect_ratio"] <= 4.0):
        raise ValueError(f"{label}宽高比需在1:4到4:1之间")
    return metadata


async def _validate_vidu_video(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_video(url)
    if metadata["format"] not in VIDU_VIDEO_FORMATS:
        raise ValueError(f"{label}格式仅支持 MP4/AVI/MOV")
    if metadata["file_size"] > 50 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过50MB")
    if not (1.0 <= metadata["duration"] <= 5.0):
        raise ValueError(f"{label}时长需在1到5秒之间")
    if metadata["pixel_count"] < 128 * 128:
        raise ValueError(f"{label}分辨率总像素不能小于128×128")
    if not (0.25 <= metadata["aspect_ratio"] <= 4.0):
        raise ValueError(f"{label}宽高比需在1:4到4:1之间")
    return metadata


async def _validate_wan27_image(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_image(url)
    if metadata["format"] not in WAN27_IMAGE_FORMATS:
        raise ValueError(f"{label}格式仅支持 JPEG/JPG/PNG/BMP/WEBP")
    if metadata["has_alpha"]:
        raise ValueError(f"{label}不支持透明通道 PNG")
    if metadata["file_size"] > 20 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过20MB")
    if not (240 <= metadata["width"] <= 8000 and 240 <= metadata["height"] <= 8000):
        raise ValueError(f"{label}宽高需在240到8000像素之间")
    if not (0.125 <= metadata["aspect_ratio"] <= 8.0):
        raise ValueError(f"{label}宽高比需在1:8到8:1之间")
    return metadata


async def _validate_wan27_video(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_video(url)
    if metadata["format"] not in WAN27_VIDEO_FORMATS:
        raise ValueError(f"{label}格式仅支持 MP4/MOV")
    if metadata["file_size"] > 100 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过100MB")
    if not (2.0 <= metadata["duration"] <= 10.0):
        raise ValueError(f"{label}时长需在2到10秒之间")
    if not (240 <= metadata["width"] <= 4096 and 240 <= metadata["height"] <= 4096):
        raise ValueError(f"{label}宽高需在240到4096像素之间")
    if not (0.125 <= metadata["aspect_ratio"] <= 8.0):
        raise ValueError(f"{label}宽高比需在1:8到8:1之间")
    return metadata


async def _validate_wan27_reference_video(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_video(url)
    if metadata["format"] not in WAN27_VIDEO_FORMATS:
        raise ValueError(f"{label}格式仅支持 MP4/MOV")
    if metadata["file_size"] > 100 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过100MB")
    if not (1.0 <= metadata["duration"] <= 30.0):
        raise ValueError(f"{label}时长需在1到30秒之间")
    if not (240 <= metadata["width"] <= 4096 and 240 <= metadata["height"] <= 4096):
        raise ValueError(f"{label}宽高需在240到4096像素之间")
    if not (0.125 <= metadata["aspect_ratio"] <= 8.0):
        raise ValueError(f"{label}宽高比需在1:8到8:1之间")
    return metadata


async def _validate_wan27_audio(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_audio(url)
    if metadata["format"] not in WAN27_AUDIO_FORMATS:
        raise ValueError(f"{label}格式仅支持 WAV/MP3")
    if metadata["file_size"] > 15 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过15MB")
    if not (2.0 <= metadata["duration"] <= 30.0):
        raise ValueError(f"{label}时长需在2到30秒之间")
    return metadata


async def _validate_wan27_reference_voice(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_audio(url)
    if metadata["format"] not in WAN27_AUDIO_FORMATS:
        raise ValueError(f"{label}格式仅支持 WAV/MP3")
    if metadata["file_size"] > 15 * 1024 * 1024:
        raise ValueError(f"{label}大小不能超过15MB")
    if not (1.0 <= metadata["duration"] <= 10.0):
        raise ValueError(f"{label}时长需在1到10秒之间")
    return metadata


def _normalize_happyhorse_prompt(prompt: str, *, required: bool) -> str:
    normalized = (prompt or "").strip()
    if not normalized:
        if required:
            raise ValueError("提示词不能为空")
        return ""
    unit_count = _count_cjk_weighted_units(
        normalized,
        cjk_unit=HAPPYHORSE_PROMPT_CJK_UNIT,
        non_cjk_unit=HAPPYHORSE_PROMPT_NON_CJK_UNIT,
    )
    if unit_count > HAPPYHORSE_PROMPT_MAX_UNITS:
        raise ValueError("提示词长度不能超过2500个中文字符或5000个非中文字符")
    return normalized


async def _validate_happyhorse_image(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_image(url)
    if metadata["format"] not in HAPPYHORSE_IMAGE_FORMATS:
        raise ValueError(f"{label}格式仅支持 JPEG/JPG/PNG/WEBP")
    if metadata["file_size"] > HAPPYHORSE_MAX_IMAGE_BYTES:
        raise ValueError(f"{label}大小不能超过10MB")
    if metadata["width"] < HAPPYHORSE_MIN_IMAGE_SIDE or metadata["height"] < HAPPYHORSE_MIN_IMAGE_SIDE:
        raise ValueError(f"{label}宽高不能小于300像素")
    aspect_ratio = metadata.get("aspect_ratio") or (metadata["width"] / metadata["height"])
    if not (HAPPYHORSE_MIN_ASPECT_RATIO <= aspect_ratio <= HAPPYHORSE_MAX_ASPECT_RATIO):
        raise ValueError(f"{label}宽高比需在1:2.5到2.5:1之间")
    return metadata


async def _validate_happyhorse_reference_image(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_image(url)
    if metadata["format"] not in HAPPYHORSE_IMAGE_FORMATS:
        raise ValueError(f"{label}格式仅支持 JPEG/JPG/PNG/WEBP")
    if metadata["file_size"] > HAPPYHORSE_MAX_IMAGE_BYTES:
        raise ValueError(f"{label}大小不能超过10MB")
    if min(metadata["width"], metadata["height"]) < HAPPYHORSE_MIN_REFERENCE_SHORT_SIDE:
        raise ValueError(f"{label}短边不能小于400像素")
    return metadata


async def _validate_happyhorse_video_edit_reference_image(url: str, label: str) -> Dict[str, Any]:
    return await _validate_happyhorse_image(url, label)


async def _validate_happyhorse_video_edit_video(url: str, label: str) -> Dict[str, Any]:
    metadata = await inspect_remote_video(url)
    if metadata["format"] not in HAPPYHORSE_VIDEO_EDIT_VIDEO_FORMATS:
        raise ValueError(f"{label}格式仅支持 MP4/MOV")
    if metadata["file_size"] > HAPPYHORSE_VIDEO_EDIT_MAX_VIDEO_BYTES:
        raise ValueError(f"{label}大小不能超过100MB")
    if not (3.0 <= float(metadata["duration"]) <= 60.0):
        raise ValueError(f"{label}时长需在3到60秒之间")
    width = int(metadata["width"])
    height = int(metadata["height"])
    if max(width, height) > HAPPYHORSE_VIDEO_EDIT_MAX_LONG_SIDE:
        raise ValueError(f"{label}长边不能超过2160像素")
    if min(width, height) < HAPPYHORSE_VIDEO_EDIT_MIN_SHORT_SIDE:
        raise ValueError(f"{label}短边不能小于320像素")
    aspect_ratio = metadata.get("aspect_ratio") or (width / height)
    if not (HAPPYHORSE_MIN_ASPECT_RATIO <= aspect_ratio <= HAPPYHORSE_MAX_ASPECT_RATIO):
        raise ValueError(f"{label}宽高比需在1:2.5到2.5:1之间")
    if float(metadata.get("fps") or 0) <= HAPPYHORSE_VIDEO_EDIT_MIN_FPS:
        raise ValueError(f"{label}帧率必须大于8FPS")
    return metadata


@dataclass
class NormalizedVideoTaskRequest:
    project_id: str
    task_kind: str
    provider: str
    model_id: str
    key_profile: Optional[str] = None
    prompt: str = ""
    negative_prompt: str = ""
    narrative_mode: str = "single"
    input_assets: Dict[str, Any] = field(default_factory=dict)
    normalized_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoSubmitResult:
    task_id: str
    request_id: Optional[str] = None
    provider_payload: Optional[Dict[str, Any]] = None
    key_profile: Optional[str] = None


class VideoProviderError(ValueError):
    """保留厂商提交阶段错误的结构化上下文。"""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        request_id: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        key_profile: Optional[str] = None,
        provider_payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(f"{code} - {message}")
        self.code = code
        self.message = message
        self.request_id = request_id
        self.raw_response = raw_response or {}
        self.provider = provider
        self.key_profile = key_profile
        self.provider_payload = provider_payload


@dataclass
class VideoStatusResult:
    status: str
    video_url: Optional[str] = None
    request_id: Optional[str] = None
    key_profile: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_output: Dict[str, Any] = field(default_factory=dict)


class DashScopeGenericVideoService:
    """Kling / Vidu 的通用异步视频服务"""

    def __init__(self, provider: str, key_profile: Optional[str] = None):
        config = get_config()
        self.provider = provider
        self.key_profile = get_provider_key_profile(provider, override_profile=key_profile, config=config)
        self.api_key = get_provider_api_key(provider, override_profile=self.key_profile)
        self.base_url = config.base_url.rstrip("/")

    async def create_task(self, request_body: Dict[str, Any]) -> VideoSubmitResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/video-generation/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=request_body,
            )
            result = response.json()

        if response.status_code != 200:
            code = result.get("code", "Unknown")
            message = result.get("message", "未知错误")
            raise VideoProviderError(
                code=code,
                message=message,
                request_id=result.get("request_id"),
                raw_response=result,
                provider=self.provider,
                key_profile=self.key_profile,
                provider_payload=request_body,
            )

        output = result.get("output", {})
        task_id = output.get("task_id")
        if not task_id:
            raise ValueError("创建任务失败：未返回 task_id")

        return VideoSubmitResult(
            task_id=task_id,
            request_id=result.get("request_id"),
            provider_payload=request_body,
            key_profile=self.key_profile,
        )

    async def get_task_status(self, task_id: str, project_id: str = "") -> VideoStatusResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            result = response.json()

        output = result.get("output", {})
        status = output.get("task_status", "UNKNOWN")
        video_url = output.get("video_url")
        request_id = result.get("request_id")

        if status == "SUCCEEDED" and video_url:
            if oss_service.is_enabled():
                video_url = await oss_service.upload_video_async(video_url, project_id)
            else:
                logger.warning("[视频工作室] OSS 未启用，保留供应商视频 URL")

        return VideoStatusResult(
            status=status,
            video_url=video_url,
            request_id=request_id,
            key_profile=self.key_profile,
            usage=result.get("usage") or {},
            error_code=output.get("code") or result.get("code"),
            error_message=output.get("message") or result.get("message"),
            raw_output=output,
        )


class BaseVideoProviderAdapter(ABC):
    provider: str

    @abstractmethod
    async def validate(self, request: NormalizedVideoTaskRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    async def submit(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> VideoSubmitResult:
        raise NotImplementedError

    @abstractmethod
    async def fetch(self, request: NormalizedVideoTaskRequest, task_id: str) -> VideoStatusResult:
        raise NotImplementedError

    @abstractmethod
    def build_provider_payload(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> Dict[str, Any]:
        raise NotImplementedError


class WanVideoAdapter(BaseVideoProviderAdapter):
    provider = "wan"

    @staticmethod
    def _resolve_key_profile(request: NormalizedVideoTaskRequest) -> str:
        return get_provider_key_profile("wan", override_profile=request.key_profile)

    @classmethod
    def _apply_service_key(cls, service: Any, request: NormalizedVideoTaskRequest) -> str:
        key_profile = cls._resolve_key_profile(request)
        service.api_key = get_provider_api_key("wan", override_profile=key_profile)
        return key_profile

    @staticmethod
    def _is_wan27_i2v(request: NormalizedVideoTaskRequest) -> bool:
        return request.model_id in WAN27_I2V_MODEL_IDS

    @staticmethod
    def _is_wan27_t2v(request: NormalizedVideoTaskRequest) -> bool:
        return request.model_id == "wan2.7-t2v"

    @staticmethod
    def _is_wan27_r2v(request: NormalizedVideoTaskRequest) -> bool:
        return request.model_id == "wan2.7-r2v"

    @staticmethod
    def _is_wan27_videoedit(request: NormalizedVideoTaskRequest) -> bool:
        return request.model_id == "wan2.7-videoedit"

    @classmethod
    def _wan27_service(cls, request: NormalizedVideoTaskRequest) -> DashScopeGenericVideoService:
        return DashScopeGenericVideoService("wan", key_profile=cls._resolve_key_profile(request))

    async def validate(self, request: NormalizedVideoTaskRequest) -> None:
        params = request.normalized_params
        assets = request.input_assets
        duration = int(params["duration"]) if params.get("duration") is not None else 5

        if params.get("seed") is not None and not (0 <= int(params["seed"]) <= SEED_MAX):
            raise ValueError("随机种子必须在 0 到 2147483647 之间")

        if request.task_kind == "image_to_video":
            if not assets.get("first_frame"):
                raise ValueError("首帧生视频需要选择首帧图")
            if self._is_wan27_i2v(request):
                if params.get("resolution") not in WAN27_I2V_RESOLUTIONS:
                    raise ValueError("wan2.7 图生视频分辨率仅支持 720P / 1080P")
                if not (2 <= duration <= 15):
                    raise ValueError("wan2.7 图生视频时长需在2到15秒之间")
                await _validate_wan27_image((assets.get("first_frame") or [None])[0], "首帧图")
                audio_asset = (assets.get("audio") or [None])[0]
                if audio_asset:
                    await _validate_wan27_audio(audio_asset, "驱动音频")
                if request.prompt and len(request.prompt) > 5000:
                    raise ValueError("wan2.7 图生视频提示词长度不能超过5000字符")
                if request.negative_prompt and len(request.negative_prompt) > 500:
                    raise ValueError("wan2.7 图生视频负面提示词长度不能超过500字符")
                return
            if request.model_id == "wan2.2-s2v" and not assets.get("audio"):
                raise ValueError("数字人模型需要驱动音频")
        elif request.task_kind == "text_to_video":
            if not request.prompt:
                raise ValueError("文生视频需要输入提示词")
            if self._is_wan27_t2v(request):
                if params.get("resolution") not in WAN27_T2V_RESOLUTIONS:
                    raise ValueError("wan2.7 文生视频分辨率仅支持 720P / 1080P")
                if params.get("ratio") is not None and params.get("ratio") not in WAN27_COMMON_RATIOS:
                    raise ValueError("wan2.7 文生视频画面比例仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4")
                if not (2 <= duration <= 15):
                    raise ValueError("wan2.7 文生视频时长需在2到15秒之间")
                audio_asset = (assets.get("audio") or [None])[0]
                if audio_asset:
                    await _validate_wan27_audio(audio_asset, "自定义音频")
                if len(request.prompt) > 5000:
                    raise ValueError("wan2.7 文生视频提示词长度不能超过5000字符")
                if request.negative_prompt and len(request.negative_prompt) > 500:
                    raise ValueError("wan2.7 文生视频负面提示词长度不能超过500字符")
                return
        elif request.task_kind == "reference_to_video":
            reference_media = list(assets.get("reference_media") or [])
            if self._is_wan27_r2v(request):
                first_frames = list(assets.get("first_frame") or [])
                if len(first_frames) > 1:
                    raise ValueError("wan2.7 参考生视频最多支持1张首帧图")
                if first_frames:
                    await _validate_wan27_image(first_frames[0], "首帧图")
                if not reference_media:
                    raise ValueError("wan2.7 参考生视频需要至少一项参考素材")
                reference_images = [item for item in reference_media if item.get("type") == "reference_image"]
                reference_videos = [item for item in reference_media if item.get("type") == "reference_video"]
                if len(reference_images) + len(reference_videos) > 5:
                    raise ValueError("wan2.7 参考生视频参考图和参考视频总数不能超过5个")
                for index, item in enumerate(reference_media, start=1):
                    item_type = item.get("type")
                    item_url = item.get("url")
                    if item_type not in {"reference_image", "reference_video"}:
                        raise ValueError("wan2.7 参考生视频素材类型仅支持 reference_image / reference_video")
                    if not item_url:
                        raise ValueError("wan2.7 参考生视频素材缺少 url")
                    if item_type == "reference_image":
                        await _validate_wan27_image(item_url, f"参考图{index}")
                    else:
                        await _validate_wan27_reference_video(item_url, f"参考视频{index}")
                    if item.get("reference_voice"):
                        await _validate_wan27_reference_voice(item["reference_voice"], f"参考音频{index}")
                if params.get("resolution") not in WAN27_R2V_RESOLUTIONS:
                    raise ValueError("wan2.7 参考生视频分辨率仅支持 720P / 1080P")
                if not first_frames and params.get("ratio") is not None and params.get("ratio") not in WAN27_COMMON_RATIOS:
                    raise ValueError("wan2.7 参考生视频画面比例仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4")
                if not (2 <= duration <= 10):
                    raise ValueError("wan2.7 参考生视频时长需在2到10秒之间")
                if request.prompt and len(request.prompt) > 5000:
                    raise ValueError("wan2.7 参考生视频提示词长度不能超过5000字符")
                if request.negative_prompt and len(request.negative_prompt) > 500:
                    raise ValueError("wan2.7 参考生视频负面提示词长度不能超过500字符")
                return
            if not assets.get("reference_images") and not assets.get("reference_videos"):
                raise ValueError("参考生视频需要至少一项参考素材")
        elif request.task_kind == "keyframe_to_video":
            if not assets.get("first_frame") or not assets.get("last_frame"):
                raise ValueError("首尾帧生视频需要同时提供首帧和尾帧图片")
            if self._is_wan27_i2v(request):
                if params.get("resolution") not in WAN27_I2V_RESOLUTIONS:
                    raise ValueError("wan2.7 首尾帧生视频分辨率仅支持 720P / 1080P")
                if not (2 <= duration <= 15):
                    raise ValueError("wan2.7 首尾帧生视频时长需在2到15秒之间")
                await _validate_wan27_image((assets.get("first_frame") or [None])[0], "首帧图")
                await _validate_wan27_image((assets.get("last_frame") or [None])[0], "尾帧图")
                audio_asset = (assets.get("audio") or [None])[0]
                if audio_asset:
                    await _validate_wan27_audio(audio_asset, "驱动音频")
                if request.prompt and len(request.prompt) > 5000:
                    raise ValueError("wan2.7 首尾帧生视频提示词长度不能超过5000字符")
                if request.negative_prompt and len(request.negative_prompt) > 500:
                    raise ValueError("wan2.7 首尾帧生视频负面提示词长度不能超过500字符")
                return
        elif request.task_kind == "video_extension":
            if not self._is_wan27_i2v(request):
                raise ValueError("当前仅 wan2.7-i2v 支持视频续写")
            if not assets.get("first_clip"):
                raise ValueError("视频续写需要选择首段视频")
            if params.get("resolution") not in WAN27_I2V_RESOLUTIONS:
                raise ValueError("wan2.7 视频续写分辨率仅支持 720P / 1080P")
            if not (2 <= duration <= 15):
                raise ValueError("wan2.7 视频续写时长需在2到15秒之间")
            await _validate_wan27_video((assets.get("first_clip") or [None])[0], "首段视频")
            last_frame = (assets.get("last_frame") or [None])[0]
            if last_frame:
                await _validate_wan27_image(last_frame, "尾帧图")
            if assets.get("audio"):
                raise ValueError("视频续写不支持驱动音频")
            if request.prompt and len(request.prompt) > 5000:
                raise ValueError("wan2.7 视频续写提示词长度不能超过5000字符")
            if request.negative_prompt and len(request.negative_prompt) > 500:
                raise ValueError("wan2.7 视频续写负面提示词长度不能超过500字符")
            return
        elif request.task_kind == "video_edit_global":
            if not self._is_wan27_videoedit(request):
                raise ValueError(f"万相暂不支持任务类型: {request.task_kind}")
            base_video = assets.get("base_video") or assets.get("source_video") or []
            if len(base_video) != 1:
                raise ValueError("wan2.7 视频编辑必须且仅能提供1个待编辑视频")
            await _validate_wan27_video(base_video[0], "待编辑视频")
            reference_images = list(assets.get("reference_images") or [])
            if len(reference_images) > 3:
                raise ValueError("wan2.7 视频编辑最多支持3张参考图")
            for index, image_url in enumerate(reference_images, start=1):
                await _validate_wan27_image(image_url, f"参考图{index}")
            if params.get("resolution") not in WAN27_VIDEOEDIT_RESOLUTIONS:
                raise ValueError("wan2.7 视频编辑分辨率仅支持 720P / 1080P")
            if params.get("ratio") is not None and params.get("ratio") not in WAN27_VIDEOEDIT_RATIOS:
                raise ValueError("wan2.7 视频编辑画面比例仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4")
            if params.get("audio_setting") is not None and params.get("audio_setting") not in WAN27_VIDEOEDIT_AUDIO_SETTINGS:
                raise ValueError("wan2.7 视频编辑声音设置仅支持 auto / origin")
            if duration not in {0, *range(2, 11)}:
                raise ValueError("wan2.7 视频编辑时长仅支持 0 或 2 到 10 秒")
            if request.prompt and len(request.prompt) > 5000:
                raise ValueError("wan2.7 视频编辑提示词长度不能超过5000字符")
            if request.negative_prompt and len(request.negative_prompt) > 500:
                raise ValueError("wan2.7 视频编辑负面提示词长度不能超过500字符")
            return
        elif request.task_kind == "video_repainting":
            await self._validate_vace_request(request, require_mask=False)
            return
        elif request.task_kind == "video_edit_local":
            await self._validate_vace_request(request, require_mask=True)
            return

        else:
            raise ValueError(f"万相暂不支持任务类型: {request.task_kind}")

    async def _validate_vace_request(self, request: NormalizedVideoTaskRequest, require_mask: bool) -> None:
        service = VaceVideoEditService()
        params = request.normalized_params
        assets = request.input_assets

        if not oss_service.is_enabled():
            raise ValueError("VACE任务需要启用OSS，请先在设置中配置并启用OSS")

        if not request.prompt:
            raise ValueError("请输入提示词")
        if len(request.prompt) > 800:
            raise ValueError("提示词长度不能超过800字符")
        if params.get("seed") is not None and not (0 <= int(params["seed"]) <= SEED_MAX):
            raise ValueError("随机种子必须在0到2147483647之间")

        source_video = assets.get("source_video")
        if not source_video:
            raise ValueError("请选择源视频")
        source_video_url = source_video[0] if isinstance(source_video, list) else source_video
        source_metadata = await service.validate_source_video(source_video_url)

        reference_images = assets.get("reference_images") or []
        if reference_images:
            await service.validate_reference_image(reference_images[0])

        if require_mask:
            control_condition = params.get("control_condition")
            if control_condition and control_condition not in VACE_EDIT_CONTROL_CONDITIONS:
                raise ValueError("局部编辑的控制条件不合法")
            mask_type = params.get("mask_type") or "tracking"
            if mask_type not in VACE_EDIT_MASK_TYPES:
                raise ValueError("局部编辑的mask_type不合法")
            if params.get("size") and params["size"] not in VACE_EDIT_SIZES:
                raise ValueError("局部编辑的输出分辨率不合法")
            if mask_type == "tracking":
                if params.get("expand_ratio") is not None and not (0.0 <= float(params["expand_ratio"]) <= 1.0):
                    raise ValueError("expand_ratio必须在0到1之间")
                if params.get("expand_mode") and params["expand_mode"] not in VACE_EDIT_EXPAND_MODES:
                    raise ValueError("expand_mode不合法")
            else:
                if params.get("expand_ratio") is not None:
                    raise ValueError("fixed模式下不支持expand_ratio")
                if params.get("expand_mode") is not None:
                    raise ValueError("fixed模式下不支持expand_mode")
        else:
            if params.get("control_condition") not in VACE_REPAINTING_CONTROL_CONDITIONS:
                raise ValueError("视频重绘的控制条件不合法")
            if params.get("strength") is not None and not (0.0 <= float(params["strength"]) <= 1.0):
                raise ValueError("视频重绘强度必须在0到1之间")

        if require_mask:
            mask_asset = assets.get("mask_image")
            if not mask_asset:
                raise ValueError("局部编辑需要上传 Mask")
            mask_url = mask_asset[0] if isinstance(mask_asset, list) else mask_asset
            await service.validate_mask_image(mask_url, source_metadata["width"], source_metadata["height"])
            if params.get("mask_frame_id") not in (None, VACE_MASK_FRAME_ID):
                raise ValueError("当前仅支持首帧 Mask，mask_frame_id 固定为 1")

    async def submit(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> VideoSubmitResult:
        params = dict(request.normalized_params)
        assets = request.input_assets
        provider_payload = self.build_provider_payload(request, seed_offset)
        seed = params.get("seed")
        if seed is not None:
            params["seed"] = int(seed) + seed_offset

        if (
            self._is_wan27_i2v(request)
            or self._is_wan27_t2v(request)
            or self._is_wan27_r2v(request)
            or self._is_wan27_videoedit(request)
        ):
            service = self._wan27_service(request)
            return await service.create_task(provider_payload)

        if request.task_kind == "image_to_video":
            first_frame = assets.get("first_frame")
            image_url = first_frame[0] if isinstance(first_frame, list) else first_frame
            audio_asset = assets.get("audio")
            audio_url = None
            if audio_asset:
                audio_url = audio_asset[0] if isinstance(audio_asset, list) else audio_asset
            if request.model_id == "wan2.2-s2v":
                svc = DigitalHumanService()
                key_profile = self._apply_service_key(svc, request)
                task_id = await svc.create_task(
                    image_url=image_url,
                    audio_url=audio_url,
                    model=request.model_id,
                    resolution=params.get("resolution"),
                )
                return VideoSubmitResult(
                    task_id=task_id,
                    request_id=getattr(svc, "last_request_id", None),
                    provider_payload=provider_payload,
                    key_profile=key_profile,
                )

            svc = ImageToVideoService()
            key_profile = self._apply_service_key(svc, request)
            task_id = await svc.create_task(
                image_url=image_url,
                prompt=request.prompt,
                model=request.model_id,
                resolution=params.get("resolution"),
                duration=params.get("duration"),
                prompt_extend=params.get("prompt_extend"),
                watermark=params.get("watermark"),
                seed=params.get("seed"),
                audio_url=audio_url,
                audio=params.get("audio") if request.model_id == "wan2.6-i2v-flash" else None,
                negative_prompt=request.negative_prompt or None,
                shot_type=params.get("shot_type"),
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        if request.task_kind == "text_to_video":
            svc = TextToVideoService()
            key_profile = self._apply_service_key(svc, request)
            task_id = await svc.create_task(
                prompt=request.prompt,
                model=request.model_id,
                size=params.get("size"),
                duration=params.get("duration"),
                prompt_extend=params.get("prompt_extend"),
                shot_type=params.get("shot_type"),
                watermark=params.get("watermark"),
                seed=params.get("seed"),
                audio_url=(assets.get("audio") or [None])[0] if isinstance(assets.get("audio"), list) else assets.get("audio"),
                negative_prompt=request.negative_prompt or None,
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        if request.task_kind == "reference_to_video":
            svc = ReferenceToVideoService()
            key_profile = self._apply_service_key(svc, request)
            reference_urls = list(assets.get("reference_videos") or []) + list(assets.get("reference_images") or [])
            task_id = await svc.create_task(
                reference_urls=reference_urls,
                prompt=request.prompt,
                model=request.model_id,
                size=params.get("size"),
                duration=params.get("duration"),
                shot_type=params.get("shot_type"),
                watermark=params.get("watermark"),
                seed=params.get("seed"),
                negative_prompt=request.negative_prompt or None,
                audio=params.get("audio"),
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        if request.task_kind == "keyframe_to_video":
            svc = KeyframeToVideoService()
            key_profile = self._apply_service_key(svc, request)
            first_frame = (assets.get("first_frame") or [None])[0]
            last_frame = (assets.get("last_frame") or [None])[0]
            task_id = await svc.create_task(
                first_frame_url=first_frame,
                last_frame_url=last_frame,
                prompt=request.prompt or None,
                model=request.model_id,
                resolution=params.get("resolution"),
                prompt_extend=params.get("prompt_extend"),
                watermark=params.get("watermark"),
                seed=params.get("seed"),
                negative_prompt=request.negative_prompt or None,
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        if request.task_kind == "video_repainting":
            svc = VaceVideoEditService()
            key_profile = self._apply_service_key(svc, request)
            source_video = (assets.get("source_video") or [None])[0]
            reference_image = (assets.get("reference_images") or [None])[0]
            task_id = await svc.create_video_repainting_task(
                prompt=request.prompt,
                source_video_url=source_video,
                reference_image_url=reference_image,
                control_condition=params.get("control_condition"),
                strength=params.get("strength"),
                prompt_extend=params.get("prompt_extend"),
                seed=params.get("seed"),
                watermark=params.get("watermark"),
                model=request.model_id,
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        if request.task_kind == "video_edit_local":
            svc = VaceVideoEditService()
            key_profile = self._apply_service_key(svc, request)
            source_video = (assets.get("source_video") or [None])[0]
            reference_image = (assets.get("reference_images") or [None])[0]
            mask_image = (assets.get("mask_image") or [None])[0]
            task_id = await svc.create_video_edit_task(
                prompt=request.prompt,
                source_video_url=source_video,
                mask_image_url=mask_image,
                mask_frame_id=params.get("mask_frame_id") or VACE_MASK_FRAME_ID,
                reference_image_url=reference_image,
                control_condition=params.get("control_condition"),
                mask_type=params.get("mask_type"),
                expand_ratio=params.get("expand_ratio"),
                expand_mode=params.get("expand_mode"),
                size=params.get("size"),
                prompt_extend=params.get("prompt_extend"),
                seed=params.get("seed"),
                watermark=params.get("watermark"),
                model=request.model_id,
            )
            return VideoSubmitResult(
                task_id=task_id,
                request_id=getattr(svc, "last_request_id", None),
                provider_payload=provider_payload,
                key_profile=key_profile,
            )

        raise ValueError(f"不支持的万相任务类型: {request.task_kind}")

    async def fetch(self, request: NormalizedVideoTaskRequest, task_id: str) -> VideoStatusResult:
        try:
            if (
                self._is_wan27_i2v(request)
                or self._is_wan27_t2v(request)
                or self._is_wan27_r2v(request)
                or self._is_wan27_videoedit(request)
            ):
                service = self._wan27_service(request)
                return await service.get_task_status(task_id, request.project_id)
            if request.task_kind == "reference_to_video":
                svc = ReferenceToVideoService()
                key_profile = self._apply_service_key(svc, request)
                status, video_url = await svc.get_task_status(task_id, request.project_id)
                return VideoStatusResult(
                    status=status,
                    video_url=video_url,
                    request_id=getattr(svc, "last_request_id", None),
                    key_profile=key_profile,
                    usage=getattr(svc, "last_usage", {}) or {},
                    error_code=getattr(svc, "last_error_code", None),
                    error_message=getattr(svc, "last_error_message", None),
                    raw_output=getattr(svc, "last_raw_output", {}) or {},
                )
            if request.task_kind == "text_to_video":
                svc = TextToVideoService()
                key_profile = self._apply_service_key(svc, request)
                status, video_url = await svc.get_task_status(task_id, request.project_id)
                return VideoStatusResult(
                    status=status,
                    video_url=video_url,
                    request_id=getattr(svc, "last_request_id", None),
                    key_profile=key_profile,
                    usage=getattr(svc, "last_usage", {}) or {},
                    error_code=getattr(svc, "last_error_code", None),
                    error_message=getattr(svc, "last_error_message", None),
                    raw_output=getattr(svc, "last_raw_output", {}) or {},
                )
            if request.task_kind == "keyframe_to_video":
                svc = KeyframeToVideoService()
                key_profile = self._apply_service_key(svc, request)
                status, video_url = await svc.get_task_status(task_id, request.project_id)
                return VideoStatusResult(
                    status=status,
                    video_url=video_url,
                    request_id=getattr(svc, "last_request_id", None),
                    key_profile=key_profile,
                    usage=getattr(svc, "last_usage", {}) or {},
                    error_code=getattr(svc, "last_error_code", None),
                    error_message=getattr(svc, "last_error_message", None),
                    raw_output=getattr(svc, "last_raw_output", {}) or {},
                )
            if request.task_kind in {"video_repainting", "video_edit_local"}:
                svc = VaceVideoEditService()
                key_profile = self._apply_service_key(svc, request)
                status, video_url = await svc.get_task_status(task_id, request.project_id)
                return VideoStatusResult(
                    status=status,
                    video_url=video_url,
                    request_id=getattr(svc, "last_request_id", None),
                    key_profile=key_profile,
                    usage=getattr(svc, "last_usage", {}) or {},
                    error_code=getattr(svc, "last_error_code", None),
                    error_message=getattr(svc, "last_error_message", None),
                    raw_output=getattr(svc, "last_raw_output", {}) or {},
                )
            if request.model_id == "wan2.2-s2v":
                svc = DigitalHumanService()
                key_profile = self._apply_service_key(svc, request)
                status, video_url = await svc.get_task_status(task_id, request.project_id)
                return VideoStatusResult(
                    status=status,
                    video_url=video_url,
                    request_id=getattr(svc, "last_request_id", None),
                    key_profile=key_profile,
                    usage=getattr(svc, "last_usage", {}) or {},
                    error_code=getattr(svc, "last_error_code", None),
                    error_message=getattr(svc, "last_error_message", None),
                    raw_output=getattr(svc, "last_raw_output", {}) or {},
                )

            svc = ImageToVideoService()
            key_profile = self._apply_service_key(svc, request)
            status, video_url = await svc.get_task_status(task_id, request.project_id, use_http="wan2.6" in request.model_id)
            return VideoStatusResult(
                status=status,
                video_url=video_url,
                request_id=getattr(svc, "last_request_id", None),
                key_profile=key_profile,
                usage=getattr(svc, "last_usage", {}) or {},
                error_code=getattr(svc, "last_error_code", None),
                error_message=getattr(svc, "last_error_message", None),
                raw_output=getattr(svc, "last_raw_output", {}) or {},
            )
        except Exception as exc:
            return VideoStatusResult(
                status="FAILED",
                error_message=str(exc),
                key_profile=self._resolve_key_profile(request),
            )

    def build_provider_payload(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> Dict[str, Any]:
        params = dict(request.normalized_params)
        assets = request.input_assets
        if params.get("seed") is not None:
            params["seed"] = int(params["seed"]) + seed_offset

        base_payload: Dict[str, Any] = {"model": request.model_id, "input": {}, "parameters": {}}
        if request.prompt:
            base_payload["input"]["prompt"] = request.prompt
        if request.negative_prompt:
            base_payload["input"]["negative_prompt"] = request.negative_prompt

        if self._is_wan27_i2v(request):
            media: List[Dict[str, Any]] = []
            first_frame = (assets.get("first_frame") or [None])[0]
            last_frame = (assets.get("last_frame") or [None])[0]
            audio_url = (assets.get("audio") or [None])[0]
            first_clip = (assets.get("first_clip") or [None])[0]
            if request.task_kind == "video_extension":
                if first_clip:
                    media.append({"type": "first_clip", "url": first_clip})
                if last_frame:
                    media.append({"type": "last_frame", "url": last_frame})
            else:
                if first_frame:
                    media.append({"type": "first_frame", "url": first_frame})
                if request.task_kind == "keyframe_to_video" and last_frame:
                    media.append({"type": "last_frame", "url": last_frame})
                if audio_url:
                    media.append({"type": "driving_audio", "url": audio_url})
            base_payload["input"]["media"] = media
            for key in ("resolution", "duration", "prompt_extend", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if self._is_wan27_videoedit(request):
            media = []
            base_video = (assets.get("base_video") or assets.get("source_video") or [None])[0]
            if base_video:
                media.append({"type": "video", "url": base_video})
            for image_url in assets.get("reference_images") or []:
                media.append({"type": "reference_image", "url": image_url})
            base_payload["input"]["media"] = media
            for key in ("resolution", "ratio", "duration", "audio_setting", "prompt_extend", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if self._is_wan27_t2v(request):
            audio_url = (assets.get("audio") or [None])[0]
            if audio_url:
                base_payload["input"]["audio_url"] = audio_url
            for key in ("resolution", "ratio", "duration", "prompt_extend", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if self._is_wan27_r2v(request):
            media: List[Dict[str, Any]] = []
            first_frame = (assets.get("first_frame") or [None])[0]
            if first_frame:
                media.append({"type": "first_frame", "url": first_frame})
            for item in assets.get("reference_media") or []:
                media_item = {
                    "type": item["type"],
                    "url": item["url"],
                }
                if item.get("reference_voice"):
                    media_item["reference_voice"] = item["reference_voice"]
                media.append(media_item)
            base_payload["input"]["media"] = media
            for key in ("resolution", "duration", "prompt_extend", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            if not first_frame and params.get("ratio") is not None:
                base_payload["parameters"]["ratio"] = params.get("ratio")
            return base_payload

        if request.task_kind == "image_to_video":
            base_payload["input"]["img_url"] = (assets.get("first_frame") or [None])[0]
            audio_url = (assets.get("audio") or [None])[0]
            if audio_url:
                base_payload["input"]["audio_url"] = audio_url
            if request.model_id == "wan2.2-s2v":
                base_payload["parameters"]["resolution"] = params.get("resolution")
                return base_payload
            for key in ("resolution", "duration", "prompt_extend", "watermark", "seed", "shot_type"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            if request.model_id == "wan2.6-i2v-flash" and params.get("audio") is not None:
                base_payload["parameters"]["audio"] = params.get("audio")
            return base_payload

        if request.task_kind == "text_to_video":
            audio_url = (assets.get("audio") or [None])[0]
            if audio_url:
                base_payload["input"]["audio_url"] = audio_url
            for key in ("size", "duration", "prompt_extend", "shot_type", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if request.task_kind == "reference_to_video":
            base_payload["input"]["reference_urls"] = list(assets.get("reference_videos") or []) + list(assets.get("reference_images") or [])
            for key in ("size", "duration", "shot_type", "watermark", "seed", "audio"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if request.task_kind == "keyframe_to_video":
            base_payload["input"]["first_frame_url"] = (assets.get("first_frame") or [None])[0]
            base_payload["input"]["last_frame_url"] = (assets.get("last_frame") or [None])[0]
            for key in ("resolution", "prompt_extend", "watermark", "seed"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if request.task_kind == "video_repainting":
            base_payload["input"] = {
                "function": "video_repainting",
                "prompt": request.prompt,
                "video_url": (assets.get("source_video") or [None])[0],
            }
            reference_image = (assets.get("reference_images") or [None])[0]
            if reference_image:
                base_payload["input"]["ref_images_url"] = [reference_image]
                base_payload["parameters"]["obj_or_bg"] = ["obj"]
            for key in ("control_condition", "strength", "prompt_extend", "seed", "watermark"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        if request.task_kind == "video_edit_local":
            base_payload["input"] = {
                "function": "video_edit",
                "prompt": request.prompt,
                "video_url": (assets.get("source_video") or [None])[0],
                "mask_image_url": (assets.get("mask_image") or [None])[0],
                "mask_frame_id": params.get("mask_frame_id") or VACE_MASK_FRAME_ID,
            }
            reference_image = (assets.get("reference_images") or [None])[0]
            if reference_image:
                base_payload["input"]["ref_images_url"] = [reference_image]
                base_payload["parameters"]["obj_or_bg"] = ["obj"]
            for key in ("control_condition", "mask_type", "expand_ratio", "expand_mode", "size", "prompt_extend", "seed", "watermark"):
                if params.get(key) is not None:
                    base_payload["parameters"][key] = params.get(key)
            return base_payload

        return base_payload


class HappyHorseVideoAdapter(BaseVideoProviderAdapter):
    provider = "happyhorse"

    @staticmethod
    def _service(request: NormalizedVideoTaskRequest) -> DashScopeGenericVideoService:
        return DashScopeGenericVideoService("happyhorse", request.key_profile)

    @staticmethod
    def _reference_image_urls(request: NormalizedVideoTaskRequest) -> List[str]:
        assets = request.input_assets
        reference_media = list(assets.get("reference_media") or [])
        if reference_media:
            urls: List[str] = []
            for item in reference_media:
                if item.get("type") != "reference_image":
                    raise ValueError("HappyHorse 参考生视频仅支持参考图，不支持参考视频")
                if item.get("reference_voice"):
                    raise ValueError("HappyHorse 参考生视频不支持参考音频")
                if not item.get("url"):
                    raise ValueError("HappyHorse 参考生视频参考图缺少URL")
                urls.append(item["url"])
            return urls
        if assets.get("reference_videos"):
            raise ValueError("HappyHorse 参考生视频仅支持参考图，不支持参考视频")
        return list(assets.get("reference_images") or [])

    @staticmethod
    def _video_edit_base_video_url(request: NormalizedVideoTaskRequest) -> Optional[str]:
        assets = request.input_assets
        base_videos = list(assets.get("base_video") or [])
        source_videos = list(assets.get("source_video") or [])
        videos = base_videos or source_videos
        if len(videos) > 1:
            raise ValueError("HappyHorse 视频编辑必须且仅能提供1个待编辑视频")
        return videos[0] if videos else None

    @staticmethod
    def _video_edit_reference_image_urls(request: NormalizedVideoTaskRequest) -> List[str]:
        assets = request.input_assets
        reference_media = list(assets.get("reference_media") or [])
        if reference_media:
            urls: List[str] = []
            for item in reference_media:
                if item.get("type") != "reference_image":
                    raise ValueError("HappyHorse 视频编辑参考素材仅支持参考图")
                if item.get("reference_voice"):
                    raise ValueError("HappyHorse 视频编辑不支持参考音频")
                if not item.get("url"):
                    raise ValueError("HappyHorse 视频编辑参考图缺少URL")
                urls.append(item["url"])
            return urls
        if assets.get("reference_videos"):
            raise ValueError("HappyHorse 视频编辑参考素材仅支持参考图")
        return list(assets.get("reference_images") or [])

    async def validate(self, request: NormalizedVideoTaskRequest) -> None:
        params = request.normalized_params
        assets = request.input_assets
        duration = int(params.get("duration") or 5)

        if params.get("seed") is not None and not (0 <= int(params["seed"]) <= SEED_MAX):
            raise ValueError("随机种子必须在 0 到 2147483647 之间")

        if request.task_kind == "text_to_video":
            _normalize_happyhorse_prompt(request.prompt, required=True)
            if params.get("resolution") not in HAPPYHORSE_RESOLUTIONS:
                raise ValueError("HappyHorse 文生视频分辨率仅支持 720P / 1080P")
            if params.get("ratio") not in HAPPYHORSE_RATIOS:
                raise ValueError("HappyHorse 文生视频画面比例仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4")
            if duration not in HAPPYHORSE_DURATIONS:
                raise ValueError("HappyHorse 文生视频时长仅支持 3 到 15 秒")
            return

        if request.task_kind == "image_to_video":
            _normalize_happyhorse_prompt(request.prompt, required=False)
            first_frames = list(assets.get("first_frame") or [])
            if len(first_frames) != 1:
                raise ValueError("HappyHorse 图生视频仅支持1张首帧图")
            if params.get("resolution") not in HAPPYHORSE_RESOLUTIONS:
                raise ValueError("HappyHorse 图生视频分辨率仅支持 720P / 1080P")
            if duration not in HAPPYHORSE_DURATIONS:
                raise ValueError("HappyHorse 图生视频时长仅支持 3 到 15 秒")
            await _validate_happyhorse_image(first_frames[0], "首帧图")
            return

        if request.task_kind == "reference_to_video":
            _normalize_happyhorse_prompt(request.prompt, required=True)
            reference_images = self._reference_image_urls(request)
            if not (1 <= len(reference_images) <= 9):
                raise ValueError("HappyHorse 参考生视频需要1到9张参考图")
            if params.get("resolution") not in HAPPYHORSE_RESOLUTIONS:
                raise ValueError("HappyHorse 参考生视频分辨率仅支持 720P / 1080P")
            if params.get("ratio") not in HAPPYHORSE_RATIOS:
                raise ValueError("HappyHorse 参考生视频画面比例仅支持 16:9 / 9:16 / 1:1 / 4:3 / 3:4")
            if duration not in HAPPYHORSE_DURATIONS:
                raise ValueError("HappyHorse 参考生视频时长仅支持 3 到 15 秒")
            for index, image_url in enumerate(reference_images, start=1):
                await _validate_happyhorse_reference_image(image_url, f"参考图{index}")
            return

        if request.task_kind == "video_edit_global":
            _normalize_happyhorse_prompt(request.prompt, required=True)
            base_video = self._video_edit_base_video_url(request)
            if not base_video:
                raise ValueError("HappyHorse 视频编辑必须且仅能提供1个待编辑视频")
            reference_images = self._video_edit_reference_image_urls(request)
            if len(reference_images) > 5:
                raise ValueError("HappyHorse 视频编辑最多支持5张参考图")
            if params.get("resolution") not in HAPPYHORSE_RESOLUTIONS:
                raise ValueError("HappyHorse 视频编辑分辨率仅支持 720P / 1080P")
            if params.get("audio_setting") is not None and params.get("audio_setting") not in HAPPYHORSE_VIDEO_EDIT_AUDIO_SETTINGS:
                raise ValueError("HappyHorse 视频编辑声音设置仅支持 auto / origin")
            await _validate_happyhorse_video_edit_video(base_video, "待编辑视频")
            for index, image_url in enumerate(reference_images, start=1):
                await _validate_happyhorse_video_edit_reference_image(image_url, f"参考图{index}")
            return

        raise ValueError(f"HappyHorse 暂不支持任务类型: {request.task_kind}")

    async def submit(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> VideoSubmitResult:
        service = self._service(request)
        return await service.create_task(self.build_provider_payload(request, seed_offset))

    async def fetch(self, request: NormalizedVideoTaskRequest, task_id: str) -> VideoStatusResult:
        service = self._service(request)
        return await service.get_task_status(task_id, request.project_id)

    def build_provider_payload(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> Dict[str, Any]:
        params = dict(request.normalized_params)
        if params.get("seed") is not None:
            params["seed"] = int(params["seed"]) + seed_offset

        if request.task_kind == "text_to_video":
            payload = {
                "model": request.model_id,
                "input": {"prompt": _normalize_happyhorse_prompt(request.prompt, required=True)},
                "parameters": {"watermark": bool(params.get("watermark", False))},
            }
            for key in ("resolution", "ratio", "duration", "seed"):
                if params.get(key) is not None:
                    payload["parameters"][key] = params[key]
            return payload

        if request.task_kind == "image_to_video":
            prompt = _normalize_happyhorse_prompt(request.prompt, required=False)
            payload = {
                "model": request.model_id,
                "input": {
                    "media": [{"type": "first_frame", "url": (request.input_assets.get("first_frame") or [None])[0]}],
                },
                "parameters": {"watermark": bool(params.get("watermark", False))},
            }
            if prompt:
                payload["input"]["prompt"] = prompt
            for key in ("resolution", "duration", "seed"):
                if params.get(key) is not None:
                    payload["parameters"][key] = params[key]
            return payload

        if request.task_kind == "reference_to_video":
            payload = {
                "model": request.model_id,
                "input": {
                    "prompt": _normalize_happyhorse_prompt(request.prompt, required=True),
                    "media": [
                        {"type": "reference_image", "url": url}
                        for url in self._reference_image_urls(request)
                    ],
                },
                "parameters": {"watermark": bool(params.get("watermark", False))},
            }
            for key in ("resolution", "ratio", "duration", "seed"):
                if params.get(key) is not None:
                    payload["parameters"][key] = params[key]
            return payload

        if request.task_kind == "video_edit_global":
            media = [{"type": "video", "url": self._video_edit_base_video_url(request)}]
            media.extend(
                {"type": "reference_image", "url": url}
                for url in self._video_edit_reference_image_urls(request)
            )
            payload = {
                "model": request.model_id,
                "input": {
                    "prompt": _normalize_happyhorse_prompt(request.prompt, required=True),
                    "media": media,
                },
                "parameters": {"watermark": bool(params.get("watermark", False))},
            }
            for key in ("resolution", "audio_setting", "seed"):
                if params.get(key) is not None:
                    payload["parameters"][key] = params[key]
            return payload

        raise ValueError(f"HappyHorse 暂不支持任务类型: {request.task_kind}")


class KlingVideoAdapter(BaseVideoProviderAdapter):
    provider = "kling"

    async def validate(self, request: NormalizedVideoTaskRequest) -> None:
        params = request.normalized_params
        assets = request.input_assets
        element_ids = _parse_element_ids(params.get("element_ids"))

        if params.get("seed") is not None and not (0 <= int(params["seed"]) <= SEED_MAX):
            raise ValueError("随机种子必须在 0 到 2147483647 之间")
        if params.get("mode") and params["mode"] not in KLING_MODE_VALUES:
            raise ValueError("Kling 画质模式仅支持 pro / std")
        if params.get("aspect_ratio") and params["aspect_ratio"] not in KLING_ASPECT_RATIO_VALUES:
            raise ValueError("Kling 画面比例仅支持 16:9 / 9:16 / 1:1")
        if request.prompt and len(request.prompt) > KLANG_DOC_MAX_PROMPT:
            raise ValueError("Kling 提示词长度不能超过2500字符")

        has_video_input = bool(assets.get("reference_videos") or assets.get("base_video"))
        min_duration, max_duration = (3, 10) if has_video_input else (3, 15)
        duration = int(params.get("duration") or 5)
        if not (min_duration <= duration <= max_duration):
            raise ValueError(f"Kling 当前场景的视频时长必须在 {min_duration} 到 {max_duration} 秒之间")

        if request.task_kind == "text_to_video":
            if request.narrative_mode == "multi_shot_customize":
                segments = params.get("multi_prompt_segments") or []
                if not (1 <= len(segments) <= 6):
                    raise ValueError("Kling 自定义分镜模式需要 1 到 6 个片段")
                if any(not str(segment.get("prompt", "")).strip() for segment in segments):
                    raise ValueError("Kling 自定义分镜的每个片段都需要填写提示词")
                if any(len(str(segment.get("prompt", ""))) > 512 for segment in segments):
                    raise ValueError("Kling 自定义分镜的单条提示词长度不能超过512字符")
                if any(not (1 <= int(segment.get("duration") or 0) <= duration) for segment in segments):
                    raise ValueError("Kling 自定义分镜片段时长必须在 1 到总时长之间")
            elif not request.prompt:
                raise ValueError("文生视频需要输入提示词")
            if not params.get("aspect_ratio"):
                raise ValueError("Kling 文生视频必须指定画面比例")
            return

        if request.task_kind == "image_to_video":
            if not assets.get("first_frame"):
                raise ValueError("Kling 首帧生视频需要首帧图")
            await _validate_kling_image(assets["first_frame"][0], "首帧图")
            if len(element_ids) > 3:
                raise ValueError("Kling 首帧生视频最多支持 3 个主体ID")
            return

        if request.task_kind == "keyframe_to_video":
            if not assets.get("first_frame") or not assets.get("last_frame"):
                raise ValueError("Kling 首尾帧生视频需要首帧图和尾帧图")
            await _validate_kling_image(assets["first_frame"][0], "首帧图")
            await _validate_kling_image(assets["last_frame"][0], "尾帧图")
            if len(element_ids) > 3:
                raise ValueError("Kling 首尾帧生视频最多支持 3 个主体ID")
            return

        if request.task_kind == "reference_to_video":
            reference_images = assets.get("reference_images") or []
            reference_videos = assets.get("reference_videos") or []
            first_frame = assets.get("first_frame") or []
            if not reference_images and not reference_videos:
                raise ValueError("Kling 参考生视频至少需要参考图片或参考视频")
            if len(reference_videos) > 1:
                raise ValueError("Kling 参考生视频最多支持 1 个参考视频")
            if first_frame and not reference_videos:
                raise ValueError("Kling 的首帧参考模式需要同时提供参考视频")
            if reference_videos and first_frame and reference_images:
                raise ValueError("Kling 参考生视频不支持 feature + first_frame + refer 同时组合")
            if first_frame and len(first_frame) > 1:
                raise ValueError("Kling 首帧参考模式只支持 1 张首帧")
            max_reference_total = 4 if reference_videos else 7
            if len(reference_images) + len(element_ids) > max_reference_total:
                raise ValueError(f"Kling 当前组合下参考图片和主体ID总数最多支持 {max_reference_total} 个")
            if not first_frame and not params.get("aspect_ratio"):
                raise ValueError("Kling 参考生视频在未提供首帧时必须指定画面比例")
            for index, url in enumerate(reference_images, start=1):
                await _validate_kling_image(url, f"参考图{index}")
            for index, url in enumerate(reference_videos, start=1):
                await _validate_kling_video(url, f"参考视频{index}")
            if first_frame:
                await _validate_kling_image(first_frame[0], "首帧参考图")
            return

        if request.task_kind == "video_edit_global":
            base_video = assets.get("base_video") or []
            reference_images = assets.get("reference_images") or []
            if len(base_video) != 1:
                raise ValueError("Kling 视频编辑需要且仅支持 1 个输入视频")
            if len(reference_images) + len(element_ids) > 4:
                raise ValueError("Kling 视频编辑中参考图和主体ID总数最多支持 4 个")
            if not request.prompt:
                raise ValueError("Kling 视频编辑需要输入提示词")
            await _validate_kling_video(base_video[0], "输入视频")
            for index, url in enumerate(reference_images, start=1):
                await _validate_kling_image(url, f"参考图{index}")
            return

        raise ValueError(f"Kling 暂不支持任务类型: {request.task_kind}")

    async def submit(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> VideoSubmitResult:
        payload = self.build_provider_payload(request, seed_offset)
        service = DashScopeGenericVideoService("kling", request.key_profile)
        return await service.create_task(payload)

    async def fetch(self, request: NormalizedVideoTaskRequest, task_id: str) -> VideoStatusResult:
        service = DashScopeGenericVideoService("kling", request.key_profile)
        return await service.get_task_status(task_id, request.project_id)

    def build_provider_payload(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> Dict[str, Any]:
        params = dict(request.normalized_params)
        element_ids = _parse_element_ids(params.get("element_ids"))
        if params.get("seed") is not None:
            params["seed"] = int(params["seed"]) + seed_offset

        input_data: Dict[str, Any] = {}
        parameters: Dict[str, Any] = {
            "mode": params.get("mode", "pro"),
            "duration": int(params.get("duration") or 5),
            "watermark": bool(params.get("watermark", False)),
        }
        if "audio" in params:
            parameters["audio"] = bool(params.get("audio", True))
        if params.get("aspect_ratio"):
            parameters["aspect_ratio"] = params["aspect_ratio"]

        if request.task_kind == "text_to_video":
            if request.narrative_mode == "multi_shot_intelligence":
                input_data["prompt"] = request.prompt
                input_data["multi_shot"] = True
                input_data["shot_type"] = "intelligence"
                input_data["multi_prompt"] = []
                input_data["media"] = []
                input_data["element_list"] = []
            elif request.narrative_mode == "multi_shot_customize":
                input_data["prompt"] = ""
                input_data["multi_shot"] = True
                input_data["shot_type"] = "customize"
                input_data["multi_prompt"] = [
                    {
                        "index": index,
                        "prompt": segment["prompt"],
                        "duration": segment["duration"],
                    }
                    for index, segment in enumerate(params.get("multi_prompt_segments") or [])
                ]
                input_data["media"] = []
                input_data["element_list"] = []
            else:
                input_data["prompt"] = request.prompt
        elif request.task_kind == "image_to_video":
            input_data["prompt"] = request.prompt
            input_data["media"] = [{"type": "first_frame", "url": (request.input_assets.get("first_frame") or [None])[0]}]
            if element_ids:
                input_data["element_list"] = [{"element_id": value} for value in element_ids]
        elif request.task_kind == "keyframe_to_video":
            input_data["prompt"] = request.prompt
            input_data["media"] = [
                {"type": "first_frame", "url": (request.input_assets.get("first_frame") or [None])[0]},
                {"type": "last_frame", "url": (request.input_assets.get("last_frame") or [None])[0]},
            ]
            if element_ids:
                input_data["element_list"] = [{"element_id": value} for value in element_ids]
        elif request.task_kind == "reference_to_video":
            input_data["prompt"] = request.prompt
            media: List[Dict[str, Any]] = []
            if request.input_assets.get("reference_videos"):
                for url in request.input_assets["reference_videos"][:1]:
                    item: Dict[str, Any] = {"type": "feature", "url": url}
                    if params.get("keep_original_sound"):
                        item["keep_original_sound"] = "yes"
                    media.append(item)
            for url in request.input_assets.get("reference_images") or []:
                media.append({"type": "refer", "url": url})
            if request.input_assets.get("first_frame"):
                media.append({"type": "first_frame", "url": request.input_assets["first_frame"][0]})
            input_data["media"] = media
            input_data["element_list"] = [{"element_id": value} for value in element_ids]
            input_data["multi_shot"] = False
            input_data["shot_type"] = "intelligence"
            input_data["multi_prompt"] = []
        elif request.task_kind == "video_edit_global":
            input_data["prompt"] = request.prompt
            media = []
            base_video_url = (request.input_assets.get("base_video") or [None])[0]
            base_item: Dict[str, Any] = {"type": "base", "url": base_video_url}
            if params.get("keep_original_sound"):
                base_item["keep_original_sound"] = "yes"
            media.append(base_item)
            for url in request.input_assets.get("reference_images") or []:
                media.append({"type": "refer", "url": url})
            input_data["media"] = media
            input_data["element_list"] = [{"element_id": value} for value in element_ids]

        return {"model": request.model_id, "input": input_data, "parameters": parameters}


class ViduVideoAdapter(BaseVideoProviderAdapter):
    provider = "vidu"

    async def validate(self, request: NormalizedVideoTaskRequest) -> None:
        params = request.normalized_params
        assets = request.input_assets
        duration = int(params["duration"]) if params.get("duration") is not None else 5

        if params.get("seed") is not None and not (0 <= int(params["seed"]) <= SEED_MAX):
            raise ValueError("随机种子必须在 0 到 2147483647 之间")
        if request.prompt and len(request.prompt) > VIDU_DOC_MAX_PROMPT:
            raise ValueError("Vidu 提示词长度不能超过5000字符")
        allowed_resolutions = set(VIDU_RESOLUTION_VALUES)
        if request.task_kind == "image_to_video" and "viduq2" in request.model_id:
            allowed_resolutions = {"720P", "1080P"}
        if params.get("resolution") and params["resolution"] not in allowed_resolutions:
            allowed_text = " / ".join(sorted(allowed_resolutions))
            raise ValueError(f"当前 Vidu 模型的分辨率档位仅支持 {allowed_text}")
        if params.get("size"):
            size_options = VIDU_REFERENCE_SIZE_OPTIONS if request.task_kind == "reference_to_video" else VIDU_COMMON_SIZE_OPTIONS
            resolution = params.get("resolution") or "720P"
            if params["size"] not in size_options.get(resolution, set()):
                raise ValueError("当前分辨率档位下不支持该输出尺寸")

        if request.task_kind == "text_to_video":
            if not request.prompt:
                raise ValueError("Vidu 文生视频需要输入提示词")
        elif request.task_kind == "image_to_video":
            if not assets.get("first_frame"):
                raise ValueError("Vidu 首帧生视频需要首帧图")
            await _validate_vidu_image(assets["first_frame"][0], "首帧图")
        elif request.task_kind == "keyframe_to_video":
            if not request.prompt:
                raise ValueError("Vidu 首尾帧生视频需要输入提示词")
            if not assets.get("first_frame") or not assets.get("last_frame"):
                raise ValueError("Vidu 首尾帧生视频需要首帧图和尾帧图")
            first_meta = await _validate_vidu_image(assets["first_frame"][0], "首帧图")
            last_meta = await _validate_vidu_image(assets["last_frame"][0], "尾帧图")
            first_pixels = first_meta["width"] * first_meta["height"]
            last_pixels = last_meta["width"] * last_meta["height"]
            pixel_ratio = first_pixels / last_pixels if last_pixels else 0
            if not (0.8 <= pixel_ratio <= 1.25):
                raise ValueError("Vidu 首尾帧的总像素比值需在 0.8 到 1.25 之间")
        elif request.task_kind == "reference_to_video":
            if not request.prompt:
                raise ValueError("Vidu 参考生视频需要输入提示词")
            image_count = len(assets.get("reference_images") or [])
            video_count = len(assets.get("reference_videos") or [])
            if image_count == 0:
                raise ValueError("Vidu 参考生视频至少需要 1 张参考图")
            if request.model_id == "vidu/viduq2_reference2video":
                if video_count > 0:
                    raise ValueError("该 Vidu 模型仅支持参考图，不支持参考视频")
                if image_count > 7:
                    raise ValueError("该 Vidu 模型最多支持 7 张参考图")
                if duration == 0:
                    raise ValueError("该 Vidu 模型不支持自动规划时长，请填写 1 到 10 秒")
            else:
                if video_count > 2:
                    raise ValueError("该 Vidu 模型最多支持 2 个参考视频")
                if video_count > 0 and image_count > 4:
                    raise ValueError("参考图 + 视频组合模式下最多支持 4 张参考图")
                if video_count == 0 and image_count > 7:
                    raise ValueError("仅参考图模式下最多支持 7 张参考图")
            for index, url in enumerate(assets.get("reference_images") or [], start=1):
                await _validate_vidu_image(url, f"参考图{index}")
            for index, url in enumerate(assets.get("reference_videos") or [], start=1):
                await _validate_vidu_video(url, f"参考视频{index}")
        else:
            raise ValueError(f"Vidu 暂不支持任务类型: {request.task_kind}")

        if request.task_kind == "reference_to_video":
            if not (0 <= duration <= 10):
                raise ValueError("Vidu 参考生视频时长必须在 0 到 10 秒之间")
        elif "viduq3" in request.model_id:
            if not (1 <= duration <= 16):
                raise ValueError("Vidu Q3 系列时长必须在 1 到 16 秒之间")
        elif not (1 <= duration <= 10):
            raise ValueError("Vidu Q2 系列时长必须在 1 到 10 秒之间")

    async def submit(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> VideoSubmitResult:
        payload = self.build_provider_payload(request, seed_offset)
        service = DashScopeGenericVideoService("vidu", request.key_profile)
        return await service.create_task(payload)

    async def fetch(self, request: NormalizedVideoTaskRequest, task_id: str) -> VideoStatusResult:
        service = DashScopeGenericVideoService("vidu", request.key_profile)
        return await service.get_task_status(task_id, request.project_id)

    def build_provider_payload(self, request: NormalizedVideoTaskRequest, seed_offset: int = 0) -> Dict[str, Any]:
        params = dict(request.normalized_params)
        if params.get("seed") is not None:
            params["seed"] = int(params["seed"]) + seed_offset

        input_data: Dict[str, Any] = {"prompt": request.prompt}
        parameters: Dict[str, Any] = {
            "resolution": params.get("resolution", "720P"),
            "duration": int(params["duration"]) if params.get("duration") is not None else 5,
            "watermark": bool(params.get("watermark", False)),
        }
        if params.get("size"):
            parameters["size"] = params["size"]
        if "audio" in params and params["audio"] is not None:
            parameters["audio"] = bool(params["audio"])
        if params.get("seed") is not None:
            parameters["seed"] = params["seed"]

        if request.task_kind == "image_to_video":
            input_data["media"] = [{"type": "image", "url": (request.input_assets.get("first_frame") or [None])[0]}]
        elif request.task_kind == "keyframe_to_video":
            input_data["media"] = [
                {"type": "image", "url": (request.input_assets.get("first_frame") or [None])[0]},
                {"type": "image", "url": (request.input_assets.get("last_frame") or [None])[0]},
            ]
        elif request.task_kind == "reference_to_video":
            media: List[Dict[str, Any]] = []
            for url in request.input_assets.get("reference_videos") or []:
                media.append({"type": "video", "url": url})
            for url in request.input_assets.get("reference_images") or []:
                media.append({"type": "image", "url": url})
            input_data["media"] = media

        return {"model": request.model_id, "input": input_data, "parameters": parameters}


def infer_provider(model_id: Optional[str], task_kind: Optional[str]) -> str:
    if model_id and model_id.startswith("kling/"):
        return "kling"
    if model_id and model_id.startswith("vidu/"):
        return "vidu"
    if model_id and model_id.startswith("happyhorse-"):
        return "happyhorse"
    if task_kind in {"video_repainting", "video_edit_local"}:
        return "wan"
    return "wan"


def get_video_adapter(provider: str) -> BaseVideoProviderAdapter:
    if provider == "wan":
        return WanVideoAdapter()
    if provider == "happyhorse":
        return HappyHorseVideoAdapter()
    if provider == "kling":
        return KlingVideoAdapter()
    if provider == "vidu":
        return ViduVideoAdapter()
    raise ValueError(f"不支持的视频提供商: {provider}")
