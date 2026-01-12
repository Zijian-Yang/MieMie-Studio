"""
阿里云 DashScope 首尾帧生视频服务封装

模型支持：
- wan2.2-kf2v-flash: 
  - 万相2.2极速版（无声视频）
  - 较2.1模型速度提升50%，稳定性与成功率全面提升
  - 分辨率: 480P/720P/1080P
  - 时长: 固定5秒
  - 固定规格: 30fps, MP4 (H.264编码)

参考文档: https://help.aliyun.com/zh/model-studio/image-to-video-by-first-and-last-frame-api-reference
"""

import json
import logging
from typing import Optional, Tuple
import httpx

from app.config import get_config, KEYFRAME_TO_VIDEO_MODELS
from app.services.oss import oss_service

# 配置日志
logger = logging.getLogger(__name__)


class KeyframeToVideoService:
    """首尾帧生视频服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.base_url = config.base_url
    
    async def create_task(
        self,
        first_frame_url: str,
        last_frame_url: str,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        resolution: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """
        创建首尾帧生视频任务
        
        Args:
            first_frame_url: 首帧图像URL（必选）
            last_frame_url: 尾帧图像URL（必选）
            prompt: 文本提示词（可选，最多800字符）
            model: 模型名称，默认 wan2.2-kf2v-flash
            resolution: 分辨率档位（480P/720P/1080P），默认720P
            prompt_extend: 智能改写，默认True
            watermark: 是否添加水印，默认False
            seed: 随机种子
            negative_prompt: 反向提示词
            
        Returns:
            任务 ID
        """
        model_name = model or "wan2.2-kf2v-flash"
        model_info = KEYFRAME_TO_VIDEO_MODELS.get(model_name, {})
        
        # 构建输入
        input_data = {
            "first_frame_url": first_frame_url,
            "last_frame_url": last_frame_url,
        }
        
        # 提示词
        if prompt:
            # wan2.2 限制800字符
            max_length = model_info.get("prompt_max_length", 800)
            input_data["prompt"] = prompt[:max_length]
        
        # 反向提示词
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt[:500]
        
        # 构建参数
        parameters = {}
        
        # 分辨率
        resolution_value = resolution or model_info.get("default_resolution", "720P")
        supported_resolutions = model_info.get("resolutions", ["480P", "720P", "1080P"])
        if resolution_value in supported_resolutions:
            parameters["resolution"] = resolution_value
        else:
            parameters["resolution"] = "720P"
        
        # 智能改写
        prompt_extend_value = prompt_extend if prompt_extend is not None else True
        parameters["prompt_extend"] = prompt_extend_value
        
        # 水印
        watermark_value = watermark if watermark is not None else False
        parameters["watermark"] = watermark_value
        
        # 种子
        if seed is not None:
            parameters["seed"] = seed
        
        request_body = {
            "model": model_name,
            "input": input_data
        }
        
        if parameters:
            request_body["parameters"] = parameters
        
        # 打印详细请求信息
        print(f"\n{'='*60}")
        print(f"[HTTP 首尾帧生视频请求] 模型: {model_name}")
        print(f"[HTTP 首尾帧生视频请求] URL: {self.base_url}/services/aigc/image2video/video-synthesis")
        print(f"[HTTP 首尾帧生视频请求] Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        # 发送 HTTP 请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/image2video/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"  # 必须设置为异步
                },
                json=request_body
            )
            
            result = response.json()
            
            # 打印详细响应信息
            print(f"\n{'='*60}")
            print(f"[HTTP 首尾帧生视频响应] status_code: {response.status_code}")
            print(f"[HTTP 首尾帧生视频响应] request_id: {result.get('request_id', 'N/A')}")
            if response.status_code == 200:
                output = result.get("output", {})
                print(f"[HTTP 首尾帧生视频响应] task_id: {output.get('task_id', 'N/A')}")
                print(f"[HTTP 首尾帧生视频响应] task_status: {output.get('task_status', 'N/A')}")
            else:
                print(f"[HTTP 首尾帧生视频响应] code: {result.get('code', 'N/A')}")
                print(f"[HTTP 首尾帧生视频响应] message: {result.get('message', 'N/A')}")
            print(f"[HTTP 首尾帧生视频响应] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"{'='*60}\n")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                raise Exception(f"创建首尾帧生视频任务失败: {code} - {message}")
            
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建首尾帧生视频任务失败: 未返回任务ID")
            
            return task_id
    
    async def get_task_status(self, task_id: str, project_id: str = "") -> Tuple[str, Optional[str]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            (状态, 视频URL) 元组，状态为 PENDING/RUNNING/SUCCEEDED/FAILED
            如果启用 OSS，视频 URL 将是 OSS URL
        """
        print(f"\n[HTTP 首尾帧生视频状态查询] task_id: {task_id}, URL: {self.base_url}/tasks/{task_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            
            result = response.json()
            
            # 打印详细状态信息
            output = result.get("output", {})
            status = output.get("task_status", "UNKNOWN")
            
            print(f"[HTTP 首尾帧生视频状态查询] status_code: {response.status_code}")
            print(f"[HTTP 首尾帧生视频状态查询] request_id: {result.get('request_id', 'N/A')}")
            print(f"[HTTP 首尾帧生视频状态查询] task_status: {status}")
            
            # 如果任务失败，输出详细的失败信息
            if status == "FAILED":
                print(f"\n{'!'*60}")
                print(f"[首尾帧生视频任务失败] 详细错误信息:")
                print(json.dumps({
                    "request_id": result.get('request_id', 'N/A'),
                    "output": {
                        "task_id": task_id,
                        "task_status": status,
                        "code": output.get('code', 'N/A'),
                        "message": output.get('message', 'N/A')
                    }
                }, ensure_ascii=False, indent=4))
                print(f"{'!'*60}\n")
            
            if output.get('video_url'):
                print(f"[HTTP 首尾帧生视频状态查询] video_url: {output.get('video_url')[:100]}...")
            if output.get('orig_prompt'):
                print(f"[HTTP 首尾帧生视频状态查询] orig_prompt: {output.get('orig_prompt')[:100]}...")
            if output.get('actual_prompt'):
                print(f"[HTTP 首尾帧生视频状态查询] actual_prompt: {output.get('actual_prompt')[:100]}...")
            if output.get('submit_time'):
                print(f"[HTTP 首尾帧生视频状态查询] submit_time: {output.get('submit_time')}")
            if output.get('end_time'):
                print(f"[HTTP 首尾帧生视频状态查询] end_time: {output.get('end_time')}")
            if result.get('usage'):
                print(f"[HTTP 首尾帧生视频状态查询] usage: {json.dumps(result.get('usage'), ensure_ascii=False)}")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                print(f"[HTTP 首尾帧生视频状态查询] 错误: {code} - {message}")
                raise Exception(f"查询首尾帧生视频任务状态失败: {code} - {message}")
            
            video_url = output.get("video_url")
            
            # 如果启用了 OSS，上传视频并返回 OSS URL（使用异步方法）
            if status == 'SUCCEEDED' and video_url and oss_service.is_enabled():
                video_url = await oss_service.upload_video_async(video_url, project_id)
            
            return status, video_url
