"""
通义千问图像编辑模型 (qwen-image-edit-plus / qwen-image-edit-max)

API 文档: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api

模型特点：
- 支持单图编辑和多图融合两种模式
- 单图编辑：输入1张图片+提示词，编辑图片内容
- 多图融合：输入2-3张图片+提示词，融合多张图片
- 支持输出1-6张图片 (plus/max)
- 支持负面提示词、智能改写、水印、种子
- 支持自定义输出尺寸 (plus/max)
- 不支持异步接口，仅同步调用

模型系列：
- qwen-image-edit-max: 最强版本，效果最好
- qwen-image-edit-plus: 标准版本
- qwen-image-edit: 基础版本（仅输出1张，不支持自定义尺寸/智能改写）

参数说明（根据 2026-02 官方文档）：
- n: 输出图片数量 1-6，默认1 (plus/max)
- negative_prompt: 负面提示词，最长500字符
- size: 输出分辨率 "宽*高"，宽高范围[512,2048] (plus/max)
- prompt_extend: 智能改写，默认True (plus/max)
- watermark: 水印，默认False
- seed: 随机种子，范围[0,2147483647]
"""

from typing import Optional, List, Union
from dashscope import MultiModalConversation

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption, SizeOption,
    BaseModelService, TaskResult, TaskStatus, registry
)
from app.services.oss import oss_service


# ============ 尺寸定义 ============

QWEN_IMAGE_EDIT_COMMON_SIZES = [
    SizeOption(width=1024, height=1024, label="1024×1024 方形 1:1", aspect_ratio="1:1"),
    SizeOption(width=1536, height=1536, label="1536×1536 方形 1:1", aspect_ratio="1:1"),
    SizeOption(width=1152, height=768, label="1152×768 横向 3:2", aspect_ratio="3:2"),
    SizeOption(width=768, height=1152, label="768×1152 竖向 2:3", aspect_ratio="2:3"),
    SizeOption(width=1536, height=1024, label="1536×1024 横向 3:2", aspect_ratio="3:2"),
    SizeOption(width=1024, height=1536, label="1024×1536 竖向 2:3", aspect_ratio="2:3"),
    SizeOption(width=1280, height=960, label="1280×960 横向 4:3", aspect_ratio="4:3"),
    SizeOption(width=960, height=1280, label="960×1280 竖向 3:4", aspect_ratio="3:4"),
    SizeOption(width=1440, height=1080, label="1440×1080 横向 4:3", aspect_ratio="4:3"),
    SizeOption(width=1080, height=1440, label="1080×1440 竖向 3:4", aspect_ratio="3:4"),
    SizeOption(width=1280, height=720, label="1280×720 横向 16:9", aspect_ratio="16:9"),
    SizeOption(width=720, height=1280, label="720×1280 竖向 9:16", aspect_ratio="9:16"),
    SizeOption(width=1920, height=1080, label="1920×1080 横向 16:9", aspect_ratio="16:9"),
    SizeOption(width=1080, height=1920, label="1080×1920 竖向 9:16", aspect_ratio="9:16"),
    SizeOption(width=1344, height=576, label="1344×576 横向 21:9", aspect_ratio="21:9"),
    SizeOption(width=2048, height=872, label="2048×872 横向 21:9", aspect_ratio="21:9"),
]


# ============ 模型定义 ============

