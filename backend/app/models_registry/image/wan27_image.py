"""
万相 2.7 图像生成与编辑模型（wan2.7-image-pro / wan2.7-image）

文档来源：
- docs/阿里云模型api文档/万相-图像生成与编辑2.7.md

支持能力：
- 文生图
- 图像编辑 / 多图参考生成
- 交互式编辑（bbox_list）
- 组图生成（enable_sequential=true）
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
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
    TaskResult,
    TaskStatus,
    registry,
)


WAN27_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

WAN27_HELP_SIZE = {
    "summary": "输出尺寸参数，支持规格档位或自定义像素，两种方式不可混用。",
    "limits": [
        "wan2.7-image-pro：纯文生图可选 1K / 2K / 4K；带图片输入或组图时仅 1K / 2K。",
        "wan2.7-image：所有场景仅支持 1K / 2K。",
        "自定义像素时，宽高比需在 1:8 到 8:1 之间。",
    ],
    "how_to_choose": [
        "只有纯文生图且需要最高规格时再选 4K。",
        "有输入图时，规格档位会跟随最后一张输入图的宽高比缩放。",
        "需要精确控制版式时再切到自定义像素。",
    ],
    "examples": [
        "纯文生图海报：2K 或 4K。",
        "两张图融合编辑：2K，输出比例跟随最后一张图。",
    ],
}

WAN27_COMMON_PARAMS = [
    ModelParameter(
        name="prompt",
        label="提示词",
        type=ParameterType.TEXT,
        description="支持中英文，最长 5000 字符。",
        help={
            "summary": "描述希望生成或编辑后的画面内容。",
            "limits": ["最长 5000 字符，超出部分会被截断。"],
            "how_to_choose": [
                "多图输入时，可在提示词中按“图1、图2...”描述不同素材的作用。",
                "组图生成时，建议在提示词中清楚写出每张图的场景顺序与一致性要求。",
            ],
            "examples": [
                "把图2的涂鸦喷绘在图1的汽车上。",
                "电影感组图，四张图都保持同一只橘猫特征一致。",
            ],
        },
        required=True,
        group="basic",
        order=1,
    ),
    ModelParameter(
        name="images",
        label="输入图片",
        type=ParameterType.IMAGE_URLS,
        description="可输入 0-9 张图片，顺序会影响引用与输出。",
        help={
            "summary": "输入图片既可以作为编辑源，也可以作为多图参考来源。",
            "limits": [
                "最多 9 张图片。",
                "单张图宽高范围 240-8000 像素，宽高比 1:8 到 8:1，文件大小不超过 20MB。",
                "支持 JPEG / JPG / PNG（不支持透明通道）/ BMP / WEBP。",
            ],
            "how_to_choose": [
                "多图时请按业务顺序排列，最后一张图会影响规格档位下的输出比例。",
                "交互式编辑时，bbox_list 的索引必须和这里的图片顺序完全一致。",
            ],
        },
        required=False,
        constraint=ParameterConstraint(min_length=0, max_length=9),
        group="reference",
        order=1,
    ),
    ModelParameter(
        name="size",
        label="尺寸",
        type=ParameterType.STRING,
        description="规格档位（1K / 2K / 4K）或自定义像素（如 1536*1024）。",
        help=WAN27_HELP_SIZE,
        required=False,
        default="2K",
        group="size",
        order=1,
    ),
    ModelParameter(
        name="n",
        label="生成数量",
        type=ParameterType.INTEGER,
        description="普通模式表示输出张数，组图模式表示最大组图数。",
        help={
            "summary": "直接影响成功生成图片张数和费用。",
            "limits": [
                "普通模式：1-4，默认 4。",
                "组图模式：1-12，默认 12，实际返回数量由模型决定且不会超过 n。",
            ],
            "how_to_choose": [
                "普通生成建议先从 1 或 2 起步。",
                "组图模式请按故事段落数设置上限，例如四季组图通常填 4。",
            ],
        },
        default=4,
        constraint=ParameterConstraint(min_value=1, max_value=12),
        group="generation",
        order=1,
    ),
    ModelParameter(
        name="enable_sequential",
        label="组图模式",
        type=ParameterType.BOOLEAN,
        description="开启后生成同主题的多张组图。",
        help={
            "summary": "控制是否进入组图生成模式。",
            "limits": [
                "开启后，thinking_mode 不生效。",
                "开启后，n 代表最大组图数，范围为 1-12。",
            ],
            "how_to_choose": [
                "需要一组连续主题、角色一致的图片时开启。",
                "单张图或单次编辑不要开启。",
            ],
        },
        default=False,
        group="generation",
        order=2,
    ),
    ModelParameter(
        name="thinking_mode",
        label="思考模式",
        type=ParameterType.BOOLEAN,
        description="增强推理能力，提升纯文生图质量。",
        help={
            "summary": "仅在非组图且没有输入图片时生效。",
            "limits": [
                "有图片输入时无效。",
                "组图模式时无效。",
            ],
            "how_to_choose": [
                "纯文生图且提示词复杂时建议开启。",
                "图像编辑、交互式编辑、多图参考生成时无需开启。",
            ],
        },
        default=True,
        group="generation",
        order=3,
    ),
    ModelParameter(
        name="watermark",
        label="水印",
        type=ParameterType.BOOLEAN,
        description="是否在右下角添加 AI 生成水印。",
        required=False,
        default=False,
        group="generation",
        order=4,
    ),
    ModelParameter(
        name="seed",
        label="随机种子",
        type=ParameterType.INTEGER,
        description="相同 seed 可获得相对稳定的结果。",
        help={
            "summary": "用于增强可复现性，但不能保证像素级完全一致。",
            "limits": ["范围 0 到 2147483647。"],
        },
        required=False,
        constraint=ParameterConstraint(min_value=0, max_value=2147483647),
        group="generation",
        advanced=True,
        order=5,
    ),
    ModelParameter(
        name="bbox_list",
        label="交互式框选区域",
        type=ParameterType.TEXT,
        description="交互式编辑专用，长度需与输入图片数量一致。",
        help={
            "summary": "用于告诉模型每张图中哪些区域需要被引用或编辑。",
            "limits": [
                "列表长度必须与输入图片数量完全一致。",
                "每张图最多 2 个框。",
                "坐标格式为 [x1, y1, x2, y2]，使用原图绝对像素坐标。",
            ],
            "how_to_choose": [
                "不需要框选的图片位置传空数组 []。",
                "只在交互式编辑模式使用。",
            ],
        },
        required=False,
        group="advanced",
        advanced=True,
        order=1,
    ),
    ModelParameter(
        name="color_palette",
        label="颜色主题",
        type=ParameterType.TEXT,
        description="非组图模式可选，自定义 3-10 种颜色及占比。",
        help={
            "summary": "通过限定颜色和占比控制整体色彩倾向。",
            "limits": [
                "仅在非组图模式下可用。",
                "必须包含 3-10 种颜色。",
                "ratio 需精确到两位小数，所有比例总和必须为 100.00%。",
            ],
            "how_to_choose": [
                "需要保持海报、插画、品牌 KV 的色彩统一时使用。",
                "一般自然场景或照片感生成可以不设置。",
            ],
        },
        required=False,
        group="advanced",
        advanced=True,
        order=2,
    ),
]

WAN27_PRO_MODEL_INFO = ModelInfo(
    id="wan2.7-image-pro",
    name="万相 2.7 Image Pro",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="wan",
    description="支持文生图、图像编辑、交互式编辑、组图生成，纯文生图支持 4K。",
    version="2.7",
    api_model_name="wan2.7-image-pro",
    doc_url="docs/阿里云模型api文档/万相-图像生成与编辑2.7.md",
    capabilities=ModelCapability(
        supports_async=True,
        supports_batch=True,
        supports_seed=True,
        supports_watermark=True,
        supports_reference_images=True,
        max_reference_images=9,
    ),
    size_constraints=SizeConstraints(
        min_pixels=768 * 768,
        max_pixels=4096 * 4096,
        min_ratio=0.125,
        max_ratio=8.0,
    ),
    parameters=WAN27_COMMON_PARAMS,
)

WAN27_MODEL_INFO = ModelInfo(
    id="wan2.7-image",
    name="万相 2.7 Image",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="wan",
    description="万相 2.7 标准版，支持文生图、图像编辑、交互式编辑、组图生成，不支持 4K。",
    version="2.7",
    api_model_name="wan2.7-image",
    doc_url="docs/阿里云模型api文档/万相-图像生成与编辑2.7.md",
    capabilities=ModelCapability(
        supports_async=True,
        supports_batch=True,
        supports_seed=True,
        supports_watermark=True,
        supports_reference_images=True,
        max_reference_images=9,
    ),
    size_constraints=SizeConstraints(
        min_pixels=768 * 768,
        max_pixels=2048 * 2048,
        min_ratio=0.125,
        max_ratio=8.0,
    ),
    parameters=WAN27_COMMON_PARAMS,
)


class Wan27ImageService(BaseModelService[List[str]]):
    """万相 2.7 图像生成与编辑服务"""

    def __init__(self, model_info: ModelInfo = WAN27_PRO_MODEL_INFO):
        super().__init__(model_info)
        self._api_url = WAN27_API_URL
        self.last_request_id: Optional[str] = None
        self.last_usage: Dict[str, Any] = {}
        self.last_error_code: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.last_raw_output: Dict[str, Any] = {}
        self.last_payload: Dict[str, Any] = {}

    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._api_url = base_url.rstrip("/") + "/services/aigc/multimodal-generation/generation"

    def build_payload(
        self,
        *,
        prompt: str,
        images: Optional[List[str]] = None,
        size: str = "2K",
        n: int = 4,
        enable_sequential: bool = False,
        thinking_mode: Optional[bool] = None,
        color_palette: Optional[List[Dict[str, str]]] = None,
        bbox_list: Optional[List[List[List[int]]]] = None,
        watermark: bool = False,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        content: List[Dict[str, Any]] = []
        for image_url in images or []:
            content.append({"image": image_url})
        content.append({"text": prompt})

        parameters: Dict[str, Any] = {
            "size": size,
            "n": n,
            "watermark": watermark,
        }
        if enable_sequential:
            parameters["enable_sequential"] = True
        elif thinking_mode is not None:
            parameters["thinking_mode"] = thinking_mode
        if color_palette:
            parameters["color_palette"] = color_palette
        if bbox_list is not None:
            parameters["bbox_list"] = bbox_list
        if seed is not None:
            parameters["seed"] = seed

        return {
            "model": self.model_info.api_model_name,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": parameters,
        }

    async def create_task(self, **params) -> str:
        if not self._api_key:
            raise ValueError("API key 未配置")

        payload = self.build_payload(**params)
        self.last_payload = payload
        self.last_request_id = None
        self.last_usage = {}
        self.last_error_code = None
        self.last_error_message = None
        self.last_raw_output = {}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._api_url, headers=headers, json=payload)
        result = response.json()
        self.last_request_id = result.get("request_id")
        self.last_usage = result.get("usage") or {}
        self.last_raw_output = result.get("output") or {}
        self.last_error_code = result.get("code")
        self.last_error_message = result.get("message")

        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(self.last_error_message or f"HTTP {response.status_code}")

        task_id = (result.get("output") or {}).get("task_id")
        if not task_id:
            raise RuntimeError("万相2.7 未返回 task_id")
        return task_id

    async def get_task_status(self, task_id: str) -> TaskResult:
        if not self._api_key:
            raise ValueError("API key 未配置")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        status_url = self._api_url.rsplit("/services/", 1)[0] + f"/tasks/{task_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(status_url, headers=headers)
        result = response.json()

        request_id = result.get("request_id")
        usage = result.get("usage") or {}
        code = result.get("code")
        message = result.get("message")
        output = result.get("output") or {}
        task_status = output.get("task_status") or "UNKNOWN"

        if task_status in {"PENDING", "RUNNING"}:
            status = TaskStatus.PROCESSING
            image_urls = None
        elif task_status == "SUCCEEDED":
            status = TaskStatus.SUCCEEDED
            image_urls = [
                item.get("image")
                for choice in output.get("choices") or []
                for item in (choice.get("message") or {}).get("content") or []
                if item.get("type") == "image" and item.get("image")
            ]
        elif task_status == "CANCELED":
            status = TaskStatus.CANCELLED
            image_urls = None
        else:
            status = TaskStatus.FAILED
            image_urls = None

        return TaskResult(
            task_id=task_id,
            status=status,
            result=image_urls,
            error_message=message or code,
            metadata={
                "request_id": request_id,
                "usage": usage,
                "error_code": code,
                "error_message": message,
                "raw_output": output,
            },
        )

    async def generate(self, **params) -> List[str]:
        task_id = await self.create_task(**params)
        timeout_seconds = 300
        elapsed = 0
        while elapsed < timeout_seconds:
            status = await self.get_task_status(task_id)
            if status.status == TaskStatus.SUCCEEDED:
                return status.result or []
            if status.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                raise RuntimeError(status.error_message or "万相2.7 生成失败")
            await asyncio.sleep(2)
            elapsed += 2
        raise RuntimeError("万相2.7 生成超时")


registry.register(WAN27_PRO_MODEL_INFO, Wan27ImageService)
registry.register(WAN27_MODEL_INFO, Wan27ImageService)
