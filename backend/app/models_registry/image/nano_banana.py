"""
Google Gemini Nano Banana 原生图片生成模型。

文档来源：
- docs/Google模型api文档.md/nano-banana文档.md
- https://ai.google.dev/gemini-api/docs/image-generation
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.remote_media_validation import download_remote_bytes

from ..base import (
    BaseModelService,
    ModelCapability,
    ModelInfo,
    ModelParameter,
    ModelType,
    ParameterConstraint,
    ParameterType,
    SelectOption,
    registry,
)


GOOGLE_GENERATE_CONTENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GOOGLE_INLINE_IMAGE_LIMIT_BYTES = 20 * 1024 * 1024

NANO_BANANA_2_ASPECT_RATIOS = [
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
]
NANO_BANANA_PRO_ASPECT_RATIOS = [
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
]
NANO_BANANA_2_IMAGE_SIZES = ["512", "1K", "2K", "4K"]
NANO_BANANA_PRO_IMAGE_SIZES = ["1K", "2K", "4K"]


NANO_BANANA_HELP = {
    "aspect_ratio": {
        "summary": "控制输出图片比例。",
        "meaning": "Gemini imageConfig.aspectRatio 只指定比例，清晰度由 image_size 决定。",
        "limits": [
            "Nano Banana 2 额外支持 1:4、1:8、4:1、8:1。",
            "Nano Banana Pro 不支持极窄或极宽比例。",
        ],
    },
    "image_size": {
        "summary": "控制输出清晰度档位。",
        "meaning": "Gemini imageConfig.imageSize 使用 512/1K/2K/4K 等档位，不直接传固定像素宽高。",
        "limits": [
            "512 仅 Nano Banana 2 支持。",
            "参数大小写敏感，必须使用 1K/2K/4K。",
        ],
    },
    "google_search_mode": {
        "summary": "允许模型使用 Google Search grounding。",
        "limits": [
            "Nano Banana Pro 仅开放 web grounding。",
            "Nano Banana 2 支持 web/image/web+image grounding。",
            "使用 image search 时需在结果详情保留来源链接。",
        ],
    },
}


def _select_options(values: List[str]) -> List[SelectOption]:
    return [SelectOption(value=value, label=value) for value in values]


def _build_parameters(*, flash: bool) -> List[ModelParameter]:
    aspect_ratios = NANO_BANANA_2_ASPECT_RATIOS if flash else NANO_BANANA_PRO_ASPECT_RATIOS
    image_sizes = NANO_BANANA_2_IMAGE_SIZES if flash else NANO_BANANA_PRO_IMAGE_SIZES
    search_options = [
        SelectOption(value="none", label="关闭"),
        SelectOption(value="web", label="Web Search"),
    ]
    if flash:
        search_options.extend(
            [
                SelectOption(value="image", label="Image Search"),
                SelectOption(value="web_and_image", label="Web + Image Search"),
            ]
        )

    params = [
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="用于生成或编辑图片的提示词。",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="images",
            label="参考图片",
            type=ParameterType.IMAGE_URLS,
            description="图像编辑时支持 1-14 张参考图片；文生图不传参考图。",
            required=False,
            constraint=ParameterConstraint(min_length=0, max_length=14),
            group="reference",
            order=1,
        ),
        ModelParameter(
            name="aspect_ratio",
            label="输出比例",
            type=ParameterType.SELECT,
            description="输出图片宽高比。",
            help=NANO_BANANA_HELP["aspect_ratio"],
            required=False,
            default="1:1",
            constraint=ParameterConstraint(options=_select_options(aspect_ratios)),
            group="size",
            order=1,
        ),
        ModelParameter(
            name="image_size",
            label="清晰度",
            type=ParameterType.SELECT,
            description="输出清晰度档位。",
            help=NANO_BANANA_HELP["image_size"],
            required=False,
            default="1K",
            constraint=ParameterConstraint(options=_select_options(image_sizes)),
            group="size",
            order=2,
        ),
        ModelParameter(
            name="google_search_mode",
            label="Google Search",
            type=ParameterType.SELECT,
            description="联网 grounding 模式。",
            help=NANO_BANANA_HELP["google_search_mode"],
            required=False,
            default="none",
            constraint=ParameterConstraint(options=search_options),
            group="advanced",
            advanced=True,
            order=1,
        ),
    ]
    if flash:
        params.append(
            ModelParameter(
                name="thinking_level",
                label="思考强度",
                type=ParameterType.SELECT,
                description="Gemini 3.1 Flash Image 的 thinkingLevel。",
                required=False,
                default="minimal",
                constraint=ParameterConstraint(
                    options=[
                        SelectOption(value="minimal", label="minimal"),
                        SelectOption(value="high", label="high"),
                    ]
                ),
                group="advanced",
                advanced=True,
                order=2,
            )
        )
    return params


NANO_BANANA_2_MODEL_INFO = ModelInfo(
    id="nano-banana-2",
    name="Nano Banana 2",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="google",
    description="Google Gemini 3.1 Flash Image Preview，适合高效率图片生成与编辑，支持 Google Search grounding。",
    version="3.1-flash-image-preview",
    api_model_name="gemini-3.1-flash-image-preview",
    api_endpoint=GOOGLE_GENERATE_CONTENT_BASE_URL,
    doc_url="docs/Google模型api文档.md/nano-banana文档.md",
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        supports_reference_images=True,
        max_reference_images=14,
        supports_search=True,
        supports_tools=True,
        supports_thinking=True,
    ),
    parameters=_build_parameters(flash=True),
)


NANO_BANANA_PRO_MODEL_INFO = ModelInfo(
    id="nano-banana-pro",
    name="Nano Banana Pro",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="google",
    description="Google Gemini 3 Pro Image Preview，适合专业资产生产、复杂指令和高保真文字渲染。",
    version="3-pro-image-preview",
    api_model_name="gemini-3-pro-image-preview",
    api_endpoint=GOOGLE_GENERATE_CONTENT_BASE_URL,
    doc_url="docs/Google模型api文档.md/nano-banana文档.md",
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        supports_reference_images=True,
        max_reference_images=14,
        supports_search=True,
        supports_tools=True,
        supports_thinking=True,
    ),
    parameters=_build_parameters(flash=False),
)


def build_google_search_tools(search_mode: str, *, flash: bool) -> List[Dict[str, Any]]:
    mode = (search_mode or "none").strip()
    if mode == "none":
        return []
    if mode == "web":
        return [{"google_search": {}}]
    if not flash:
        return []
    if mode == "image":
        return [{"google_search": {"searchTypes": {"imageSearch": {}}}}]
    if mode == "web_and_image":
        return [{"google_search": {"searchTypes": {"webSearch": {}, "imageSearch": {}}}}]
    return []


def _inline_data_from_part(part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return part.get("inlineData") or part.get("inline_data")


def _mime_type_from_inline(inline: Dict[str, Any]) -> str:
    return inline.get("mimeType") or inline.get("mime_type") or "image/png"


def _first_text_value(data: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _grounding_link_from_payload(payload: Dict[str, Any], source_type: str) -> Optional[Dict[str, Any]]:
    uri = _first_text_value(payload, "uri", "url")
    if not uri:
        return None
    image_uri = _first_text_value(payload, "imageUri", "image_uri", "imageUrl", "image_url")
    return {
        "uri": uri,
        "title": _first_text_value(payload, "title") or uri,
        "source_type": source_type,
        "image_uri": image_uri,
    }


def extract_grounding_source_links(grounding_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从 Google groundingMetadata 中提取可展示的来源链接。"""

    links: List[Dict[str, Any]] = []
    seen = set()
    for grounding in grounding_metadata:
        chunks = grounding.get("groundingChunks") or grounding.get("grounding_chunks") or []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            candidates = [
                (chunk.get("web"), "web"),
                (chunk.get("image"), "image"),
                (chunk.get("retrievedContext") or chunk.get("retrieved_context"), "retrieved_context"),
            ]
            if chunk.get("uri") or chunk.get("url"):
                root_source_type = (
                    "image"
                    if _first_text_value(chunk, "imageUri", "image_uri", "imageUrl", "image_url")
                    else "web"
                )
                candidates.append((chunk, root_source_type))
            for payload, source_type in candidates:
                if not isinstance(payload, dict):
                    continue
                link = _grounding_link_from_payload(payload, source_type)
                if not link:
                    continue
                dedupe_key = (link["uri"], link.get("image_uri"))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                links.append(link)
    return links