def _build_qwen_image_edit_params():
    """构建 qwen-image-edit plus/max 系列共用参数"""
    return [
        ModelParameter(
            name="prompt",
            label="编辑提示词",
            type=ParameterType.TEXT,
            description="描述要对图片进行的编辑操作。多图时用'图1'、'图2'、'图3'指代。最长800字符。",
            required=True,
            constraint=ParameterConstraint(max_length=800),
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容，最长500字符",
            required=False,
            constraint=ParameterConstraint(max_length=500),
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="images",
            label="输入图片",
            type=ParameterType.IMAGE_URLS,
            description="输入图片URL（1-3张）。1张为单图编辑，2-3张为多图融合。图片顺序影响结果，输出比例以最后一张图片为准。",
            required=True,
            constraint=ParameterConstraint(min_length=1, max_length=3),
            group="input",
            order=1,
        ),
        ModelParameter(
            name="n",
            label="生成数量",
            type=ParameterType.INTEGER,
            description="输出图片数量（1-6张）",
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
            description="输出图像分辨率，宽高范围[512,2048]。不设置则保持原图比例，接近1024*1024。",
            required=False,
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="", label="默认（保持原图比例）"),
                    SelectOption(value="1024*1024", label="1024×1024 方形 1:1"),
                    SelectOption(value="1536*1536", label="1536×1536 方形 1:1"),
                    SelectOption(value="1152*768", label="1152×768 横向 3:2"),
                    SelectOption(value="768*1152", label="768×1152 竖向 2:3"),
                    SelectOption(value="1536*1024", label="1536×1024 横向 3:2"),
                    SelectOption(value="1024*1536", label="1024×1536 竖向 2:3"),
                    SelectOption(value="1280*960", label="1280×960 横向 4:3"),
                    SelectOption(value="960*1280", label="960×1280 竖向 3:4"),
                    SelectOption(value="1280*720", label="1280×720 横向 16:9"),
                    SelectOption(value="720*1280", label="720×1280 竖向 9:16"),
                    SelectOption(value="1920*1080", label="1920×1080 横向 16:9"),
                    SelectOption(value="1080*1920", label="1080×1920 竖向 9:16"),
                    SelectOption(value="1344*576", label="1344×576 横向 21:9"),
                    SelectOption(value="2048*872", label="2048×872 横向 21:9"),
                ],
            ),
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="开启后使用大模型优化提示词，对简单描述效果更明显",
            required=False,
            default=True,
            group="generation",
            order=3,
        ),
        ModelParameter(
            name="watermark",
            label="添加水印",
            type=ParameterType.BOOLEAN,
            description="在图像右下角添加 Qwen-Image 水印",
            required=False,
            default=False,
            group="generation",
            order=4,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            description="固定种子可使结果相对稳定，留空为随机。范围[0,2147483647]",
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="generation",
            advanced=True,
            order=5,
        ),
    ]


QWEN_IMAGE_EDIT_PLUS_MODEL_INFO = ModelInfo(
    id="qwen-image-edit-plus",
    name="通义千问 图像编辑 Plus",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="支持单图编辑和多图融合，可修改文字、增删物体、改变动作、风格迁移等",
    version="plus",
    
    api_model_name="qwen-image-edit-plus",
    doc_url="https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
    ),
    
    common_sizes=QWEN_IMAGE_EDIT_COMMON_SIZES,
    parameters=_build_qwen_image_edit_params(),
)


QWEN_IMAGE_EDIT_MAX_MODEL_INFO = ModelInfo(
    id="qwen-image-edit-max",
    name="通义千问 图像编辑 Max",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="最强图像编辑模型，支持单图编辑和多图融合，效果优于Plus。可修改文字、增删物体、改变动作、风格迁移、增强画面细节",
    version="max",
    
    api_model_name="qwen-image-edit-max",
    doc_url="https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=False,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
    ),
    
    common_sizes=QWEN_IMAGE_EDIT_COMMON_SIZES,
    recommended=True,
    parameters=_build_qwen_image_edit_params(),
)


# ============ 服务实现 ============

