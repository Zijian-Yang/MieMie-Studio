"""
阿里云 DashScope 图生视频服务封装
"""

from typing import Optional, Tuple
from http import HTTPStatus
import dashscope
from dashscope import VideoSynthesis

from app.config import get_config


class ImageToVideoService:
    """图生视频服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.video_config = config.video
        dashscope.base_http_api_url = config.base_url
    
    async def create_task(
        self,
        image_url: str,
        prompt: str = "",
        model: Optional[str] = None,
        size: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None
    ) -> str:
        """
        创建视频生成任务
        
        Args:
            image_url: 首帧图片 URL
            prompt: 视频生成提示词
            model: 模型名称（使用配置默认值）
            size: 视频分辨率（使用配置默认值）
            prompt_extend: 智能改写（使用配置默认值）
            watermark: 水印（使用配置默认值）
            seed: 种子（使用配置默认值）
            
        Returns:
            任务 ID
        """
        input_data = {
            'image_url': image_url
        }
        
        if prompt:
            input_data['prompt'] = prompt
        
        params = {
            'api_key': self.api_key,
            'model': model or self.video_config.model,
            'input': input_data
        }
        
        # 添加可选参数
        parameters = {}
        
        size_value = size or self.video_config.size
        if size_value:
            parameters['size'] = size_value
        
        prompt_extend_value = prompt_extend if prompt_extend is not None else self.video_config.prompt_extend
        if prompt_extend_value is not None:
            parameters['prompt_extend'] = prompt_extend_value
        
        watermark_value = watermark if watermark is not None else self.video_config.watermark
        if watermark_value is not None:
            parameters['watermark'] = watermark_value
        
        seed_value = seed if seed is not None else self.video_config.seed
        if seed_value is not None:
            parameters['seed'] = seed_value
        
        if parameters:
            params['parameters'] = parameters
        
        rsp = VideoSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建视频任务失败: {rsp.code} - {rsp.message}")
        
        return rsp.output.task_id
    
    async def get_task_status(self, task_id: str) -> Tuple[str, Optional[str]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            (状态, 视频URL) 元组，状态为 PENDING/PROCESSING/SUCCEEDED/FAILED
        """
        rsp = VideoSynthesis.fetch(
            api_key=self.api_key,
            task=task_id
        )
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"查询任务状态失败: {rsp.code} - {rsp.message}")
        
        status = rsp.output.task_status
        video_url = None
        
        if status == 'SUCCEEDED':
            video_url = rsp.output.video_url
        
        return status, video_url
    
    async def wait_for_task(self, task_id: str) -> str:
        """
        等待任务完成并返回视频 URL
        
        Args:
            task_id: 任务 ID
            
        Returns:
            视频 URL
        """
        rsp = VideoSynthesis.wait(
            api_key=self.api_key,
            task=task_id
        )
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"任务失败: {rsp.code} - {rsp.message}")
        
        if rsp.output.task_status == 'SUCCEEDED':
            return rsp.output.video_url
        elif rsp.output.task_status == 'FAILED':
            error_msg = getattr(rsp.output, 'message', '未知错误')
            raise Exception(f"视频生成失败: {error_msg}")
        else:
            raise Exception(f"未知的任务状态: {rsp.output.task_status}")
    
    async def generate(
        self,
        image_url: str,
        prompt: str = "",
        model: Optional[str] = None,
        size: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None
    ) -> str:
        """
        生成视频（完整流程：创建任务并等待完成）
        """
        task_id = await self.create_task(
            image_url, prompt, model, size, prompt_extend, watermark, seed
        )
        return await self.wait_for_task(task_id)
