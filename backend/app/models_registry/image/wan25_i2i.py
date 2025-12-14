"""
万相2.5 图生图模型 (wan2.5-i2i-preview)

API 文档: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference

模型特点：
- 支持参考图片进行风格迁移或内容生成
- 支持多参考图（最多5张）
- 支持自定义输出尺寸
- 支持智能改写、种子、负面提示词
"""

from typing import Optional, List, Union
from http import HTTPStatus
import asyncio
import dashscope
from dashscope import ImageSynthesis

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)


# ============ 模型定义 ============

WAN25_I2I_MODEL_INFO = ModelInfo(
    id="wan2.5-i2i-preview",
    name="万相2.5 图生图 Preview",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="万相2.5 图生图模型，支持风格迁移和多参考图生成",
    version="2.5",
    
    api_model_name="wanx2.5-i2i-preview",
    doc_url="https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=True,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
    ),
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的图片内容",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容",
            required=False,
            group="basic",
            order=2,
        ),
        
        # === 参考图参数 ===
        ModelParameter(
            name="images",
            label="参考图片",
            type=ParameterType.IMAGE_URLS,
            description="参考图片URL列表（最多5张），图片顺序会影响生成结果",
            required=True,
            constraint=ParameterConstraint(min_length=1, max_length=5),
            group="reference",
            order=1,
        ),
        
        # === 尺寸参数 ===
        ModelParameter(
            name="size",
            label="输出尺寸",
            type=ParameterType.SELECT,
            description="输出图片尺寸",
            required=False,
            default="1024*1024",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1024*1024", label="1024×1024 (1:1 方形)"),
                    SelectOption(value="1280*720", label="1280×720 (16:9 横屏)"),
                    SelectOption(value="720*1280", label="720×1280 (9:16 竖屏)"),
                    SelectOption(value="1024*768", label="1024×768 (4:3 横屏)"),
                    SelectOption(value="768*1024", label="768×1024 (3:4 竖屏)"),
                ]
            ),
            group="size",
            order=1,
        ),
        ModelParameter(
            name="width",
            label="自定义宽度",
            type=ParameterType.INTEGER,
            description="自定义宽度",
            required=False,
            constraint=ParameterConstraint(min_value=256, max_value=2048),
            group="size",
            advanced=True,
            order=2,
        ),
        ModelParameter(
            name="height",
            label="自定义高度",
            type=ParameterType.INTEGER,
            description="自定义高度",
            required=False,
            constraint=ParameterConstraint(min_value=256, max_value=2048),
            group="size",
            advanced=True,
            order=3,
        ),
        
        # === 生成参数 ===
        ModelParameter(
            name="n",
            label="生成数量",
            type=ParameterType.INTEGER,
            description="一次生成的图片数量",
            required=False,
            default=1,
            constraint=ParameterConstraint(min_value=1, max_value=4),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词",
            required=False,
            default=True,
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            description="固定种子可复现结果，留空为随机",
            required=False,
            constraint=ParameterConstraint(min_value=0),
            group="generation",
            advanced=True,
            order=3,
        ),
    ],
)


# ============ 服务实现 ============

class Wan25I2IService(BaseModelService[List[str]]):
    """
    万相2.5 图生图服务
    """
    
    def __init__(self, model_info: ModelInfo = WAN25_I2I_MODEL_INFO):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            dashscope.base_http_api_url = base_url
    
    def _parse_size(self, size: str = None, width: int = None, height: int = None) -> tuple[int, int]:
        """解析尺寸参数"""
        if width and height:
            return width, height
        if size:
            parts = size.split('*')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        return 1024, 1024
    
    async def generate(
        self,
        prompt: str,
        images: Union[str, List[str]],
        negative_prompt: str = "",
        size: str = "1024*1024",
        width: Optional[int] = None,
        height: Optional[int] = None,
        n: int = 1,
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """
        图生图
        
        Args:
            prompt: 提示词
            images: 参考图片URL（单个或列表）
            
        Returns:
            生成的图片URL列表
        """
        # 确保 images 是列表
        if isinstance(images, str):
            images = [images]
        
        w, h = self._parse_size(size, width, height)
        
        task_id = await self.create_task(
            prompt=prompt,
            images=images,
            negative_prompt=negative_prompt,
            width=w,
            height=h,
            n=n,
            prompt_extend=prompt_extend,
            seed=seed,
        )
        
        # 等待完成
        max_wait = 300
        elapsed = 0
        
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)
            if result.status == TaskStatus.SUCCEEDED:
                return result.result or []
            elif result.status == TaskStatus.FAILED:
                raise Exception(f"图片生成失败: {result.error_message}")
            
            await asyncio.sleep(3)
            elapsed += 3
        
        raise Exception("图片生成超时")
    
    async def create_task(
        self,
        prompt: str,
        images: List[str],
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建图生图任务"""
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'prompt': prompt,
            'images': images,  # 参考图列表
            'n': n,
            'size': f"{width}*{height}",
        }
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        params['prompt_extend'] = prompt_extend
        
        if seed is not None:
            params['seed'] = seed
        
        rsp = ImageSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建任务失败: {rsp.code} - {rsp.message}")
        
        return rsp.output.task_id
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """获取任务状态"""
        rsp = ImageSynthesis.fetch(
            api_key=self._api_key,
            task=task_id
        )
        
        if rsp.status_code != HTTPStatus.OK:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=f"查询失败: {rsp.code} - {rsp.message}"
            )
        
        status_map = {
            'PENDING': TaskStatus.PENDING,
            'RUNNING': TaskStatus.PROCESSING,
            'SUCCEEDED': TaskStatus.SUCCEEDED,
            'FAILED': TaskStatus.FAILED,
        }
        
        task_status = rsp.output.task_status
        status = status_map.get(task_status, TaskStatus.PROCESSING)
        
        result = TaskResult(
            task_id=task_id,
            status=status,
        )
        
        if status == TaskStatus.SUCCEEDED:
            urls = []
            if hasattr(rsp.output, 'results') and rsp.output.results:
                for r in rsp.output.results:
                    if hasattr(r, 'url') and r.url:
                        urls.append(r.url)
            result.result = urls
        elif status == TaskStatus.FAILED:
            result.error_message = getattr(rsp.output, 'message', '未知错误')
        
        return result


# ============ 注册模型 ============

def register():
    registry.register(WAN25_I2I_MODEL_INFO, Wan25I2IService)


register()

