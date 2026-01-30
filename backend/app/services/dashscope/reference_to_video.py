"""
参考生视频服务 - 参考视频/图像生成视频
基于 wan2.6-r2v 模型，参考输入视频或图像中的角色形象（视频还可参考音色）生成新视频

官方文档: https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference

参考素材说明：
- 支持视频和图片作为参考素材
- 图片数量：0-5张
- 视频数量：0-3个
- 总数限制：图片+视频 ≤ 5
- 通过 character1, character2 等标识引用参考角色（按传入顺序）
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
    """参考生视频服务（参考视频/图像生成视频）"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.ref_video_config = config.ref_video
        self.base_url = config.base_url
    
    async def create_task(
        self,
        reference_urls: List[str],
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        duration: Optional[int] = None,
        shot_type: Optional[str] = None,
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """
        创建参考生视频任务
        
        Args:
            reference_urls: 参考素材URL列表（视频+图片，总数≤5，视频≤3，图片≤5）
            prompt: 文本提示词，使用 character1/character2... 指代参考素材中的角色
            model: 模型名称，默认 wan2.6-r2v
            size: 分辨率（宽*高格式，如 1920*1080），默认1080P 16:9
            duration: 视频时长（2-10秒整数），默认5秒
            shot_type: 镜头类型，single单镜头/multi多镜头叙事
            watermark: 是否添加水印
            seed: 随机种子
            negative_prompt: 反向提示词
            
        Returns:
            任务 ID
        """
        model_name = model or self.ref_video_config.model
        
        # 构建 input 参数
        input_data = {
            "prompt": prompt
        }
        
        if reference_urls:
            # 总数限制5个（API要求：图片+视频≤5）
            input_data["reference_urls"] = reference_urls[:5]
        
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
        
        # 注意：wan2.6-r2v 不再支持 audio 和 prompt_extend 参数
        # 音频由参考视频提取音色 + 提示词生成
        
        # 构建请求体
        request_body = {
            "model": model_name,
            "input": input_data
        }
        
        if parameters:
            request_body["parameters"] = parameters
        
        # 打印详细请求信息
        print(f"\n{'='*60}")
        print(f"[HTTP 参考生视频请求] 模型: {model_name}")
        print(f"[HTTP 参考生视频请求] URL: {self.base_url}/services/aigc/video-generation/video-synthesis")
        print(f"[HTTP 参考生视频请求] Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
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
            
            # 打印详细响应信息
            print(f"\n{'='*60}")
            print(f"[HTTP 参考生视频响应] status_code: {response.status_code}")
            print(f"[HTTP 参考生视频响应] request_id: {result.get('request_id', 'N/A')}")
            if response.status_code == 200:
                output = result.get("output", {})
                print(f"[HTTP 参考生视频响应] task_id: {output.get('task_id', 'N/A')}")
                print(f"[HTTP 参考生视频响应] task_status: {output.get('task_status', 'N/A')}")
            else:
                print(f"[HTTP 参考生视频响应] code: {result.get('code', 'N/A')}")
                print(f"[HTTP 参考生视频响应] message: {result.get('message', 'N/A')}")
            print(f"[HTTP 参考生视频响应] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"{'='*60}\n")
            
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
        print(f"\n[HTTP 参考生视频状态查询] task_id: {task_id}")
        print(f"[HTTP 参考生视频状态查询] URL: {self.base_url}/tasks/{task_id}")
        
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
            
            print(f"[HTTP 参考生视频状态查询] status_code: {response.status_code}")
            print(f"[HTTP 参考生视频状态查询] request_id: {result.get('request_id', 'N/A')}")
            print(f"[HTTP 参考生视频状态查询] task_status: {status}")
            
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
                print(f"[HTTP 参考生视频状态查询] video_url: {output.get('video_url')[:100]}...")
            if output.get('submit_time'):
                print(f"[HTTP 参考生视频状态查询] submit_time: {output.get('submit_time')}")
            if output.get('end_time'):
                print(f"[HTTP 参考生视频状态查询] end_time: {output.get('end_time')}")
            if result.get('usage'):
                print(f"[HTTP 参考生视频状态查询] usage: {json.dumps(result.get('usage'), ensure_ascii=False)}")
            
            if response.status_code != 200:
                error_code = result.get("code", "Unknown")
                error_message = result.get("message", "Unknown error")
                print(f"[HTTP 参考生视频状态查询] 错误: {error_code} - {error_message}")
                raise Exception(f"查询任务状态失败: {error_code} - {error_message}")
            
            video_url = output.get("video_url") if status == "SUCCEEDED" else None
        
        # 如果启用了 OSS，上传视频并返回 OSS URL（使用异步方法）
        if status == "SUCCEEDED" and video_url and oss_service.is_enabled():
            video_url = await oss_service.upload_video_async(video_url, project_id)
        
        return status, video_url
    
    def get_model_info(self, model: str = None) -> dict:
        """获取模型信息"""
        model_name = model or self.ref_video_config.model
        return REF_VIDEO_MODELS.get(model_name, {})

