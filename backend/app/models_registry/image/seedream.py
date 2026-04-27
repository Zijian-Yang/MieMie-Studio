"""
火山引擎 Seedream 图片生成模型。

文档来源：
- docs/火山api文档/seedream文档.md

平台能力：
- 文生图
- 单/多图生图
- 组图生成
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..base import (
    BaseModelService,
    ModelCapability,
    ModelInfo,
    ModelParameter,
    ModelType,
    ParameterConstraint,
    ParameterType,
    SelectOption,
    SizeConstraints,
    SizeOption,
    registry,
)


SEEDREAM_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
SEEDREAM_MIN_TOTAL_PIXELS = 2560 * 1440
SEEDREAM_MAX_TOTAL_PIXELS = 4096 * 4096
SEEDREAM_MIN_RATIO = 1 / 16
SEEDREAM_MAX_RATIO = 16


SEEDREAM_2K_SIZES = [
    ("2048x2048", "2K 1:1 正方形 2048×2048", "1:1"),
    ("2304x1728", "2K 4:3 横向 2304×1728", "4:3"),
    ("1728x2304", "2K 3:4 竖向 1728×2304", "3:4"),
    ("2848x1600", "2K 16:9 横向 2848×1600", "16:9"),
    ("1600x2848", "2K 9:16 竖向 1600×2848", "9:16"),
    ("2496x1664", "2K 3:2 横向 2496×1664", "3:2"),
    ("1664x2496", "2K 2:3 竖向 1664×2496", "2:3"),
    ("3136x1344", "2K 21:9 横向 3136×1344", "21:9"),
]

SEEDREAM_3K_SIZES = [
    ("3072x3072", "3K 1:1 正方形 3072×3072", "1:1"),
    ("3456x2592", "3K 4:3 横向 3456×2592", "4:3"),
    ("2592x3456", "3K 3:4 竖向 2592×3456", "3:4"),
    ("4096x2304", "3K 16:9 横向 4096×2304", "16:9"),
    ("2304x4096", "3K 9:16 竖向 2304×4096", "9:16"),
    ("3744x2496", "3K 3:2 横向 3744×2496", "3:2"),
    ("2496x3744", "3K 2:3 竖向 2496×3744", "2:3"),
    ("4704x2016", "3K 21:9 横向 4704×2016", "21:9"),
]

SEEDREAM_4K_SIZES = [
    ("4096x4096", "4K 1:1 正方形 4096×4096", "1:1"),
    ("4704x3520", "4K 4:3 横向 4704×3520", "4:3"),
    ("3520x4704", "4K 3:4 竖向 3520×4704", "3:4"),
    ("5504x3040", "4K 16:9 横向 5504×3040", "16:9"),
    ("3040x5504", "4K 9:16 竖向 3040×5504", "9:16"),
    ("4992x3328", "4K 3:2 横向 4992×3328", "3:2"),
    ("3328x4992", "4K 2:3 竖向 3328×4992", "2:3"),
    ("6240x2656", "4K 21:9 横向 6240×2656", "21:9"),
]


def _size_option(value: str, label: str, aspect_ratio: str) -> SizeOption:
    width_text, height_text = value.split("x", 1)
    return SizeOption(width=int(width_text), height=int(height_text), label=label, aspect_ratio=aspect_ratio)


def _seedream_size_options(include_3k: bool) -> List[SelectOption]:
    options = [
        SelectOption(value="2K", label="2K（模型自动判断比例）"),
        *[SelectOption(value=value, label=label) for value, label, _ in SEEDREAM_2K_SIZES],
    ]
    if include_3k:
        options.extend(
            [
                SelectOption(value="3K", label="3K（模型自动判断比例，仅 5.0 lite）"),
                *[SelectOption(value=value, label=label) for value, label, _ in SEEDREAM_3K_SIZES],
            ]
        )
    options.extend(
        [
            SelectOption(value="4K", label="4K（模型自动判断比例）"),
            *[SelectOption(value=value, label=label) for value, label, _ in SEEDREAM_4K_SIZES],
        ]
    )
    return options


def _seedream_common_sizes(include_3k: bool) -> List[SizeOption]:
    raw_sizes = [*SEEDREAM_2K_SIZES, *(SEEDREAM_3K_SIZES if include_3k else []), *SEEDREAM_4K_SIZES]
    return [_size_option(value, label, aspect_ratio) for value, label, aspect_ratio in raw_sizes]


SEEDREAM_HELP = {
    "size": {
        "summary": "Seedream 支持 2K/3K/4K 规格档位或明确宽高像素值。",
        "limits": [
            "5.0 lite 支持 2K / 3K / 4K；4.5 支持 2K / 4K。",
            "自定义像素总像素需在 2560×1440 到 4096×4096 之间。",
            "自定义像素宽高比需在 1:16 到 16:1 之间。",
        ],
        "how_to_choose": [
            "只关心清晰度时选 2K/4K 档位，并在提示词里描述画幅。",
            "需要精确横竖比例时选择具体像素尺寸。",
        ],
    },
    "sequential": {
        "summary": "组图模式下 n 表示最多生成几张图。",
        "limits": [
            "n 范围 1-15。",
            "输入参考图数量 + 最终生成图片数量不能超过 15。",
        ],
    },
}


def _build_parameters(*, lite: bool) -> List[ModelParameter]:
    params = [
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="用于生成图片的提示词，建议不超过300个汉字或600个英文单词。",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="images",
            label="参考图片",
            type=ParameterType.IMAGE_URLS,
            description="支持 0-14 张 URL 或 Base64 图片输入。",
            required=False,
            constraint=ParameterConstraint(min_length=0, max_length=14),
            group="reference",
            order=1,
        ),
        ModelParameter(
            name="size",
            label="输出尺寸",
            type=ParameterType.SELECT,
            description="规格档位或宽高像素值。",
            help=SEEDREAM_HELP["size"],
            required=False,
            default="2048x2048",
            constraint=ParameterConstraint(options=_seedream_size_options(include_3k=lite)),
            group="size",
            order=1,
        ),
        ModelParameter(
            name="n",
            label="生成数量",
            type=ParameterType.INTEGER,
            description="普通模式固定单图；组图模式下表示最大组图数量。",
            help=SEEDREAM_HELP["sequential"],
            required=False,
            default=1,
            constraint=ParameterConstraint(min_value=1, max_value=15),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="提示词优化",
            type=ParameterType.BOOLEAN,
            description="开启后下发 optimize_prompt_options.mode=standard。",
            required=False,
            default=True,
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            description="是否在右下角添加“AI生成”水印。",
            required=False,
            default=False,
            group="generation",
            order=3,
        ),
    ]
    if lite:
        params.extend(
            [
                ModelParameter(
                    name="output_format",
                    label="输出格式",
                    type=ParameterType.SELECT,
                    description="5.0 lite 支持 jpeg 或 png。",
                    required=False,
                    default="jpeg",
                    constraint=ParameterConstraint(
                        options=[
                            SelectOption(value="jpeg", label="JPEG"),
                            SelectOption(value="png", label="PNG"),
                        ]
                    ),
                    group="advanced",
                    advanced=True,
                    order=1,
                ),
                ModelParameter(
                    name="web_search",
                    label="联网搜索",
                    type=ParameterType.BOOLEAN,
                    description="开启后模型可按提示词自主决定是否联网搜索。",
                    required=False,
                    default=False,
                    group="advanced",
                    advanced=True,
                    order=2,
                ),
            ]
        )
    return params


SEEDREAM_5_LITE_MODEL_INFO = ModelInfo(
    id="doubao-seedream-5.0-lite",
    name="豆包 Seedream 5.0 Lite",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="volcengine",
    description="火山引擎 Ark 图片生成模型，支持文生图、单/多图生图和组图生成，5.0 lite 支持 PNG 输出与联网搜索。",
    version="5.0-lite",
    api_model_name="doubao-seedream-5-0-260128",
    api_endpoint=SEEDREAM_API_URL,
    doc_url="docs/火山api文档/seedream文档.md",
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_reference_images=True,
        max_reference_images=14,
        supports_search=True,
        supports_tools=True,
    ),
    size_constraints=SizeConstraints(
        min_pixels=SEEDREAM_MIN_TOTAL_PIXELS,
        max_pixels=SEEDREAM_MAX_TOTAL_PIXELS,
        min_ratio=SEEDREAM_MIN_RATIO,
        max_ratio=SEEDREAM_MAX_RATIO,
    ),
    common_sizes=_seedream_common_sizes(include_3k=True),
    parameters=_build_parameters(lite=True),
)


SEEDREAM_45_MODEL_INFO = ModelInfo(
    id="doubao-seedream-4.5",
    name="豆包 Seedream 4.5",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="volcengine",
    description="火山引擎 Ark 图片生成模型，支持文生图、单/多图生图和组图生成。",
    version="4.5",
    api_model_name="doubao-seedream-4-5-251128",
    api_endpoint=SEEDREAM_API_URL,
    doc_url="docs/火山api文档/seedream文档.md",
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_reference_images=True,
        max_reference_images=14,
    ),
    size_constraints=SizeConstraints(
        min_pixels=SEEDREAM_MIN_TOTAL_PIXELS,
        max_pixels=SEEDREAM_MAX_TOTAL_PIXELS,
        min_ratio=SEEDREAM_MIN_RATIO,
        max_ratio=SEEDREAM_MAX_RATIO,
    ),
    common_sizes=_seedream_common_sizes(include_3k=False),
    parameters=_build_parameters(lite=False),
)


class SeedreamImageService(BaseModelService[List[str]]):
    """火山引擎 Seedream 图片生成服务。"""

    def __init__(self, model_info: ModelInfo = SEEDREAM_5_LITE_MODEL_INFO):
        super().__init__(model_info)
        self._api_url = SEEDREAM_API_URL

    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._api_url = base_url.rstrip("/") + "/api/v3/images/generations"

    def build_payload(
        self,
        *,
        prompt: str,
        images: Optional[List[str]] = None,
        size: Optional[str] = None,
        n: int = 1,
        task_kind: str = "text_to_image",
        prompt_extend: bool = True,
        watermark: bool = False,
        output_format: Optional[str] = None,
        web_search: bool = False,
    ) -> Dict[str, Any]:
        normalized_images = [url for url in (images or []) if url]
        sequential_enabled = task_kind == "sequential_generation"
        payload: Dict[str, Any] = {
            "model": self.model_info.api_model_name or self.model_info.id,
            "prompt": prompt,
            "size": size or "2048x2048",
            "sequential_image_generation": "auto" if sequential_enabled else "disabled",
            "response_format": "url",
            "stream": False,
            "watermark": bool(watermark),
        }
        if normalized_images:
            payload["image"] = normalized_images[0] if len(normalized_images) == 1 else normalized_images
        if sequential_enabled:
            payload["sequential_image_generation_options"] = {"max_images": int(n or 1)}
        if prompt_extend:
            payload["optimize_prompt_options"] = {"mode": "standard"}
        if output_format and self.model_info.id == "doubao-seedream-5.0-lite":
            payload["output_format"] = output_format
        if web_search and self.model_info.id == "doubao-seedream-5.0-lite":
            payload["tools"] = [{"type": "web_search"}]
        return payload

    async def generate(
        self,
        *,
        prompt: str,
        images: Optional[List[str]] = None,
        size: Optional[str] = None,
        n: int = 1,
        task_kind: str = "text_to_image",
        prompt_extend: bool = True,
        watermark: bool = False,
        output_format: Optional[str] = None,
        web_search: bool = False,
        **kwargs,
    ) -> Tuple[List[str], str, Dict[str, Any]]:
        if not self._api_key:
            raise ValueError("火山引擎 API Key 未配置")

        payload = self.build_payload(
            prompt=prompt,
            images=images,
            size=size,
            n=n,
            task_kind=task_kind,
            prompt_extend=prompt_extend,
            watermark=watermark,
            output_format=output_format,
            web_search=web_search,
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(self._api_url, headers=headers, json=payload)

        try:
            result = response.json()
        except Exception as exc:
            raise RuntimeError(f"火山引擎返回非 JSON 响应: {getattr(response, 'text', '')}") from exc

        request_id = (
            response.headers.get("x-tt-logid")
            or response.headers.get("X-Tt-Logid")
            or response.headers.get("x-request-id")
            or result.get("request_id")
            or ""
        )
        if response.status_code >= 400:
            error = result.get("error") or {}
            message = error.get("message") or result.get("message") or getattr(response, "text", "")
            code = error.get("code") or result.get("code") or f"HTTP {response.status_code}"
            raise RuntimeError(f"火山引擎调用失败 ({code}): {message}")

        if result.get("error"):
            error = result["error"]
            raise RuntimeError(f"火山引擎调用失败 ({error.get('code', '')}): {error.get('message', '未知错误')}")

        urls: List[str] = []
        item_errors: List[Dict[str, Any]] = []
        for index, item in enumerate(result.get("data") or []):
            if item.get("url"):
                urls.append(item["url"])
                continue
            if item.get("error"):
                error = item["error"]
                item_errors.append(
                    {
                        "index": index,
                        "code": error.get("code"),
                        "message": error.get("message"),
                    }
                )

        if not urls and not item_errors:
            raise RuntimeError("火山引擎未返回图片")

        meta = {
            "provider": "volcengine",
            "request_id": request_id,
            "model": result.get("model"),
            "created": result.get("created"),
            "usage": result.get("usage") or {},
            "tools": result.get("tools") or [],
            "item_errors": item_errors,
            "raw_response": result,
        }
        return urls, request_id, meta


registry.register(SEEDREAM_5_LITE_MODEL_INFO, SeedreamImageService)
registry.register(SEEDREAM_45_MODEL_INFO, SeedreamImageService)
