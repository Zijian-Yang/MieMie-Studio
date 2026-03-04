"""
千问文生图模型 (qwen-image-max, qwen-image-plus)

API 文档: https://help.aliyun.com/zh/model-studio/qwen-image-api-reference

模型特点：
- 同步 HTTP 调用（推荐），一次请求即出结果
- 每次固定生成 1 张图（n=1），通过 group_count 并发来批量生成
- 支持 negative_prompt, prompt_extend, watermark, seed
- qwen-image-max: 更高真实感与自然度，人物质感、纹理细节更优
- qwen-image-plus: 多样化艺术风格，擅长复杂文字渲染和图文混合布局
"""

from typing import Optional, List
import httpx

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry,
    SizeOption, SizeConstraints,
)


# ============ 共用常量 ============

QWEN_IMAGE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

QWEN_IMAGE_COMMON_SIZES = [
    SizeOption(width=1664, height=928,  label="1664×928 横向 16:9（默认）", aspect_ratio="16:9"),
    SizeOption(width=1472, height=1104, label="1472×1104 横向 4:3",       aspect_ratio="4:3"),
    SizeOption(width=1328, height=1328, label="1328×1328 正方形 1:1",     aspect_ratio="1:1"),
    SizeOption(width=1104, height=1472, label="1104×1472 竖向 3:4",       aspect_ratio="3:4"),
    SizeOption(width=928,  height=1664, label="928×1664 竖向 9:16",       aspect_ratio="9:16"),
]

QWEN_IMAGE_SIZE_CONSTRAINTS = SizeConstraints(
    min_pixels=928 * 928,
    max_pixels=1664 * 1664,
    min_ratio=928 / 1664,
    max_ratio=1664 / 928,
)


def _build_common_parameters() -> list:
    return [
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的图片内容，支持中英文，最多800字符",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容，最多500字符",
            required=False,
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="size",
            label="图片尺寸",
            type=ParameterType.SELECT,
            description="输出分辨率",
            required=False,
            default="1664*928",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1664*928",  label="1664×928 横向 16:9（默认）"),
                    SelectOption(value="1472*1104", label="1472×1104 横向 4:3"),
                    SelectOption(value="1328*1328", label="1328×1328 正方形 1:1"),
                    SelectOption(value="1104*1472", label="1104×1472 竖向 3:4"),
                    SelectOption(value="928*1664",  label="928×1664 竖向 9:16"),
                ]
            ),
            group="size",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词，使图像更多样化",
            required=False,
            default=True,
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            description="是否添加 Qwen-Image 水印",
            required=False,
            default=False,
            group="generation",
            order=2,
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
            order=3,
        ),
    ]


# ============ 模型定义 ============

QWEN_IMAGE_MAX_MODEL_INFO = ModelInfo(
    id="qwen-image-max",
    name="千问文生图 Max",
    type=ModelType.TEXT_TO_IMAGE,
    provider="dashscope",
    description="更高真实感与自然度，人物质感、纹理细节和文字渲染表现突出",
    version="max",

    api_model_name="qwen-image-max",
    doc_url="https://help.aliyun.com/zh/model-studio/qwen-image-api-reference",

    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=False,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
    ),

    size_constraints=QWEN_IMAGE_SIZE_CONSTRAINTS,
    common_sizes=QWEN_IMAGE_COMMON_SIZES,
    recommended=True,

    parameters=_build_common_parameters(),
)

QWEN_IMAGE_PLUS_MODEL_INFO = ModelInfo(
    id="qwen-image-plus",
    name="千问文生图 Plus",
    type=ModelType.TEXT_TO_IMAGE,
    provider="dashscope",
    description="多样化艺术风格，擅长复杂文字渲染和图文混合布局设计",
    version="plus",

    api_model_name="qwen-image-plus",
    doc_url="https://help.aliyun.com/zh/model-studio/qwen-image-api-reference",

    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=False,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
    ),

    size_constraints=QWEN_IMAGE_SIZE_CONSTRAINTS,
    common_sizes=QWEN_IMAGE_COMMON_SIZES,

    parameters=_build_common_parameters(),
)


# ============ 服务实现 ============

class QwenImageService(BaseModelService[List[str]]):
    """
    千问文生图服务（qwen-image-max / qwen-image-plus）

    使用同步 HTTP 调用，每次固定返回 1 张图。
    通过 group_count 并发多次调用来批量生成。
    """

    def __init__(self, model_info: ModelInfo = QWEN_IMAGE_MAX_MODEL_INFO):
        super().__init__(model_info)
        self._api_url = QWEN_IMAGE_API_URL

    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._api_url = base_url.rstrip('/') + "/services/aigc/multimodal-generation/generation"

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1664*928",
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> tuple[list[str], str]:
        """
        生成 1 张图片（同步调用）

        Returns:
            (包含一个URL的列表, request_id)
        """
        payload = {
            "model": self.model_info.api_model_name or self.model_info.id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ]
            },
            "parameters": {}
        }

        params = payload["parameters"]
        if negative_prompt:
            params["negative_prompt"] = negative_prompt
        if size:
            params["size"] = size
        params["n"] = 1
        params["prompt_extend"] = prompt_extend
        params["watermark"] = watermark
        if seed is not None:
            params["seed"] = seed

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._api_url, json=payload, headers=headers)

            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                code = error_data.get("code", "")
                msg = error_data.get("message", response.text)
                raise Exception(f"API 调用失败 ({code}): {msg}")

            data = response.json()
            req_id = data.get("request_id", "")

            if "code" in data:
                raise Exception(f"API 错误 ({data['code']}): {data.get('message', '未知错误')}")

            choices = data.get("output", {}).get("choices", [])
            if not choices:
                raise Exception("API 返回空结果")

            content = choices[0].get("message", {}).get("content", [])
            urls = [item["image"] for item in content if "image" in item]

            if not urls:
                raise Exception("API 未返回图片")

            return urls, req_id


# ============ 注册模型 ============

def register():
    registry.register(QWEN_IMAGE_MAX_MODEL_INFO, QwenImageService)
    registry.register(QWEN_IMAGE_PLUS_MODEL_INFO, lambda info=QWEN_IMAGE_PLUS_MODEL_INFO: QwenImageService(info))


register()
