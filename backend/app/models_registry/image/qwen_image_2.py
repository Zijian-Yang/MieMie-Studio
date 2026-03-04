"""
千问图像生成与编辑融合模型 (qwen-image-2.0-pro / qwen-image-2.0)

API 文档:
- 文生图: https://help.aliyun.com/zh/model-studio/qwen-image-api
- 图像编辑: https://help.aliyun.com/zh/model-studio/qwen-image-edit-api

模型特点：
- 同时支持文生图（纯文本输入）和图像编辑（1-3 张图 + 文本）
- 同步 HTTP 调用，不支持异步接口
- 单次请求支持输出 1-6 张图片（n 参数）
- 自由尺寸：总像素 512*512 至 2048*2048，默认 1024*1024
- 支持 negative_prompt, prompt_extend, watermark, seed

模型系列：
- qwen-image-2.0-pro: 文字渲染、真实质感、语义遵循能力更强
- qwen-image-2.0: 加速版，兼顾效果与响应速度
"""

from typing import Optional, List, Union
import httpx

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry,
    SizeOption, SizeConstraints,
)


QWEN_IMAGE_2_API_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)

QWEN_IMAGE_2_COMMON_SIZES = [
    SizeOption(width=1024, height=1024, label="1024×1024 正方形 1:1（默认）", aspect_ratio="1:1"),
    SizeOption(width=1536, height=1536, label="1536×1536 正方形 1:1", aspect_ratio="1:1"),
    SizeOption(width=768,  height=1152, label="768×1152 竖向 2:3",   aspect_ratio="2:3"),
    SizeOption(width=1152, height=768,  label="1152×768 横向 3:2",   aspect_ratio="3:2"),
    SizeOption(width=1024, height=1536, label="1024×1536 竖向 2:3",  aspect_ratio="2:3"),
    SizeOption(width=1536, height=1024, label="1536×1024 横向 3:2",  aspect_ratio="3:2"),
    SizeOption(width=960,  height=1280, label="960×1280 竖向 3:4",   aspect_ratio="3:4"),
    SizeOption(width=1280, height=960,  label="1280×960 横向 4:3",   aspect_ratio="4:3"),
    SizeOption(width=720,  height=1280, label="720×1280 竖向 9:16",  aspect_ratio="9:16"),
    SizeOption(width=1280, height=720,  label="1280×720 横向 16:9",  aspect_ratio="16:9"),
    SizeOption(width=1080, height=1920, label="1080×1920 竖向 9:16", aspect_ratio="9:16"),
    SizeOption(width=1920, height=1080, label="1920×1080 横向 16:9", aspect_ratio="16:9"),
]

QWEN_IMAGE_2_SIZE_CONSTRAINTS = SizeConstraints(
    min_pixels=512 * 512,
    max_pixels=2048 * 2048,
    min_ratio=512 / 2048,
    max_ratio=2048 / 512,
)


def _build_parameters() -> list:
    return [
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成或编辑的图片内容，支持中英文，最多800字符",
            required=True,
            constraint=ParameterConstraint(max_length=800),
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容，最多500字符",
            required=False,
            constraint=ParameterConstraint(max_length=500),
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="images",
            label="参考图片（可选）",
            type=ParameterType.IMAGE_URLS,
            description='不选为文生图模式；选1-3张则为图像编辑模式，多图时用"图1""图2"指代',
            required=False,
            constraint=ParameterConstraint(min_length=0, max_length=3),
            group="input",
            order=1,
        ),
        ModelParameter(
            name="n",
            label="生成数量",
            type=ParameterType.INTEGER,
            description="单次请求输出图片数量（1-6张）",
            required=False,
            default=1,
            constraint=ParameterConstraint(min_value=1, max_value=6),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="size",
            label="输出尺寸",
            type=ParameterType.SELECT,
            description="输出分辨率，总像素需在512×512至2048×2048之间",
            required=False,
            default="1024*1024",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1024*1024", label="1024×1024 正方形 1:1（默认）"),
                    SelectOption(value="1536*1536", label="1536×1536 正方形 1:1"),
                    SelectOption(value="768*1152",  label="768×1152 竖向 2:3"),
                    SelectOption(value="1152*768",  label="1152×768 横向 3:2"),
                    SelectOption(value="1024*1536", label="1024×1536 竖向 2:3"),
                    SelectOption(value="1536*1024", label="1536×1024 横向 3:2"),
                    SelectOption(value="960*1280",  label="960×1280 竖向 3:4"),
                    SelectOption(value="1280*960",  label="1280×960 横向 4:3"),
                    SelectOption(value="720*1280",  label="720×1280 竖向 9:16"),
                    SelectOption(value="1280*720",  label="1280×720 横向 16:9"),
                    SelectOption(value="1080*1920", label="1080×1920 竖向 9:16"),
                    SelectOption(value="1920*1080", label="1920×1080 横向 16:9"),
                ],
            ),
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词，使图像更多样化",
            required=False,
            default=True,
            group="generation",
            order=3,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            description="是否添加 Qwen-Image 水印",
            required=False,
            default=False,
            group="generation",
            order=4,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            description="固定种子可复现结果，留空为随机",
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="generation",
            advanced=True,
            order=5,
        ),
    ]


