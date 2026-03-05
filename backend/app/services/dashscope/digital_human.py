"""
阿里云 DashScope 数字人视频服务封装

模型支持：
- wan2.2-s2v:
  - 基于单张图片和音频生成动作自然的说话、唱歌或表演视频
  - 音频驱动口型、表情和动作同步
  - 支持真人（肖像、半身、全身）及卡通人物
  - 分辨率: 480P/720P（默认720P）
  - 音频限制: wav/mp3, <15MB, <20s, 需清晰人声

参考文档: https://help.aliyun.com/zh/model-studio/digital-human-video-generation
"""

import json
import logging
from typing import Optional, Tuple
import httpx

from app.config import get_config, VIDEO_MODELS
from app.services.oss import oss_service

logger = logging.getLogger(__name__)


class DigitalHumanService:
    """数字人视频服务（图片+音频 → 说话视频）"""

    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.base_url = config.base_url

    async def create_task(
        self,
        image_url: str,
        audio_url: str,
        model: str = "wan2.2-s2v",
        resolution: Optional[str] = None,
    ) -> str:
        """
        创建数字人视频任务

        Args:
            image_url: 人物图片URL（必选, jpg/jpeg/png/bmp/webp, 400-7000px）
            audio_url: 音频URL（必选, wav/mp3, <15MB, <20s）
            model: 模型名称，默认 wan2.2-s2v
            resolution: 分辨率档位（480P/720P），默认720P

        Returns:
            任务 ID
        """
        model_info = VIDEO_MODELS.get(model, {})

        resolution_value = resolution or model_info.get("default_resolution", "720P")
        supported = model_info.get("resolutions", [{"value": "480P"}, {"value": "720P"}])
        supported_values = [r["value"] if isinstance(r, dict) else r for r in supported]
        if resolution_value not in supported_values:
            resolution_value = "720P"

        request_body = {
            "model": model,
            "input": {
                "image_url": image_url,
                "audio_url": audio_url,
            },
            "parameters": {
                "resolution": resolution_value,
            },
        }

        print(f"\n{'='*60}")
        print(f"[HTTP 数字人视频请求] 模型: {model}")
        print(f"[HTTP 数字人视频请求] URL: {self.base_url}/services/aigc/image2video/video-synthesis")
        print(f"[HTTP 数字人视频请求] Body: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/image2video/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=request_body,
            )

            result = response.json()

            print(f"\n{'='*60}")
            print(f"[HTTP 数字人视频响应] status_code: {response.status_code}")
            print(f"[HTTP 数字人视频响应] request_id: {result.get('request_id', 'N/A')}")
            if response.status_code == 200:
                output = result.get("output", {})
                print(f"[HTTP 数字人视频响应] task_id: {output.get('task_id', 'N/A')}")
                print(f"[HTTP 数字人视频响应] task_status: {output.get('task_status', 'N/A')}")
            else:
                print(f"[HTTP 数字人视频响应] code: {result.get('code', 'N/A')}")
                print(f"[HTTP 数字人视频响应] message: {result.get('message', 'N/A')}")
            print(f"[HTTP 数字人视频响应] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"{'='*60}\n")

            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                raise Exception(f"创建数字人视频任务失败: {code} - {message}")

            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建数字人视频任务失败: 未返回任务ID")

            return task_id

    async def get_task_status(self, task_id: str, project_id: str = "") -> Tuple[str, Optional[str]]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID
            project_id: 项目ID，用于 OSS 上传路径

        Returns:
            (状态, 视频URL) 元组，状态为 PENDING/RUNNING/SUCCEEDED/FAILED
        """
        print(f"\n[HTTP 数字人视频状态查询] task_id: {task_id}, URL: {self.base_url}/tasks/{task_id}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            result = response.json()
            output = result.get("output", {})
            status = output.get("task_status", "UNKNOWN")

            print(f"[HTTP 数字人视频状态查询] status_code: {response.status_code}")
            print(f"[HTTP 数字人视频状态查询] request_id: {result.get('request_id', 'N/A')}")
            print(f"[HTTP 数字人视频状态查询] task_status: {status}")

            if status == "FAILED":
                print(f"\n{'!'*60}")
                print(f"[数字人视频任务失败] 详细错误信息:")
                print(json.dumps({
                    "request_id": result.get("request_id", "N/A"),
                    "output": {
                        "task_id": task_id,
                        "task_status": status,
                        "code": output.get("code", "N/A"),
                        "message": output.get("message", "N/A"),
                    },
                }, ensure_ascii=False, indent=4))
                print(f"{'!'*60}\n")

            # s2v 返回结构: output.results.video_url
            video_url = None
            results = output.get("results", {})
            if isinstance(results, dict):
                video_url = results.get("video_url")
            if not video_url:
                video_url = output.get("video_url")

            if video_url:
                print(f"[HTTP 数字人视频状态查询] video_url: {video_url[:100]}...")
            if output.get("submit_time"):
                print(f"[HTTP 数字人视频状态查询] submit_time: {output.get('submit_time')}")
            if output.get("end_time"):
                print(f"[HTTP 数字人视频状态查询] end_time: {output.get('end_time')}")
            if result.get("usage"):
                print(f"[HTTP 数字人视频状态查询] usage: {json.dumps(result.get('usage'), ensure_ascii=False)}")

            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                print(f"[HTTP 数字人视频状态查询] 错误: {code} - {message}")
                raise Exception(f"查询数字人视频任务状态失败: {code} - {message}")

            if status == "SUCCEEDED" and video_url and oss_service.is_enabled():
                video_url = await oss_service.upload_video_async(video_url, project_id)

            return status, video_url
