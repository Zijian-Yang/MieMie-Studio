"""
阿里云 DashScope 文生视频服务封装

模型支持：
- wan2.6-t2v: 
  - 支持多镜头叙事、音频能力
  - 分辨率: 720P/1080P
  - 时长: 5/10/15秒
  - 支持自动配音或自定义音频
  - 支持镜头类型: single/multi
  - HTTP异步调用

- wan2.5-t2v-preview:
  - 支持音频能力
  - 分辨率: 480P/720P/1080P  
  - 时长: 5/10秒
  - 支持自动配音或自定义音频
  - HTTP异步调用

- wan2.2-t2v-plus:
  - 无声视频
  - 分辨率: 480P/1080P
  - 时长: 固定5秒
  - HTTP异步调用

- wanx2.1-t2v-turbo:
  - 无声视频，快速生成
  - 分辨率: 480P/720P
  - 时长: 固定5秒
  - HTTP异步调用

参考文档: https://help.aliyun.com/zh/model-studio/text-to-video-api
"""

import json
import logging
from typing import Optional, Tuple
import httpx

from app.config import get_config, TEXT_TO_VIDEO_MODELS
from app.services.oss import oss_service

# 配置日志
logger = logging.getLogger(__name__)


class TextToVideoService:
    """文生视频服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.t2v_config = config.text_to_video
        self.base_url = config.base_url
    
    async def create_task(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        duration: Optional[int] = None,
        prompt_extend: Optional[bool] = None,
        shot_type: Optional[str] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio_url: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """
        创建文生视频任务
        
        Args:
            prompt: 文本提示词（必选）
            model: 模型名称
            size: 分辨率（宽*高格式，如 1920*1080）
            duration: 视频时长（秒）
            prompt_extend: 智能改写
            shot_type: 镜头类型（single/multi，仅wan2.6支持，需prompt_extend=true）
            watermark: 是否添加水印
            seed: 随机种子
            audio_url: 自定义音频URL（仅wan2.5及以上支持）
            negative_prompt: 反向提示词
            
        Returns:
            任务 ID
        """
        model_name = model or self.t2v_config.model
        model_info = TEXT_TO_VIDEO_MODELS.get(model_name, {})
        
        # 判断模型版本
        is_wan26 = 'wan2.6' in model_name
        is_wan25 = 'wan2.5' in model_name
        is_wan25_or_newer = is_wan25 or is_wan26
        
        # 构建请求体
        input_data = {
            "prompt": prompt
        }
        
        # 反向提示词
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        # 自定义音频（仅 wan2.5 及以上支持）
        if audio_url and is_wan25_or_newer:
            input_data["audio_url"] = audio_url
        
        parameters = {}
        
        # 分辨率
        size_value = size or self.t2v_config.size
        if size_value:
            parameters["size"] = size_value
        
        # 视频时长
        duration_value = duration if duration is not None else self.t2v_config.duration
        supported_durations = model_info.get("durations", [5])
        if duration_value is not None:
            # 根据模型支持的时长限制
            if duration_value in supported_durations:
                parameters["duration"] = duration_value
            else:
                # 找到最接近的支持时长
                parameters["duration"] = min(supported_durations, key=lambda x: abs(x - duration_value))
        
        # 智能改写
        prompt_extend_value = prompt_extend if prompt_extend is not None else self.t2v_config.prompt_extend
        if prompt_extend_value is not None and model_info.get("supports_prompt_extend", True):
            parameters["prompt_extend"] = prompt_extend_value
        
        # 镜头类型（仅 wan2.6 支持，且需要 prompt_extend=true 才生效）
        if is_wan26 and model_info.get("supports_shot_type", False):
            shot_type_value = shot_type or self.t2v_config.shot_type
            if shot_type_value:
                parameters["shot_type"] = shot_type_value
        
        # 水印
        watermark_value = watermark if watermark is not None else self.t2v_config.watermark
        if watermark_value is not None and model_info.get("supports_watermark", True):
            parameters["watermark"] = watermark_value
        
        # 种子
        seed_value = seed if seed is not None else self.t2v_config.seed
        if seed_value is not None and model_info.get("supports_seed", True):
            parameters["seed"] = seed_value
        
        request_body = {
            "model": model_name,
            "input": input_data
        }
        
        if parameters:
            request_body["parameters"] = parameters
        
        # 打印详细请求信息
        print(f"\n{'='*60}")
        print(f"[HTTP 文生视频请求] 模型: {model_name}")
        print(f"[HTTP 文生视频请求] URL: {self.base_url}/services/aigc/video-generation/video-synthesis")
        print(f"[HTTP 文生视频请求] Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        # 发送 HTTP 请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/video-generation/video-synthesis",
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
            print(f"[HTTP 文生视频响应] status_code: {response.status_code}")
            print(f"[HTTP 文生视频响应] request_id: {result.get('request_id', 'N/A')}")
            if response.status_code == 200:
                output = result.get("output", {})
                print(f"[HTTP 文生视频响应] task_id: {output.get('task_id', 'N/A')}")
                print(f"[HTTP 文生视频响应] task_status: {output.get('task_status', 'N/A')}")
            else:
                print(f"[HTTP 文生视频响应] code: {result.get('code', 'N/A')}")
                print(f"[HTTP 文生视频响应] message: {result.get('message', 'N/A')}")
            print(f"[HTTP 文生视频响应] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"{'='*60}\n")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                raise Exception(f"创建文生视频任务失败: {code} - {message}")
            
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建文生视频任务失败: 未返回任务ID")
            
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
        print(f"\n[HTTP 文生视频状态查询] task_id: {task_id}, URL: {self.base_url}/tasks/{task_id}")
        
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
            
            print(f"[HTTP 文生视频状态查询] status_code: {response.status_code}")
            print(f"[HTTP 文生视频状态查询] request_id: {result.get('request_id', 'N/A')}")
            print(f"[HTTP 文生视频状态查询] task_status: {status}")
            
            # 如果任务失败，输出详细的失败信息
            if status == "FAILED":
                print(f"\n{'!'*60}")
                print(f"[文生视频任务失败] 详细错误信息:")
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
                print(f"[HTTP 文生视频状态查询] video_url: {output.get('video_url')[:100]}...")
            if output.get('orig_prompt'):
                print(f"[HTTP 文生视频状态查询] orig_prompt: {output.get('orig_prompt')[:100]}...")
            if output.get('actual_prompt'):
                print(f"[HTTP 文生视频状态查询] actual_prompt: {output.get('actual_prompt')[:100]}...")
            if output.get('submit_time'):
                print(f"[HTTP 文生视频状态查询] submit_time: {output.get('submit_time')}")
            if output.get('end_time'):
                print(f"[HTTP 文生视频状态查询] end_time: {output.get('end_time')}")
            if result.get('usage'):
                print(f"[HTTP 文生视频状态查询] usage: {json.dumps(result.get('usage'), ensure_ascii=False)}")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                print(f"[HTTP 文生视频状态查询] 错误: {code} - {message}")
                raise Exception(f"查询文生视频任务状态失败: {code} - {message}")
            
            video_url = output.get("video_url")
            
            # 如果启用了 OSS，上传视频并返回 OSS URL（使用异步方法）
            if status == 'SUCCEEDED' and video_url and oss_service.is_enabled():
                video_url = await oss_service.upload_video_async(video_url, project_id)
            
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
            status, video_url = await self.get_task_status(task_id, project_id)
            
            if status == 'SUCCEEDED':
                return video_url
            elif status == 'FAILED':
                raise Exception("文生视频任务失败")
            elif status in ['PENDING', 'RUNNING']:
                # 使用异步 sleep 避免阻塞事件循环
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
            else:
                raise Exception(f"未知的任务状态: {status}")
        
        raise Exception(f"文生视频任务超时（{max_wait_time}秒）")
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        duration: Optional[int] = None,
        prompt_extend: Optional[bool] = None,
        shot_type: Optional[str] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio_url: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        project_id: str = ""
    ) -> str:
        """
        生成视频（完整流程：创建任务并等待完成）
        
        Args:
            prompt: 文本提示词（必选）
            model: 模型名称
            size: 分辨率（宽*高格式）
            duration: 视频时长（秒）
            prompt_extend: 智能改写
            shot_type: 镜头类型
            watermark: 是否添加水印
            seed: 随机种子
            audio_url: 自定义音频URL
            negative_prompt: 反向提示词
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            视频 URL（如果启用 OSS，返回 OSS URL）
        """
        task_id = await self.create_task(
            prompt=prompt,
            model=model,
            size=size,
            duration=duration,
            prompt_extend=prompt_extend,
            shot_type=shot_type,
            watermark=watermark,
            seed=seed,
            audio_url=audio_url,
            negative_prompt=negative_prompt
        )
        return await self.wait_for_task(task_id, project_id)

