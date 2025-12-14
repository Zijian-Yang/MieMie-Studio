"""
万相2.1 图生视频 Turbo 模型 (wanx2.1-i2v-turbo)

API 文档: https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference

模型特点：
- 快速生成视频，适合快速预览
- 固定 5 秒时长
- 使用 size 参数指定分辨率（与 wan2.5 不同）
- 不支持音频
"""

from typing import Optional
from http import HTTPStatus
import asyncio
import dashscope
from dashscope import VideoSynthesis

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)


# ============ 模型定义 ============

WANX21_I2V_MODEL_INFO = ModelInfo(
    id="wanx2.1-i2v-turbo",
    name="万相2.1 图生视频 Turbo",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="快速生成模型，固定5秒时长，适合快速预览",
    version="2.1",
    
    api_model_name="wanx2.1-i2v-turbo",
    doc_url="https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_audio=False,  # 不支持音频
    ),
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="image_url",  # 注意：wanx2.1 使用 image_url
            label="首帧图片",
            type=ParameterType.IMAGE_URL,
            description="首帧图片URL",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述视频内容",
            required=False,
            constraint=ParameterConstraint(max_length=1000),
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容",
            required=False,
            group="basic",
            order=3,
        ),
        
        # === 生成参数 ===
        ModelParameter(
            name="size",  # 注意：wanx2.1 使用 size 参数
            label="分辨率",
            type=ParameterType.SELECT,
            description="输出视频分辨率",
            required=False,
            default="1280*720",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1280*720", label="1280×720 (16:9 横屏)"),
                    SelectOption(value="720*1280", label="720×1280 (9:16 竖屏)"),
                    SelectOption(value="960*960", label="960×960 (1:1 方形)"),
                ]
            ),
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
        ModelParameter(
            name="watermark",
            label="添加水印",
            type=ParameterType.BOOLEAN,
            description="是否在视频中添加水印",
            required=False,
            default=False,
            group="generation",
            advanced=True,
            order=4,
        ),
    ],
)


# ============ 服务实现 ============

class Wanx21I2VService(BaseModelService[str]):
    """
    万相2.1 图生视频 Turbo 服务
    """
    
    def __init__(self, model_info: ModelInfo = WANX21_I2V_MODEL_INFO):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            dashscope.base_http_api_url = base_url
    
    async def generate(
        self,
        image_url: str,  # 注意：wanx2.1 使用 image_url
        prompt: str = "",
        negative_prompt: str = "",
        size: str = "1280*720",
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        watermark: bool = False,
        **kwargs
    ) -> str:
        """
        生成视频
        
        Returns:
            视频URL
        """
        task_id = await self.create_task(
            image_url=image_url,
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            prompt_extend=prompt_extend,
            seed=seed,
            watermark=watermark,
        )
        
        # 等待完成
        max_wait = 600
        elapsed = 0
        
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)
            if result.status == TaskStatus.SUCCEEDED:
                return result.result
            elif result.status == TaskStatus.FAILED:
                raise Exception(f"视频生成失败: {result.error_message}")
            
            await asyncio.sleep(5)
            elapsed += 5
        
        raise Exception("视频生成超时")
    
    async def create_task(
        self,
        image_url: str,
        prompt: str = "",
        negative_prompt: str = "",
        size: str = "1280*720",
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        watermark: bool = False,
        **kwargs
    ) -> str:
        """创建视频生成任务"""
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'image_url': image_url,  # wanx2.1 使用 image_url
        }
        
        if prompt:
            params['prompt'] = prompt
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        # wanx2.1 使用 size 参数
        params['size'] = size
        
        params['prompt_extend'] = prompt_extend
        params['watermark'] = watermark
        
        if seed is not None:
            params['seed'] = seed
        
        rsp = VideoSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建任务失败: {rsp.code} - {rsp.message}")
        
        return rsp.output.task_id
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """获取任务状态"""
        rsp = VideoSynthesis.fetch(
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
            result.result = rsp.output.video_url
        elif status == TaskStatus.FAILED:
            result.error_message = getattr(rsp.output, 'message', '未知错误')
        
        return result


# ============ 注册模型 ============

def register():
    registry.register(WANX21_I2V_MODEL_INFO, Wanx21I2VService)


register()

