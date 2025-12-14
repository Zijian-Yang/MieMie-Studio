"""
万相2.5 图生视频模型 (wan2.5-i2v-preview)

API 文档: https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference

模型特点:
- 支持首帧图生成视频
- 支持 5-10 秒视频时长
- 支持 480P/720P/1080P 分辨率（由输入图像宽高比决定）
- 支持音频（自定义音频或自动生成）
- 支持智能改写、水印、种子等参数

添加新模型步骤:
1. 创建模型定义文件（如本文件）
2. 定义 ModelInfo（包含参数、能力等）
3. 实现 Service 类（继承 BaseModelService）
4. 在 __init__.py 中注册模型
"""

from typing import Optional, Tuple
from http import HTTPStatus
import dashscope
from dashscope import VideoSynthesis

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)


# ============ 模型定义 ============

WAN25_I2V_MODEL_INFO = ModelInfo(
    # 基本信息
    id="wan2.5-i2v-preview",
    name="万相2.5 图生视频 Preview",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="最新图生视频模型，支持音频，分辨率由输入图像决定",
    version="2.5",
    
    # API 信息
    api_model_name="wan2.5-i2v-preview",
    doc_url="https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference",
    
    # 能力声明
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_audio=True,  # 支持音频
    ),
    
    # 参数定义
    parameters=[
        # === 基础参数组 ===
        ModelParameter(
            name="img_url",
            label="首帧图片",
            type=ParameterType.IMAGE_URL,
            description="首帧图片URL，图像宽高比决定输出视频宽高比",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述视频内容，最长1000字符",
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
        
        # === 生成参数组 ===
        ModelParameter(
            name="resolution",
            label="分辨率",
            type=ParameterType.SELECT,
            description="输出视频分辨率档位，实际分辨率由输入图像宽高比决定",
            required=False,
            default="720P",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="480P", label="480P (标清)"),
                    SelectOption(value="720P", label="720P (高清)"),
                    SelectOption(value="1080P", label="1080P (全高清)"),
                ]
            ),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="duration",
            label="视频时长",
            type=ParameterType.INTEGER,
            description="视频时长（秒），范围 5-10",
            required=False,
            default=5,
            constraint=ParameterConstraint(min_value=5, max_value=10),
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词",
            required=False,
            default=True,
            group="generation",
            order=3,
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
            order=4,
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
            order=5,
        ),
        
        # === 音频参数组 ===
        ModelParameter(
            name="audio_url",
            label="自定义音频",
            type=ParameterType.AUDIO_URL,
            description="自定义音频URL，视频画面会与音频对齐",
            required=False,
            group="audio",
            order=1,
        ),
        ModelParameter(
            name="audio",
            label="自动生成音频",
            type=ParameterType.BOOLEAN,
            description="根据画面内容自动生成匹配的音频（设置 audio_url 时此参数无效）",
            required=False,
            default=False,
            constraint=ParameterConstraint(
                depends_on="audio_url",
                depends_value=None,  # 只有当 audio_url 为空时才生效
            ),
            group="audio",
            order=2,
        ),
    ],
    
    # 状态
    enabled=True,
)


# ============ 服务实现 ============

class Wan25I2VService(BaseModelService[str]):
    """
    万相2.5 图生视频服务
    
    继承 BaseModelService 并实现具体的 API 调用逻辑
    """
    
    def __init__(self, model_info: ModelInfo = WAN25_I2V_MODEL_INFO):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        """配置 API"""
        super().configure(api_key, base_url)
        if base_url:
            dashscope.base_http_api_url = base_url
    
    async def generate(
        self,
        img_url: str,
        prompt: str = "",
        negative_prompt: str = "",
        resolution: str = "720P",
        duration: int = 5,
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        watermark: bool = False,
        audio_url: Optional[str] = None,
        audio: bool = False,
        **kwargs
    ) -> str:
        """
        生成视频（完整流程：创建任务并等待完成）
        
        Returns:
            视频URL
        """
        task_id = await self.create_task(
            img_url=img_url,
            prompt=prompt,
            negative_prompt=negative_prompt,
            resolution=resolution,
            duration=duration,
            prompt_extend=prompt_extend,
            seed=seed,
            watermark=watermark,
            audio_url=audio_url,
            audio=audio,
        )
        
        # 等待任务完成
        import asyncio
        max_wait = 600  # 10分钟超时
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
        img_url: str,
        prompt: str = "",
        negative_prompt: str = "",
        resolution: str = "720P",
        duration: int = 5,
        prompt_extend: bool = True,
        seed: Optional[int] = None,
        watermark: bool = False,
        audio_url: Optional[str] = None,
        audio: bool = False,
        **kwargs
    ) -> str:
        """
        创建视频生成任务
        
        Returns:
            任务ID
        """
        # 构建参数
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'img_url': img_url,  # wan2.5 使用 img_url
        }
        
        if prompt:
            params['prompt'] = prompt
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        # 分辨率（wan2.5 使用 resolution 参数）
        params['resolution'] = resolution
        
        # 视频时长（5-10秒）
        params['duration'] = max(5, min(10, duration))
        
        # 智能改写
        params['prompt_extend'] = prompt_extend
        
        # 水印
        params['watermark'] = watermark
        
        # 种子
        if seed is not None:
            params['seed'] = seed
        
        # 音频设置
        if audio_url:
            params['audio_url'] = audio_url
        elif audio:
            params['audio'] = True
        
        # 调用 API
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
    """注册模型到全局注册中心"""
    registry.register(WAN25_I2V_MODEL_INFO, Wan25I2VService)


# 自动注册（导入时执行）
register()

