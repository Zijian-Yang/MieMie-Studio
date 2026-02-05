"""
万相2.6 参考生视频模型 (wan2.6-r2v)

API 文档: https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference

模型特点：
- 参考输入视频或图像中的角色形象生成新视频
- 视频参考可提取音色
- 支持多镜头叙事
- 720P/1080P，2-10秒
"""

from typing import Optional, List
import asyncio
import httpx

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry,
    SizeOption,
)


# ============ 分辨率选项 ============

RESOLUTIONS_720P = [
    SizeOption(width=1280, height=720, label="1280×720 (16:9 横屏)", aspect_ratio="16:9"),
    SizeOption(width=720, height=1280, label="720×1280 (9:16 竖屏)", aspect_ratio="9:16"),
    SizeOption(width=960, height=960, label="960×960 (1:1 方形)", aspect_ratio="1:1"),
]

RESOLUTIONS_1080P = [
    SizeOption(width=1920, height=1080, label="1920×1080 (16:9 横屏)", aspect_ratio="16:9"),
    SizeOption(width=1080, height=1920, label="1080×1920 (9:16 竖屏)", aspect_ratio="9:16"),
    SizeOption(width=1440, height=1440, label="1440×1440 (1:1 方形)", aspect_ratio="1:1"),
]

ALL_RESOLUTIONS = RESOLUTIONS_1080P + RESOLUTIONS_720P


# ============ 模型定义 ============

WAN26_R2V_MODEL_INFO = ModelInfo(
    id="wan2.6-r2v",
    name="万相2.6 参考生视频",
    type=ModelType.REFERENCE_TO_VIDEO,
    provider="dashscope",
    description="参考输入视频或图像中的角色形象，生成保持角色一致性的新视频，支持多镜头叙事",
    version="2.6",
    
    api_model_name="wan2.6-r2v",
    doc_url="https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=2,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_watermark=True,
        supports_audio=True,
        supports_reference_images=True,
        max_reference_images=5,  # 图片+视频总数不超过5
    ),
    
    common_sizes=ALL_RESOLUTIONS,
    recommended=True,
    
    parameters=[
        # === 参考素材 ===
        ModelParameter(
            name="reference_images",
            label="参考图片",
            type=ParameterType.IMAGE_URLS,
            description="参考图片URL列表（最多5张，与视频合计不超过5个）",
            required=False,
            constraint=ParameterConstraint(max_length=5),
            group="reference",
            order=1,
        ),
        ModelParameter(
            name="reference_videos",
            label="参考视频",
            type=ParameterType.TEXT,  # 实际是视频URL列表
            description="参考视频URL列表（最多3个，与图片合计不超过5个）",
            required=False,
            group="reference",
            order=2,
        ),
        
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的视频内容",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容",
            required=False,
            group="basic",
            order=2,
        ),
        
        # === 视频参数 ===
        ModelParameter(
            name="size",
            label="分辨率",
            type=ParameterType.SELECT,
            description="视频分辨率",
            required=False,
            default="1920*1080",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1920*1080", label="1920×1080 (16:9 横屏 1080P)"),
                    SelectOption(value="1080*1920", label="1080×1920 (9:16 竖屏 1080P)"),
                    SelectOption(value="1440*1440", label="1440×1440 (1:1 方形 1080P)"),
                    SelectOption(value="1280*720", label="1280×720 (16:9 横屏 720P)"),
                    SelectOption(value="720*1280", label="720×1280 (9:16 竖屏 720P)"),
                    SelectOption(value="960*960", label="960×960 (1:1 方形 720P)"),
                ]
            ),
            group="video",
            order=1,
        ),
        ModelParameter(
            name="duration",
            label="视频时长",
            type=ParameterType.INTEGER,
            description="视频时长（2-10秒）",
            required=False,
            default=5,
            constraint=ParameterConstraint(min_value=2, max_value=10),
            group="video",
            order=2,
        ),
        ModelParameter(
            name="shot_type",
            label="镜头类型",
            type=ParameterType.SELECT,
            description="单镜头或多镜头叙事",
            required=False,
            default="single",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="single", label="单镜头"),
                    SelectOption(value="multi", label="多镜头叙事"),
                ]
            ),
            group="video",
            order=3,
        ),
        
        # === 音频参数 ===
        ModelParameter(
            name="audio",
            label="自动配音",
            type=ParameterType.BOOLEAN,
            description="是否自动生成配音（参考视频可提取音色）",
            required=False,
            default=True,
            group="audio",
            order=1,
        ),
        
        # === 高级参数 ===
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            required=False,
            default=False,
            group="advanced",
            order=1,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="advanced",
            advanced=True,
            order=2,
        ),
    ],
)


