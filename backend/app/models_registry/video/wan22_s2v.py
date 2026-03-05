"""
万相2.2 数字人视频模型 (wan2.2-s2v)

API 文档: https://help.aliyun.com/zh/model-studio/digital-human-video-generation

模型特点:
- 基于单张图片和音频生成动作自然的说话、唱歌或表演视频
- 音频驱动口型、表情和动作同步
- 支持真人（肖像、半身、全身）及卡通人物
- 分辨率: 480P/720P
- 时长由输入音频决定（音频 <20s）
"""

import asyncio
from typing import Optional

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)


# ============ 模型定义 ============

WAN22_S2V_MODEL_INFO = ModelInfo(
    id="wan2.2-s2v",
    name="万相2.2 数字人",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="基于单张图片和音频生成口型同步的说话/唱歌/表演视频，支持真人和卡通人物",
    version="2.2",

    api_model_name="wan2.2-s2v",
    doc_url="https://help.aliyun.com/zh/model-studio/digital-human-video-generation",

    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=1,
        supports_negative_prompt=False,
        supports_seed=False,
        supports_prompt_extend=False,
        supports_watermark=False,
        supports_audio=True,
    ),

    parameters=[
        ModelParameter(
            name="image_url",
            label="人物图片",
            type=ParameterType.IMAGE_URL,
            description="人物图片URL（jpg/jpeg/png/bmp/webp，400-7000px）",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="audio_url",
            label="驱动音频",
            type=ParameterType.AUDIO_URL,
            description="音频URL（wav/mp3，<15MB，<20s，需清晰人声）",
            required=True,
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="resolution",
            label="分辨率",
            type=ParameterType.SELECT,
            description="输出视频分辨率档位，尽量保持与输入图像宽高比一致",
            required=False,
            default="720P",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="480P", label="480P (标清)"),
                    SelectOption(value="720P", label="720P (高清)"),
                ]
            ),
            group="generation",
            order=1,
        ),
    ],

    enabled=True,
)


# ============ 服务实现 ============

class Wan22S2VService(BaseModelService[str]):
    """万相2.2 数字人视频服务"""

    def __init__(self, model_info: ModelInfo = WAN22_S2V_MODEL_INFO):
        super().__init__(model_info)

    async def generate(
        self,
        image_url: str,
        audio_url: str,
        resolution: str = "720P",
        **kwargs,
    ) -> str:
        task_id = await self.create_task(
            image_url=image_url,
            audio_url=audio_url,
            resolution=resolution,
        )

        max_wait = 900  # 15 分钟超时（s2v 生成较慢）
        elapsed = 0
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)
            if result.status == TaskStatus.SUCCEEDED:
                return result.result
            elif result.status == TaskStatus.FAILED:
                raise Exception(f"数字人视频生成失败: {result.error_message}")
            await asyncio.sleep(10)
            elapsed += 10

        raise Exception("数字人视频生成超时")

    async def create_task(
        self,
        image_url: str,
        audio_url: str,
        resolution: str = "720P",
        **kwargs,
    ) -> str:
        import json
        import httpx

        request_body = {
            "model": self.model_info.api_model_name,
            "input": {
                "image_url": image_url,
                "audio_url": audio_url,
            },
            "parameters": {
                "resolution": resolution,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/services/aigc/image2video/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=request_body,
            )

            result = response.json()
            if response.status_code != 200:
                code = result.get("code", "Unknown")
                message = result.get("message", "未知错误")
                raise Exception(f"创建数字人视频任务失败: {code} - {message}")

            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise Exception("创建数字人视频任务失败: 未返回任务ID")

            return task_id

    async def get_task_status(self, task_id: str) -> TaskResult:
        import json
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )

            result = response.json()
            output = result.get("output", {})
            task_status = output.get("task_status", "UNKNOWN")

            status_map = {
                "PENDING": TaskStatus.PENDING,
                "RUNNING": TaskStatus.PROCESSING,
                "SUCCEEDED": TaskStatus.SUCCEEDED,
                "FAILED": TaskStatus.FAILED,
            }
            status = status_map.get(task_status, TaskStatus.PROCESSING)

            task_result = TaskResult(task_id=task_id, status=status)

            if status == TaskStatus.SUCCEEDED:
                # s2v 结果在 output.results.video_url
                results = output.get("results", {})
                video_url = results.get("video_url") if isinstance(results, dict) else None
                if not video_url:
                    video_url = output.get("video_url")
                task_result.result = video_url
            elif status == TaskStatus.FAILED:
                task_result.error_message = output.get("message", "未知错误")

            return task_result


# ============ 注册模型 ============

def register():
    registry.register(WAN22_S2V_MODEL_INFO, Wan22S2VService)


register()