# ============ 模型定义 ============

QWEN_IMAGE_2_PRO_MODEL_INFO = ModelInfo(
    id="qwen-image-2.0-pro",
    name="千问图像 2.0 Pro",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="图像生成与编辑融合模型 Pro 版，文字渲染、真实质感、语义遵循能力更强。无参考图为文生图，有参考图为图像编辑",
    version="2.0-pro",

    api_model_name="qwen-image-2.0-pro",
    doc_url="https://help.aliyun.com/zh/model-studio/qwen-image-api",

    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
    ),

    size_constraints=QWEN_IMAGE_2_SIZE_CONSTRAINTS,
    common_sizes=QWEN_IMAGE_2_COMMON_SIZES,
    recommended=True,

    parameters=_build_parameters(),
)

QWEN_IMAGE_2_MODEL_INFO = ModelInfo(
    id="qwen-image-2.0",
    name="千问图像 2.0",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="图像生成与编辑融合模型加速版，兼顾效果与响应速度。无参考图为文生图，有参考图为图像编辑",
    version="2.0",

    api_model_name="qwen-image-2.0",
    doc_url="https://help.aliyun.com/zh/model-studio/qwen-image-api",

    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
    ),

    size_constraints=QWEN_IMAGE_2_SIZE_CONSTRAINTS,
    common_sizes=QWEN_IMAGE_2_COMMON_SIZES,

    parameters=_build_parameters(),
)


# ============ 服务实现 ============

class QwenImage2Service(BaseModelService[List[str]]):
    """
    千问图像 2.0 融合服务（qwen-image-2.0-pro / qwen-image-2.0）

    双模式：
    - 无图片输入 → 文生图
    - 有图片输入（1-3张） → 图像编辑
    """

    def __init__(self, model_info: ModelInfo = QWEN_IMAGE_2_PRO_MODEL_INFO):
        super().__init__(model_info)
        self._api_url = QWEN_IMAGE_2_API_URL

    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._api_url = (
                base_url.rstrip("/")
                + "/services/aigc/multimodal-generation/generation"
            )

    async def generate(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        negative_prompt: str = "",
        n: int = 1,
        size: str = "1024*1024",
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs,
    ) -> tuple[list[str], str]:
        """
        生成或编辑图片。

        Args:
            prompt: 提示词
            images: 参考图 URL 列表（空或 None 为文生图模式）
            negative_prompt: 负面提示词
            n: 输出图片数量 1-6
            size: 输出尺寸 "宽*高"
            prompt_extend: 智能改写
            watermark: 水印
            seed: 随机种子

        Returns:
            (图片URL列表, request_id)
        """
        content: list[dict] = []
        if images:
            for img_url in images[:3]:
                content.append({"image": img_url})
        content.append({"text": prompt})

        payload = {
            "model": self.model_info.api_model_name or self.model_info.id,
            "input": {
                "messages": [
                    {"role": "user", "content": content}
                ]
            },
            "parameters": {},
        }

        params = payload["parameters"]
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if size:
            params["size"] = size
        if n and n >= 1:
            params["n"] = n
        params["prompt_extend"] = prompt_extend
        params["watermark"] = watermark
        if seed is not None:
            params["seed"] = seed

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                self._api_url, json=payload, headers=headers
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                code = error_data.get("code", "")
                msg = error_data.get("message", response.text)
                raise Exception(f"API 调用失败 ({code}): {msg}")

            data = response.json()
            req_id = data.get("request_id", "")

            if "code" in data:
                raise Exception(
                    f"API 错误 ({data['code']}): {data.get('message', '未知错误')}"
                )

            choices = data.get("output", {}).get("choices", [])
            if not choices:
                raise Exception("API 返回空结果")

            urls = []
            for choice in choices:
                for item in choice.get("message", {}).get("content", []):
                    if "image" in item:
                        urls.append(item["image"])

            if not urls:
                raise Exception("API 未返回图片")

            return urls, req_id


# ============ 注册模型 ============

def register():
    registry.register(QWEN_IMAGE_2_PRO_MODEL_INFO, QwenImage2Service)
    registry.register(
        QWEN_IMAGE_2_MODEL_INFO,
        lambda info=QWEN_IMAGE_2_MODEL_INFO: QwenImage2Service(info),
    )


register()
