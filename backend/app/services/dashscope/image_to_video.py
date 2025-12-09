"""
阿里云 DashScope 图生视频服务封装

模型参数差异：
- wan2.5-i2v-preview:
  - 图片参数: img_url
  - 分辨率参数: resolution (480P/720P/1080P)
  - 支持 duration (5-10秒)
  - 支持音频: audio_url, audio
  
- wanx2.1-i2v-turbo:
  - 图片参数: image_url
  - 分辨率参数: size (1280*720 等)
  - duration 固定 5秒
  - 不支持音频
"""

from typing import Optional, Tuple
from http import HTTPStatus
import dashscope
from dashscope import VideoSynthesis

from app.config import get_config, VIDEO_MODELS
from app.services.oss import oss_service


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
        resolution: Optional[str] = None,
        duration: Optional[int] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio_url: Optional[str] = None,
        audio: Optional[bool] = None,
        negative_prompt: Optional[str] = None
    ) -> str:
        """
        创建视频生成任务
        
        Args:
            image_url: 首帧图片 URL
            prompt: 视频生成提示词
            model: 模型名称（使用配置默认值）
            resolution: 分辨率（wan2.5用480P/720P/1080P，wanx2.1用宽*高）
            duration: 视频时长（秒）
            prompt_extend: 智能改写（使用配置默认值）
            watermark: 水印（使用配置默认值）
            seed: 种子（使用配置默认值）
            audio_url: 音频URL（仅wan2.5支持）
            audio: 是否自动生成音频（仅wan2.5支持）
            negative_prompt: 负面提示词
            
        Returns:
            任务 ID
        """
        model_name = model or self.video_config.model
        is_wan25 = 'wan2.5' in model_name
        
        # 基础参数
        params = {
            'api_key': self.api_key,
            'model': model_name,
        }
        
        # 根据模型选择正确的图片参数名
        if is_wan25:
            params['img_url'] = image_url
        else:
            params['image_url'] = image_url
        
        if prompt:
            params['prompt'] = prompt
        
        # 分辨率参数
        resolution_value = resolution or self.video_config.resolution
        if resolution_value:
            if is_wan25:
                # wan2.5 使用 resolution 参数（480P/720P/1080P）
                params['resolution'] = resolution_value
            else:
                # wanx2.1 使用 size 参数（1280*720 等）
                params['size'] = resolution_value
        
        # 视频时长（wan2.5 支持 5-10秒，wanx2.1 固定5秒）
        duration_value = duration if duration is not None else self.video_config.duration
        if duration_value is not None:
            if is_wan25:
                # wan2.5 支持 duration 参数
                params['duration'] = max(5, min(10, duration_value))  # 限制在5-10秒
            # wanx2.1 不支持 duration 参数，固定5秒
        
        # 智能改写
        prompt_extend_value = prompt_extend if prompt_extend is not None else self.video_config.prompt_extend
        if prompt_extend_value is not None:
            params['prompt_extend'] = prompt_extend_value
        
        # 水印
        watermark_value = watermark if watermark is not None else self.video_config.watermark
        if watermark_value is not None:
            params['watermark'] = watermark_value
        
        # 种子
        seed_value = seed if seed is not None else self.video_config.seed
        if seed_value is not None:
            params['seed'] = seed_value
        
        # 负面提示词
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        # 音频参数（仅 wan2.5 支持）
        if is_wan25:
            if audio_url:
                # 使用自定义音频
                params['audio_url'] = audio_url
            elif audio is not None:
                # audio 参数控制是否自动生成音频
                params['audio'] = audio
            elif self.video_config.audio:
                # 使用配置的默认值
                params['audio'] = self.video_config.audio
        
        rsp = VideoSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建视频任务失败: {rsp.code} - {rsp.message}")
        
        return rsp.output.task_id
    
    async def get_task_status(self, task_id: str, project_id: str = "") -> Tuple[str, Optional[str]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            (状态, 视频URL) 元组，状态为 PENDING/PROCESSING/SUCCEEDED/FAILED
            如果启用 OSS，视频 URL 将是 OSS URL
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
            # 如果启用了 OSS，上传视频并返回 OSS URL
            if video_url and oss_service.is_enabled():
                video_url = oss_service.upload_video(video_url, project_id)
        
        return status, video_url
    
    async def wait_for_task(self, task_id: str, project_id: str = "") -> str:
        """
        等待任务完成并返回视频 URL（使用异步轮询避免阻塞）
        
        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            视频 URL（如果启用 OSS，返回 OSS URL）
        """
        import asyncio
        
        max_wait_time = 600  # 10分钟超时（视频生成需要更长时间）
        poll_interval = 5  # 每5秒检查一次
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            rsp = VideoSynthesis.fetch(
                api_key=self.api_key,
                task=task_id
            )
            
            if rsp.status_code != HTTPStatus.OK:
                raise Exception(f"任务查询失败: {rsp.code} - {rsp.message}")
            
            task_status = rsp.output.task_status
            
            if task_status == 'SUCCEEDED':
                video_url = rsp.output.video_url
                # 如果启用了 OSS，上传视频并返回 OSS URL
                if oss_service.is_enabled():
                    video_url = oss_service.upload_video(video_url, project_id)
                return video_url
            elif task_status == 'FAILED':
                error_msg = getattr(rsp.output, 'message', '未知错误')
                raise Exception(f"视频生成失败: {error_msg}")
            elif task_status in ['PENDING', 'RUNNING']:
                # 使用异步 sleep 避免阻塞事件循环
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
            else:
                raise Exception(f"未知的任务状态: {task_status}")
        
        raise Exception(f"视频生成超时（{max_wait_time}秒）")
    
    async def generate(
        self,
        image_url: str,
        prompt: str = "",
        model: Optional[str] = None,
        resolution: Optional[str] = None,
        duration: Optional[int] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio_url: Optional[str] = None,
        audio: Optional[bool] = None,
        negative_prompt: Optional[str] = None,
        project_id: str = ""
    ) -> str:
        """
        生成视频（完整流程：创建任务并等待完成）
        
        Args:
            image_url: 首帧图片 URL
            prompt: 视频生成提示词
            model: 模型名称（使用配置默认值）
            resolution: 分辨率
            duration: 视频时长（秒）
            prompt_extend: 智能改写（使用配置默认值）
            watermark: 水印（使用配置默认值）
            seed: 种子（使用配置默认值）
            audio_url: 音频URL（仅wan2.5支持）
            audio: 是否自动生成音频（仅wan2.5支持）
            negative_prompt: 负面提示词
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            视频 URL（如果启用 OSS，返回 OSS URL）
        """
        task_id = await self.create_task(
            image_url, prompt, model, resolution, duration,
            prompt_extend, watermark, seed, audio_url, audio, negative_prompt
        )
        return await self.wait_for_task(task_id, project_id)