# ============ 服务实现 ============

class Wan26R2VService(BaseModelService[str]):
    """万相2.6 参考生视频服务"""
    
    def __init__(self, model_info: ModelInfo = WAN26_R2V_MODEL_INFO):
        super().__init__(model_info)
        self._base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video2video/video-synthesis"
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._base_url = base_url.rstrip('/') + "/services/aigc/video2video/video-synthesis"
    
    async def generate(
        self,
        prompt: str,
        reference_images: List[str] = None,
        reference_videos: List[str] = None,
        negative_prompt: str = "",
        size: str = "1920*1080",
        duration: int = 5,
        shot_type: str = "single",
        audio: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """生成视频，返回视频URL"""
        task_id = await self.create_task(
            prompt=prompt,
            reference_images=reference_images,
            reference_videos=reference_videos,
            negative_prompt=negative_prompt,
            size=size,
            duration=duration,
            shot_type=shot_type,
            audio=audio,
            watermark=watermark,
            seed=seed,
        )
        
        max_wait = 600
        elapsed = 0
        
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)
            if result.status == TaskStatus.SUCCEEDED:
                return result.result or ""
            elif result.status == TaskStatus.FAILED:
                raise Exception(f"视频生成失败: {result.error_message}")
            
            await asyncio.sleep(5)
            elapsed += 5
        
        raise Exception("视频生成超时")
    
    async def create_task(
        self,
        prompt: str,
        reference_images: List[str] = None,
        reference_videos: List[str] = None,
        negative_prompt: str = "",
        size: str = "1920*1080",
        duration: int = 5,
        shot_type: str = "single",
        audio: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建视频生成任务"""
        input_data = {"prompt": prompt}
        
        if reference_images:
            input_data["reference_images"] = reference_images
        if reference_videos:
            input_data["reference_videos"] = reference_videos
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        parameters = {
            "size": size,
            "duration": duration,
            "shot_type": shot_type,
            "watermark": watermark,
        }
        
        if audio:
            parameters["audio"] = {"mode": "auto"}
        
        if seed is not None:
            parameters["seed"] = seed
        
        payload = {
            "model": "wan2.6-r2v",
            "input": input_data,
            "parameters": parameters,
        }
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self._base_url, json=payload, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"创建任务失败: HTTP {response.status_code} - {response.text}")
            
            result = response.json()
            if "output" in result and "task_id" in result["output"]:
                return result["output"]["task_id"]
            
            raise Exception(f"创建任务失败: {result}")
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """获取任务状态"""
        url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"查询失败: HTTP {response.status_code}"
                )
            
            data = response.json()
            status_map = {
                'PENDING': TaskStatus.PENDING,
                'RUNNING': TaskStatus.PROCESSING,
                'SUCCEEDED': TaskStatus.SUCCEEDED,
                'FAILED': TaskStatus.FAILED,
            }
            
            task_status = data.get("output", {}).get("task_status", "PENDING")
            status = status_map.get(task_status, TaskStatus.PROCESSING)
            
            result = TaskResult(task_id=task_id, status=status)
            
            if status == TaskStatus.SUCCEEDED:
                video_url = data.get("output", {}).get("video_url", "")
                result.result = video_url
            elif status == TaskStatus.FAILED:
                result.error_message = data.get("output", {}).get("message", "未知错误")
            
            return result


# ============ 注册模型 ============

def register():
    registry.register(WAN26_R2V_MODEL_INFO, Wan26R2VService)


register()
