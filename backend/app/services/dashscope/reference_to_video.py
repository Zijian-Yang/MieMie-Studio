"""
视频生视频服务 - 参考视频生成视频
基于 wan2.6-r2v 模型，参考输入视频的角色形象和音色生成新视频

官方文档: https://help.aliyun.com/zh/model-studio/reference-to-video-api
"""

import json
import logging
from http import HTTPStatus
from typing import Optional, List, Tuple

import httpx

from ...config import get_config, REF_VIDEO_MODELS
from ..oss import oss_service

logger = logging.getLogger(__name__)


class ReferenceToVideoService:
    """视频生视频服务（参考视频生成视频）"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.ref_video_config = config.ref_video
        self.base_url = config.base_url
    
    async def create_task(
        self,
        reference_video_urls: List[str],
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        duration: Optional[int] = None,
        shot_type: Optional[str] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio: Optional[bool] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """
        创建视频生视频任务
        
        Args:
            reference_video_urls: 参考视频URL列表（最多2个）
            prompt: 文本提示词，使用 character1/character2 指代参考视频中的主体
            model: 模型名称，默认 wan2.6-r2v
            size: 分辨率（宽*高格式，如 1920*1080）
            duration: 视频时长（秒），5 或 10
            shot_type: 镜头类型，single/multi
            watermark: 是否添加水印
            seed: 随机种子
            audio: 是否生成音频
            negative_prompt: 反向提示词
            
        Returns:
            任务 ID
        """
        model_name = model or self.ref_video_config.model
        
        # 构建 input 参数
        input_data = {
            "prompt": prompt
        }
        
        if reference_video_urls:
            # 限制最多2个参考视频
            input_data["reference_video_urls"] = reference_video_urls[:2]
        
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        # 构建 parameters 参数
        parameters = {}
        
        # 分辨率（使用具体的宽*高格式）
        if size:
            parameters["size"] = size
        elif self.ref_video_config.size:
            parameters["size"] = self.ref_video_config.size
        
        # 视频时长
        if duration is not None:
            parameters["duration"] = duration
        elif self.ref_video_config.duration:
            parameters["duration"] = self.ref_video_config.duration
        
        # 镜头类型
        if shot_type:
            parameters["shot_type"] = shot_type
        elif self.ref_video_config.shot_type:
            parameters["shot_type"] = self.ref_video_config.shot_type
        
        # 水印
        if watermark is not None:
            parameters["watermark"] = watermark
        elif self.ref_video_config.watermark is not None:
            parameters["watermark"] = self.ref_video_config.watermark
        
        # 随机种子
        if seed is not None:
            parameters["seed"] = seed
        elif self.ref_video_config.seed is not None:
            parameters["seed"] = self.ref_video_config.seed
        
        # 音频
        if audio is not None:
            parameters["audio"] = audio
        elif self.ref_video_config.audio is not None:
            parameters["audio"] = self.ref_video_config.audio
        
        # 构建请求体
        request_body = {
            "model": model_name,
            "input": input_data
        }
        
        if parameters:
            request_body["parameters"] = parameters
        
        logger.info(f"[wan2.6-r2v HTTP请求] URL: {self.base_url}/services/aigc/video-generation/video-synthesis")
        logger.info(f"[wan2.6-r2v HTTP请求] Body: {json.dumps(request_body, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/video-generation/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json=request_body
            )
            
            result = response.json()
            logger.info(f"[wan2.6-r2v HTTP响应] Status: {response.status_code}, Body: {json.dumps(result, ensure_ascii=False)}")
            
            if response.status_code != 200:
                error_code = result.get("code", "Unknown")
                error_message = result.get("message", "Unknown error")
                raise Exception(f"创建任务失败: {error_code} - {error_message}")
            
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建任务失败: 未返回 task_id")
            
            return task_id
    
    async def get_task_status(self, task_id: str, project_id: str = "") -> Tuple[str, Optional[str]]:
        """
        获取任务状态（仅支持 HTTP 查询）
        
        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            (状态, 视频URL) 元组
        """
        logger.info(f"[wan2.6-r2v 查询任务] task_id: {task_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            
            result = response.json()
            logger.info(f"[wan2.6-r2v 查询响应] Status: {response.status_code}, Body: {json.dumps(result, ensure_ascii=False)}")
            
            if response.status_code != 200:
                error_code = result.get("code", "Unknown")
                error_message = result.get("message", "Unknown error")
                raise Exception(f"查询任务状态失败: {error_code} - {error_message}")
            
            output = result.get("output", {})
            status = output.get("task_status", "UNKNOWN")
            video_url = output.get("video_url") if status == "SUCCEEDED" else None
        
        # 如果启用了 OSS，上传视频并返回 OSS URL
        if status == "SUCCEEDED" and video_url and oss_service.is_enabled():
            video_url = oss_service.upload_video(video_url, project_id)
        
        return status, video_url
    
    def get_model_info(self, model: str = None) -> dict:
        """获取模型信息"""
        model_name = model or self.ref_video_config.model
        return REF_VIDEO_MODELS.get(model_name, {})