class QwenImageEditService(BaseModelService[List[str]]):
    """
    通义千问图像编辑服务（plus / max 共用）
    
    支持两种模式：
    1. 单图编辑：输入1张图片，进行编辑
    2. 多图融合：输入2-3张图片，融合生成新图
    """
    
    def __init__(self, model_info: ModelInfo = QWEN_IMAGE_EDIT_MAX_MODEL_INFO):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        import dashscope
        if base_url:
            dashscope.base_http_api_url = base_url
    
    def _build_content(self, images: List[str], prompt: str) -> List[dict]:
        """
        构建消息内容
        
        格式：[{"image": url1}, {"image": url2}, ..., {"text": prompt}]
        """
        content = []
        
        # 添加图片
        for image_url in images:
            content.append({"image": image_url})
        
        # 添加提示词
        content.append({"text": prompt})
        
        return content
    
    async def generate(
        self,
        prompt: str,
        images: Union[str, List[str]],
        negative_prompt: str = "",
        n: int = 1,
        size: Optional[str] = None,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        project_id: str = "",
        **kwargs
    ) -> List[str]:
        """
        编辑图片或融合多图
        
        Args:
            prompt: 编辑提示词（多图时用"图1"、"图2"等指代）
            images: 输入图片URL（单个或1-3张列表）
            negative_prompt: 负面提示词
            n: 输出图片数量（1-6）
            size: 输出尺寸，格式"宽*高"，仅当n=1时可用
            prompt_extend: 是否开启智能改写
            watermark: 是否添加水印
            seed: 随机种子
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            生成的图片URL列表（如果启用 OSS，返回 OSS URL）
        """
        # 确保 images 是列表
        if isinstance(images, str):
            images = [images]
        
        # 验证图片数量
        if len(images) < 1 or len(images) > 3:
            raise ValueError(f"图片数量必须为1-3张，当前: {len(images)}")
        
        # 构建消息内容
        content = self._build_content(images, prompt)
        
        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        
        # 构建 API 参数
        call_params = {
            "model": self.model_info.api_model_name,
            "messages": messages,
            "stream": False,
        }
        
        # 添加可选参数
        if n and n > 1:
            call_params["n"] = n
        
        if negative_prompt:
            call_params["negative_prompt"] = negative_prompt
        
        if size:
            call_params["size"] = size
        
        # prompt_extend 默认为 True
        call_params["prompt_extend"] = prompt_extend
        
        # watermark
        call_params["watermark"] = watermark
        
        # seed
        if seed is not None:
            call_params["seed"] = seed
        
        # DashScope SDK 的 MultiModalConversation.call 是同步阻塞调用，
        # 通过 asyncio.to_thread 在线程池中执行，避免阻塞事件循环
        import asyncio
        response = await asyncio.to_thread(
            MultiModalConversation.call,
            api_key=self._api_key,
            **call_params
        )
        
        if response.status_code != 200:
            error_msg = f"API 调用失败: {response.code} - {response.message}"
            if hasattr(response, 'request_id'):
                error_msg += f" (request_id: {response.request_id})"
            raise Exception(error_msg)
        
        # 提取图片URL
        urls = []
        if hasattr(response, 'output') and hasattr(response.output, 'choices'):
            for choice in response.output.choices:
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    for item in choice.message.content:
                        if isinstance(item, dict) and 'image' in item:
                            urls.append(item['image'])
        
        if not urls:
            raise Exception("未能从响应中提取到图片URL")
        
        # 如果启用了 OSS，上传图片并返回 OSS URL
        if oss_service.is_enabled():
            oss_urls = []
            for url in urls:
                oss_url = await oss_service.upload_image_async(url, project_id)
                oss_urls.append(oss_url)
            return oss_urls
        
        return urls
    
    async def edit_single_image(
        self,
        image_url: str,
        prompt: str,
        negative_prompt: str = "",
        n: int = 1,
        size: Optional[str] = None,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        project_id: str = "",
    ) -> List[str]:
        """
        单图编辑模式
        """
        return await self.generate(
            prompt=prompt,
            images=[image_url],
            negative_prompt=negative_prompt,
            n=n,
            size=size,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            project_id=project_id,
        )
    
    async def merge_images(
        self,
        images: List[str],
        prompt: str,
        negative_prompt: str = "",
        n: int = 1,
        size: Optional[str] = None,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        project_id: str = "",
    ) -> List[str]:
        """
        多图融合模式
        
        Note:
            输出图像的比例以最后一张上传的图片为准
        """
        if len(images) < 2:
            raise ValueError("多图融合至少需要2张图片")
        if len(images) > 3:
            raise ValueError("多图融合最多支持3张图片")
        
        return await self.generate(
            prompt=prompt,
            images=images,
            negative_prompt=negative_prompt,
            n=n,
            size=size,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            project_id=project_id,
        )


# ============ 注册模型 ============

def register():
    registry.register(QWEN_IMAGE_EDIT_PLUS_MODEL_INFO, QwenImageEditService)
    registry.register(QWEN_IMAGE_EDIT_MAX_MODEL_INFO, QwenImageEditService)


register()
