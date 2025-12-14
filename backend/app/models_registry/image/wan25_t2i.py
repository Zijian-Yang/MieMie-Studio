"""
万相2.5 文生图模型 (wan2.5-t2i-preview)

API 文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference

模型特点：
- 支持自定义图片尺寸（总像素在 768*768 到 1440*1440 之间）
- 宽高比范围 1:4 到 4:1
- 支持智能改写、种子、负面提示词
- 支持批量生成（1-4张）
"""

from typing import Optional, List
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

WAN25_T2I_MODEL_INFO = ModelInfo(
    id="wan2.5-t2i-preview",
    name="万相2.5 文生图 Preview",
    type=ModelType.TEXT_TO_IMAGE,
    provider="dashscope",
    description="万相2.5 文生图模型，支持自定义尺寸和多种参数",
    version="2.5",
    
    api_model_name="wanx2.5-t2i-preview",
    doc_url="https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference",
    
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
        
        # === 尺寸参数 ===
        ModelParameter(
            name="size",
            label="图片尺寸",
            type=ParameterType.SELECT,
            description="预设尺寸（或使用自定义宽高）",
            required=False,
            default="1024*1024",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1024*1024", label="1024×1024 (1:1 方形)"),
                    SelectOption(value="1280*720", label="1280×720 (16:9 横屏)"),
                    SelectOption(value="720*1280", label="720×1280 (9:16 竖屏)"),
                    SelectOption(value="1024*768", label="1024×768 (4:3 横屏)"),
                    SelectOption(value="768*1024", label="768×1024 (3:4 竖屏)"),
                    SelectOption(value="1440*810", label="1440×810 (16:9 高清横屏)"),
                    SelectOption(value="810*1440", label="810×1440 (9:16 高清竖屏)"),
                ]
            ),
            group="size",
            order=1,
        ),
        ModelParameter(
            name="width",
            label="自定义宽度",
            type=ParameterType.INTEGER,
            description="自定义宽度（需与高度配合满足像素约束）",
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
            description="自定义高度（总像素需在 589824-2073600 之间）",
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

class Wan25T2IService(BaseModelService[List[str]]):
    """
    万相2.5 文生图服务
    """
    
    def __init__(self, model_info: ModelInfo = WAN25_T2I_MODEL_INFO):
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
        return 1024, 1024  # 默认
    
    def _validate_size(self, width: int, height: int) -> bool:
        """验证尺寸是否合法"""
        total_pixels = width * height
        ratio = width / height if height > 0 else 0
        
        min_pixels = 768 * 768  # 589824
        max_pixels = 1440 * 1440  # 2073600
        
        return (
            min_pixels <= total_pixels <= max_pixels and
            0.25 <= ratio <= 4.0
        )
    
    async def generate(
        self,
        prompt: str,
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
        生成图片
        
        Returns:
            图片URL列表
        """
        # 解析尺寸
        w, h = self._parse_size(size, width, height)
        
        # 验证尺寸
        if not self._validate_size(w, h):
            raise ValueError(f"尺寸不合法: {w}x{h}，总像素需在 589824-2073600 之间，宽高比需在 1:4-4:1 之间")
        
        # 创建任务
        task_id = await self.create_task(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=w,
            height=h,
            n=n,
            prompt_extend=prompt_extend,
            seed=seed,
        )
        
        # 等待完成
        max_wait = 300  # 5分钟
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
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建图片生成任务"""
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'prompt': prompt,
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
            # 提取所有图片URL
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
    registry.register(WAN25_T2I_MODEL_INFO, Wan25T2IService)


register()