class NanoBananaGenerationError(RuntimeError):
    """携带 Google 原始响应元信息的生成错误。"""

    def __init__(self, message: str, *, meta: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.meta = meta or {}
        self.error_code = error_code


class NanoBananaImageService(BaseModelService[List[Dict[str, Any]]]):
    """Google Gemini Nano Banana 图片生成服务。"""

    def __init__(self, model_info: ModelInfo = NANO_BANANA_2_MODEL_INFO):
        super().__init__(model_info)
        self._api_base_url = GOOGLE_GENERATE_CONTENT_BASE_URL

    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._api_base_url = base_url.rstrip("/")

    @property
    def _is_flash(self) -> bool:
        return self.model_info.id == "nano-banana-2"

    async def _reference_image_parts(self, images: Optional[List[str]]) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        total_bytes = 0
        for url in [item for item in (images or []) if item]:
            content, content_type = await download_remote_bytes(url)
            total_bytes += len(content)
            if total_bytes > GOOGLE_INLINE_IMAGE_LIMIT_BYTES:
                raise ValueError("Google Nano Banana 单次参考图总大小不能超过 20MB")
            mime_type = content_type.split(";", 1)[0].strip() or "image/png"
            encoded = base64.b64encode(content).decode("ascii")
            parts.append({"inline_data": {"mime_type": mime_type, "data": encoded}})
        return parts

    async def build_payload(
        self,
        *,
        prompt: str,
        images: Optional[List[str]] = None,
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
        google_search_mode: str = "none",
        thinking_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        content_parts = [{"text": prompt}] + await self._reference_image_parts(images)
        generation_config: Dict[str, Any] = {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
            },
        }
        if self._is_flash:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_level or "minimal",
                "includeThoughts": False,
            }

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": content_parts}],
            "generationConfig": generation_config,
        }
        tools = build_google_search_tools(google_search_mode, flash=self._is_flash)
        if tools:
            payload["tools"] = tools
        return payload

    async def generate(
        self,
        *,
        prompt: str,
        images: Optional[List[str]] = None,
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
        google_search_mode: str = "none",
        thinking_level: Optional[str] = None,
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        if not self._api_key:
            raise ValueError("Google Gemini API Key 未配置")

        payload = await self.build_payload(
            prompt=prompt,
            images=images,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            google_search_mode=google_search_mode,
            thinking_level=thinking_level,
        )
        api_model_name = self.model_info.api_model_name or self.model_info.id
        url = f"{self._api_base_url}/{api_model_name}:generateContent"
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        try:
            result = response.json()
        except Exception as exc:
            raise RuntimeError(f"Google Gemini 返回非 JSON 响应: {getattr(response, 'text', '')}") from exc

        request_id = (
            response.headers.get("x-request-id")
            or response.headers.get("x-goog-request-id")
            or response.headers.get("x-goog-trace-id")
            or result.get("request_id")
            or ""
        )
        if response.status_code >= 400 or result.get("error"):
            error = result.get("error") or {}
            code = error.get("code") or f"HTTP {response.status_code}"
            message = error.get("message") or getattr(response, "text", "")
            meta = {
                "provider": "google",
                "request_id": request_id,
                "model": api_model_name,
                "usage": result.get("usageMetadata") or result.get("usage") or {},
                "grounding_metadata": [],
                "grounding_source_links": [],
                "finish_reasons": [],
                "text_parts": [],
                "thought_count": 0,
                "raw_response": result,
            }
            raise NanoBananaGenerationError(
                f"Google Gemini 调用失败 ({code}): {message}",
                meta=meta,
                error_code=str(code),
            )

        images_out: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        grounding_metadata: List[Dict[str, Any]] = []
        finish_reasons: List[str] = []
        thought_count = 0

        for candidate in result.get("candidates") or []:
            if candidate.get("finishReason"):
                finish_reasons.append(candidate["finishReason"])
            if candidate.get("groundingMetadata"):
                grounding_metadata.append(candidate["groundingMetadata"])
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                if part.get("thought"):
                    thought_count += 1
                    continue
                if part.get("text"):
                    text_parts.append(part["text"])
                    continue
                inline = _inline_data_from_part(part)
                if not inline:
                    continue
                data_text = inline.get("data") or ""
                try:
                    decoded = base64.b64decode(data_text, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise RuntimeError("Google Gemini 返回的图片 base64 无法解码") from exc
                images_out.append(
                    {
                        "data": decoded,
                        "mime_type": _mime_type_from_inline(inline),
                        "thought_signature": part.get("thoughtSignature") or part.get("thought_signature"),
                    }
                )

        meta = {
            "provider": "google",
            "request_id": request_id,
            "model": api_model_name,
            "usage": result.get("usageMetadata") or result.get("usage") or {},
            "grounding_metadata": grounding_metadata,
            "grounding_source_links": extract_grounding_source_links(grounding_metadata),
            "finish_reasons": finish_reasons,
            "text_parts": text_parts,
            "thought_count": thought_count,
            "raw_response": result,
        }
        if not images_out:
            reason_text = "、".join(finish_reasons) if finish_reasons else "未知"
            raise NanoBananaGenerationError(
                f"Google Gemini 未返回有效图片（finishReason: {reason_text}）",
                meta=meta,
                error_code="NoImage",
            )
        return images_out, request_id, meta


registry.register(NANO_BANANA_2_MODEL_INFO, NanoBananaImageService)
registry.register(NANO_BANANA_PRO_MODEL_INFO, NanoBananaImageService)
