"""
万相2.6 图生视频模型 (wan2.6-i2v, wan2.6-i2v-flash)

API 文档: https://help.aliyun.com/zh/model-studio/image-to-video-api-reference

模型特点：
- wan2.6-i2v-flash: 极速版，支持2-15秒连续时长、多镜头叙事
- wan2.6-i2v: 标准版，支持2-10秒连续时长
- 720P/1080P 分辨率
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

VIDEO_RESOLUTIONS = [
    SizeOption(width=1920, height=1080, label="1080P 全高清", aspect_ratio="16:9"),
    SizeOption(width=1280, height=720, label="720P 高清", aspect_ratio="16:9"),
]


# ============ wan2.6-i2v-flash 模型定义 ============

WAN26_I2V_FLASH_MODEL_INFO = ModelInfo(
    id="wan2.6-i2v-flash",
    name="万相2.6 图生视频 极速版",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="极速版，支持2-15秒连续时长、多镜头叙事、有声/无声切换",
    version="2.6",
    
    api_model_name="wan2.6-i2v-flash",
    doc_url="https://help.aliyun.com/zh/model-studio/image-to-video-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_audio=True,
        supports_reference_images=True,
        max_reference_images=1,
    ),
    
    common_sizes=VIDEO_RESOLUTIONS,
    recommended=True,
    
    parameters=[
        ModelParameter(
            name="image_url",
            label="参考图片",
            type=ParameterType.IMAGE_URL,
            description="参考图片URL",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的视频内容",
            required=False,
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容",
            required=False,
            group="basic",
            order=3,
        ),
        ModelParameter(
            name="resolution",
            label="分辨率",
            type=ParameterType.SELECT,
            description="视频分辨率",
            required=False,
            default="1080P",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1080P", label="1080P 全高清"),
                    SelectOption(value="720P", label="720P 高清"),
                ]
            ),
            group="video",
            order=1,
        ),
        ModelParameter(
            name="duration",
            label="视频时长",
            type=ParameterType.INTEGER,
            description="视频时长（2-15秒）",
            required=False,
            default=5,
            constraint=ParameterConstraint(min_value=2, max_value=15),
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
        ModelParameter(
            name="audio",
            label="自动配音",
            type=ParameterType.BOOLEAN,
            description="是否自动生成配音",
            required=False,
            default=True,
            group="audio",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            required=False,
            default=True,
            group="advanced",
            order=1,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            required=False,
            default=False,
            group="advanced",
            order=2,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="advanced",
            advanced=True,
            order=3,
        ),
    ],
)


# ============ wan2.6-i2v 模型定义 ============

WAN26_I2V_MODEL_INFO = ModelInfo(
    id="wan2.6-i2v",
    name="万相2.6 图生视频 标准版",
    type=ModelType.IMAGE_TO_VIDEO,
    provider="dashscope",
    description="标准版，支持2-10秒连续时长",
    version="2.6",
    
    api_model_name="wan2.6-i2v",
    doc_url="https://help.aliyun.com/zh/model-studio/image-to-video-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=False,
        supports_async=True,
        max_concurrent=3,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_watermark=True,
        supports_audio=True,
        supports_reference_images=True,
        max_reference_images=1,
    ),
    
    common_sizes=VIDEO_RESOLUTIONS,
    
    parameters=[
        ModelParameter(
            name="image_url",
            label="参考图片",
            type=ParameterType.IMAGE_URL,
            description="参考图片URL",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的视频内容",
            required=False,
            group="basic",
            order=2,
        ),
        ModelParameter(
            name="resolution",
            label="分辨率",
            type=ParameterType.SELECT,
            description="视频分辨率",
            required=False,
            default="1080P",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1080P", label="1080P 全高清"),
                    SelectOption(value="720P", label="720P 高清"),
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
            name="audio",
            label="自动配音",
            type=ParameterType.BOOLEAN,
            required=False,
            default=True,
            group="audio",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            required=False,
            default=True,
            group="advanced",
            order=1,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            required=False,
            default=False,
            group="advanced",
            order=2,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="advanced",
            advanced=True,
            order=3,
        ),
    ],
)


# ============ 服务实现 ============

class Wan26I2VService(BaseModelService[str]):
    """万相2.6 图生视频服务"""
    
    def __init__(self, model_info: ModelInfo = WAN26_I2V_FLASH_MODEL_INFO):
        super().__init__(model_info)
        self._base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._base_url = base_url.rstrip('/') + "/services/aigc/image2video/video-synthesis"
    
    async def generate(
        self,
        image_url: str,
        prompt: str = "",
        negative_prompt: str = "",
        resolution: str = "1080P",
        duration: int = 5,
        shot_type: str = "single",
        audio: bool = True,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """生成视频，返回视频URL"""
        task_id = await self.create_task(
            image_url=image_url,
            prompt=prompt,
            negative_prompt=negative_prompt,
            resolution=resolution,
            duration=duration,
            shot_type=shot_type,
            audio=audio,
            prompt_extend=prompt_extend,
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
        image_url: str,
        prompt: str = "",
        negative_prompt: str = "",
        resolution: str = "1080P",
        duration: int = 5,
        shot_type: str = "single",
        audio: bool = True,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建视频生成任务"""
        input_data = {"image_url": image_url}
        if prompt:
            input_data["prompt"] = prompt
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        parameters = {
            "resolution": resolution,
            "duration": duration,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
        }
        
        # 极速版支持镜头类型
        if self.model_info.id == "wan2.6-i2v-flash":
            parameters["shot_type"] = shot_type
        
        if audio:
            parameters["audio"] = {"mode": "auto"}
        
        if seed is not None:
            parameters["seed"] = seed
        
        payload = {
            "model": self.model_info.api_model_name,
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
    registry.register(WAN26_I2V_FLASH_MODEL_INFO, Wan26I2VService)
    # 标准版使用相同的服务实现
    registry.register(WAN26_I2V_MODEL_INFO, lambda mi=WAN26_I2V_MODEL_INFO: Wan26I2VService(mi))


register()
