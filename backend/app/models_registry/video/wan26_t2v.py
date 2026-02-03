"""
万相2.6 文生视频模型 (wan2.6-t2v)

API 文档: https://help.aliyun.com/zh/model-studio/text-to-video-api

模型特点：
- 最新文生视频模型
- 支持多镜头叙事、自动配音
- 720P/1080P 分辨率
- 5/10/15秒时长
"""

from typing import Optional, List
import asyncio
import httpx

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry,
    SizeOption, SizeConstraints,
)


# ============ 分辨率选项 ============

# 720P 分辨率
RESOLUTIONS_720P = [
    SizeOption(width=1280, height=720, label="1280×720 (16:9 横屏)", aspect_ratio="16:9"),
    SizeOption(width=720, height=1280, label="720×1280 (9:16 竖屏)", aspect_ratio="9:16"),
    SizeOption(width=960, height=960, label="960×960 (1:1 方形)", aspect_ratio="1:1"),
    SizeOption(width=1088, height=832, label="1088×832 (4:3 横屏)", aspect_ratio="4:3"),
    SizeOption(width=832, height=1088, label="832×1088 (3:4 竖屏)", aspect_ratio="3:4"),
]

# 1080P 分辨率
RESOLUTIONS_1080P = [
    SizeOption(width=1920, height=1080, label="1920×1080 (16:9 横屏)", aspect_ratio="16:9"),
    SizeOption(width=1080, height=1920, label="1080×1920 (9:16 竖屏)", aspect_ratio="9:16"),
    SizeOption(width=1440, height=1440, label="1440×1440 (1:1 方形)", aspect_ratio="1:1"),
    SizeOption(width=1632, height=1248, label="1632×1248 (4:3 横屏)", aspect_ratio="4:3"),
    SizeOption(width=1248, height=1632, label="1248×1632 (3:4 竖屏)", aspect_ratio="3:4"),
]

# 合并所有分辨率供前端使用
ALL_RESOLUTIONS = RESOLUTIONS_1080P + RESOLUTIONS_720P


# ============ 模型定义 ============

WAN26_T2V_MODEL_INFO = ModelInfo(
    id="wan2.6-t2v",
    name="万相2.6 文生视频",
    type=ModelType.TEXT_TO_VIDEO,
    provider="dashscope",
    description="最新模型，支持多镜头叙事、自动配音，720P/1080P，5/10/15秒",
    version="2.6",
    
    api_model_name="wan2.6-t2v",
    doc_url="https://help.aliyun.com/zh/model-studio/text-to-video-api",
    
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
    ),
    
    common_sizes=ALL_RESOLUTIONS,
    recommended=True,
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的视频内容（最多1500字符）",
            required=True,
            constraint=ParameterConstraint(max_length=1500),
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="negative_prompt",
            label="负面提示词",
            type=ParameterType.TEXT,
            description="不希望出现的内容（最多500字符）",
            required=False,
            constraint=ParameterConstraint(max_length=500),
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
            type=ParameterType.SELECT,
            description="视频时长（秒）",
            required=False,
            default=5,
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value=5, label="5秒"),
                    SelectOption(value=10, label="10秒"),
                    SelectOption(value=15, label="15秒"),
                ]
            ),
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
            description="是否自动生成配音",
            required=False,
            default=True,
            group="audio",
            order=1,
        ),
        
        # === 高级参数 ===
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词",
            required=False,
            default=True,
            group="advanced",
            order=1,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            description="是否添加水印",
            required=False,
            default=False,
            group="advanced",
            order=2,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            description="固定种子可复现结果，留空为随机",
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="advanced",
            advanced=True,
            order=3,
        ),
    ],
)


# ============ 服务实现 ============

class Wan26T2VService(BaseModelService[str]):
    """万相2.6 文生视频服务"""
    
    def __init__(self, model_info: ModelInfo = WAN26_T2V_MODEL_INFO):
        super().__init__(model_info)
        self._base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2video/video-synthesis"
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._base_url = base_url.rstrip('/') + "/services/aigc/text2video/video-synthesis"
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1920*1080",
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
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            duration=duration,
            shot_type=shot_type,
            audio=audio,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
        )
        
        # 等待完成（视频生成时间较长）
        max_wait = 600  # 10分钟
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
        negative_prompt: str = "",
        size: str = "1920*1080",
        duration: int = 5,
        shot_type: str = "single",
        audio: bool = True,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建视频生成任务"""
        input_data = {"prompt": prompt}
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        parameters = {
            "size": size,
            "duration": duration,
            "shot_type": shot_type,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
        }
        
        if audio:
            parameters["audio"] = {"mode": "auto"}
        
        if seed is not None:
            parameters["seed"] = seed
        
        payload = {
            "model": "wan2.6-t2v",
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
    registry.register(WAN26_T2V_MODEL_INFO, Wan26T2VService)


register()
