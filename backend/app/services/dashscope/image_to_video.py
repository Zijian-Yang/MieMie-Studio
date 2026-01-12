"""
阿里云 DashScope 图生视频服务封装

模型参数差异：
- wan2.6-i2v:
  - 图片参数: img_url
  - 分辨率参数: resolution (720P/1080P)
  - 支持 duration (5/10/15秒)
  - 支持音频: audio_url, audio
  - 支持镜头类型: shot_type (single/multi)
  - 需要通过 HTTP 请求调用

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

import json
import logging
from typing import Optional, Tuple
from http import HTTPStatus
import dashscope
from dashscope import VideoSynthesis
import httpx

from app.config import get_config, VIDEO_MODELS
from app.services.oss import oss_service

# 配置日志
logger = logging.getLogger(__name__)


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
        negative_prompt: Optional[str] = None,
        shot_type: Optional[str] = None  # 镜头类型：single/multi（仅wan2.6支持）
    ) -> str:
        """
        创建视频生成任务
        
        Args:
            image_url: 首帧图片 URL
            prompt: 视频生成提示词
            model: 模型名称（使用配置默认值）
            resolution: 分辨率（wan2.5/2.6用480P/720P/1080P，wanx2.1用宽*高）
            duration: 视频时长（秒）
            prompt_extend: 智能改写（使用配置默认值）
            watermark: 水印（使用配置默认值）
            seed: 种子（使用配置默认值）
            audio_url: 音频URL（仅wan2.5/2.6支持）
            audio: 是否自动生成音频（仅wan2.5/2.6支持）
            negative_prompt: 负面提示词
            shot_type: 镜头类型 single/multi（仅wan2.6支持）
            
        Returns:
            任务 ID
        """
        model_name = model or self.video_config.model
        is_wan26 = 'wan2.6' in model_name
        is_wan25 = 'wan2.5' in model_name
        is_wan25_or_newer = is_wan25 or is_wan26
        
        # wan2.6 需要通过 HTTP 请求调用
        if is_wan26:
            return await self._create_task_http(
                image_url=image_url,
                prompt=prompt,
                model=model_name,
                resolution=resolution,
                duration=duration,
                prompt_extend=prompt_extend,
                watermark=watermark,
                seed=seed,
                audio_url=audio_url,
                audio=audio,
                negative_prompt=negative_prompt,
                shot_type=shot_type
            )
        
        # 其他模型使用 SDK 调用
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
        
        # 打印详细请求信息
        log_params = {k: v for k, v in params.items() if k != 'api_key'}
        print(f"\n{'='*60}")
        print(f"[SDK 图生视频请求] 模型: {model_name}")
        print(f"[SDK 图生视频请求] 参数: {json.dumps(log_params, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        rsp = VideoSynthesis.async_call(**params)
        
        # 打印响应信息
        print(f"\n{'='*60}")
        print(f"[SDK 图生视频响应] status_code: {rsp.status_code}")
        print(f"[SDK 图生视频响应] request_id: {getattr(rsp, 'request_id', 'N/A')}")
        if rsp.status_code == HTTPStatus.OK:
            print(f"[SDK 图生视频响应] task_id: {rsp.output.task_id}")
            print(f"[SDK 图生视频响应] task_status: {rsp.output.task_status}")
        else:
            print(f"[SDK 图生视频响应] code: {rsp.code}")
            print(f"[SDK 图生视频响应] message: {rsp.message}")
        print(f"{'='*60}\n")
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建视频任务失败: {rsp.code} - {rsp.message}")
        
        return rsp.output.task_id
    
    async def _create_task_http(
        self,
        image_url: str,
        prompt: str = "",
        model: str = "wan2.6-i2v",
        resolution: Optional[str] = None,
        duration: Optional[int] = None,
        prompt_extend: Optional[bool] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        audio_url: Optional[str] = None,
        audio: Optional[bool] = None,
        negative_prompt: Optional[str] = None,
        shot_type: Optional[str] = None
    ) -> str:
        """
        通过 HTTP 请求创建视频生成任务（用于 wan2.6 模型）
        """
        config = get_config()
        base_url = config.base_url
        
        # 构建请求体
        input_data = {
            "img_url": image_url
        }
        
        if prompt:
            input_data["prompt"] = prompt
        
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        if audio_url:
            input_data["audio_url"] = audio_url
        
        parameters = {}
        
        # 分辨率
        resolution_value = resolution or self.video_config.resolution
        if resolution_value:
            parameters["resolution"] = resolution_value
        
        # 视频时长（wan2.6 支持 5/10/15秒）
        duration_value = duration if duration is not None else self.video_config.duration
        if duration_value is not None:
            parameters["duration"] = max(5, min(15, duration_value))
        
        # 智能改写
        prompt_extend_value = prompt_extend if prompt_extend is not None else self.video_config.prompt_extend
        if prompt_extend_value is not None:
            parameters["prompt_extend"] = prompt_extend_value
        
        # 水印
        watermark_value = watermark if watermark is not None else self.video_config.watermark
        if watermark_value is not None:
            parameters["watermark"] = watermark_value
        
        # 种子
        seed_value = seed if seed is not None else self.video_config.seed
        if seed_value is not None:
            parameters["seed"] = seed_value
        
        # 音频参数
        if not audio_url:
            audio_value = audio if audio is not None else self.video_config.audio
            if audio_value is not None:
                parameters["audio"] = audio_value
        
        # 镜头类型（仅 wan2.6 支持，且需要 prompt_extend=true 才生效）
        shot_type_value = shot_type or getattr(self.video_config, 'shot_type', None)
        if shot_type_value:
            parameters["shot_type"] = shot_type_value
        
        request_body = {
            "model": model,
            "input": input_data
        }
        
        if parameters:
            request_body["parameters"] = parameters
        
        # 打印详细请求信息
        print(f"\n{'='*60}")
        print(f"[HTTP 图生视频请求] 模型: {model}")
        print(f"[HTTP 图生视频请求] URL: {base_url}/services/aigc/video-generation/video-synthesis")
        print(f"[HTTP 图生视频请求] Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        # 发送 HTTP 请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/services/aigc/video-generation/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json=request_body
            )
            
            result = response.json()
            
            # 打印详细响应信息
            print(f"\n{'='*60}")
            print(f"[HTTP 图生视频响应] status_code: {response.status_code}")
            print(f"[HTTP 图生视频响应] request_id: {result.get('request_id', 'N/A')}")
            if response.status_code == 200:
                output = result.get("output", {})
                print(f"[HTTP 图生视频响应] task_id: {output.get('task_id', 'N/A')}")
                print(f"[HTTP 图生视频响应] task_status: {output.get('task_status', 'N/A')}")
            else:
                print(f"[HTTP 图生视频响应] code: {result.get('code', 'N/A')}")
                print(f"[HTTP 图生视频响应] message: {result.get('message', 'N/A')}")
            print(f"[HTTP 图生视频响应] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"{'='*60}\n")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                raise Exception(f"创建视频任务失败: {code} - {message}")
            
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建视频任务失败: 未返回任务ID")
            
            return task_id
    
    async def _get_task_status_http(self, task_id: str) -> Tuple[str, Optional[str]]:
        """
        通过 HTTP 请求获取任务状态
        """
        config = get_config()
        base_url = config.base_url
        
        print(f"\n[HTTP 状态查询] task_id: {task_id}, URL: {base_url}/tasks/{task_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            
            result = response.json()
            
            # 打印详细状态信息
            output = result.get("output", {})
            status = output.get("task_status", "UNKNOWN")
            
            print(f"[HTTP 状态查询] status_code: {response.status_code}")
            print(f"[HTTP 状态查询] request_id: {result.get('request_id', 'N/A')}")
            print(f"[HTTP 状态查询] task_status: {status}")
            
            # 如果任务失败，输出详细的失败信息
            if status == "FAILED":
                print(f"\n{'!'*60}")
                print(f"[任务失败] 详细错误信息:")
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
                print(f"[HTTP 状态查询] video_url: {output.get('video_url')[:100]}...")
            if output.get('submit_time'):
                print(f"[HTTP 状态查询] submit_time: {output.get('submit_time')}")
            if output.get('scheduled_time'):
                print(f"[HTTP 状态查询] scheduled_time: {output.get('scheduled_time')}")
            if output.get('end_time'):
                print(f"[HTTP 状态查询] end_time: {output.get('end_time')}")
            if result.get('usage'):
                print(f"[HTTP 状态查询] usage: {json.dumps(result.get('usage'), ensure_ascii=False)}")
            
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                print(f"[HTTP 状态查询] 错误: {code} - {message}")
                raise Exception(f"查询任务状态失败: {code} - {message}")
            
            video_url = output.get("video_url")
            
            return status, video_url
    
    async def get_task_status(self, task_id: str, project_id: str = "", use_http: bool = False) -> Tuple[str, Optional[str]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径
            use_http: 是否使用 HTTP 请求（wan2.6 需要）
            
        Returns:
            (状态, 视频URL) 元组，状态为 PENDING/PROCESSING/SUCCEEDED/FAILED
            如果启用 OSS，视频 URL 将是 OSS URL
        """
        # 如果指定使用 HTTP 或者默认尝试 HTTP 查询
        if use_http:
            print(f"\n[状态查询] 使用 HTTP 方式查询, task_id: {task_id}")
            status, video_url = await self._get_task_status_http(task_id)
        else:
            # 尝试使用 SDK
            print(f"\n[状态查询] 使用 SDK 方式查询, task_id: {task_id}")
            try:
                rsp = VideoSynthesis.fetch(
                    api_key=self.api_key,
                    task=task_id
                )
                
                print(f"[SDK 状态查询] status_code: {rsp.status_code}")
                print(f"[SDK 状态查询] request_id: {getattr(rsp, 'request_id', 'N/A')}")
                
                if rsp.status_code != HTTPStatus.OK:
                    print(f"[SDK 状态查询] SDK查询失败，切换到HTTP方式")
                    # SDK 查询失败，尝试 HTTP
                    status, video_url = await self._get_task_status_http(task_id)
                else:
                    status = rsp.output.task_status
                    video_url = rsp.output.video_url if status == 'SUCCEEDED' else None
                    print(f"[SDK 状态查询] task_status: {status}")
                    if video_url:
                        print(f"[SDK 状态查询] video_url: {video_url[:100]}...")
            except Exception as e:
                print(f"[SDK 状态查询] SDK异常: {e}，切换到HTTP方式")
                # SDK 异常，尝试 HTTP
                status, video_url = await self._get_task_status_http(task_id)
        
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
            rsp = VideoSynthesis.fetch(
                api_key=self.api_key,
                task=task_id
            )
            
            if rsp.status_code != HTTPStatus.OK:
                raise Exception(f"任务查询失败: {rsp.code} - {rsp.message}")
            
            task_status = rsp.output.task_status
            
            if task_status == 'SUCCEEDED':
                video_url = rsp.output.video_url
                # 如果启用了 OSS，上传视频并返回 OSS URL（使用异步方法）
                if oss_service.is_enabled():
                    video_url = await oss_service.upload_video_async(video_url, project_id)
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
