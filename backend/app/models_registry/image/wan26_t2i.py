"""
万相2.6 文生图模型 (wan2.6-t2i)

API 文档: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference

模型特点：
- HTTP异步调用，快速生成高质量图像
- 单请求最多4张图
- 总像素范围 [1280*1280, 1440*1440] (更高分辨率)
- 宽高比范围 1:4 到 4:1
"""

from typing import Optional, List
from http import HTTPStatus
import asyncio
import httpx

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry,
    SizeOption, SizeConstraints,
)


# ============ 模型定义 ============

WAN26_T2I_COMMON_SIZES = [
    SizeOption(width=1280, height=1280, label="1:1 方形 (默认)", aspect_ratio="1:1"),
    SizeOption(width=1440, height=1440, label="1:1 方形 (大)", aspect_ratio="1:1"),
    SizeOption(width=1712, height=960, label="16:9 横屏", aspect_ratio="16:9"),
    SizeOption(width=960, height=1712, label="9:16 竖屏", aspect_ratio="9:16"),
    SizeOption(width=1488, height=1104, label="4:3 横屏", aspect_ratio="4:3"),
    SizeOption(width=1104, height=1488, label="3:4 竖屏", aspect_ratio="3:4"),
    SizeOption(width=1440, height=1152, label="5:4 横屏", aspect_ratio="5:4"),
    SizeOption(width=1152, height=1440, label="4:5 竖屏", aspect_ratio="4:5"),
]

WAN26_T2I_SIZE_CONSTRAINTS = SizeConstraints(
    min_pixels=1280 * 1280,  # 1,638,400
    max_pixels=1440 * 1440,  # 2,073,600
    min_ratio=0.25,  # 1:4
    max_ratio=4.0,  # 4:1
)

WAN26_T2I_MODEL_INFO = ModelInfo(
    id="wan2.6-t2i",
    name="万相2.6 文生图",
    type=ModelType.TEXT_TO_IMAGE,
    provider="dashscope",
    description="HTTP异步调用，快速生成高质量图像，单请求最多4张图，更高分辨率",
    version="2.6",
    
    api_model_name="wan2.6-t2i",
    doc_url="https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=True,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
    ),
    
    size_constraints=WAN26_T2I_SIZE_CONSTRAINTS,
    common_sizes=WAN26_T2I_COMMON_SIZES,
    recommended=True,  # 推荐模型
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="提示词",
            type=ParameterType.TEXT,
            description="描述要生成的图片内容",
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
        
        # === 尺寸参数 ===
        ModelParameter(
            name="size",
            label="图片尺寸",
            type=ParameterType.SELECT,
            description="预设尺寸，总像素需在 1638400-2073600 之间",
            required=False,
            default="1280*1280",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1280*1280", label="1280×1280 (1:1 方形 默认)"),
                    SelectOption(value="1440*1440", label="1440×1440 (1:1 方形 大)"),
                    SelectOption(value="1712*960", label="1712×960 (16:9 横屏)"),
                    SelectOption(value="960*1712", label="960×1712 (9:16 竖屏)"),
                    SelectOption(value="1488*1104", label="1488×1104 (4:3 横屏)"),
                    SelectOption(value="1104*1488", label="1104×1488 (3:4 竖屏)"),
                    SelectOption(value="1440*1152", label="1440×1152 (5:4 横屏)"),
                    SelectOption(value="1152*1440", label="1152×1440 (4:5 竖屏)"),
                ]
            ),
            group="size",
            order=1,
        ),
        
        # === 生成参数 ===
        ModelParameter(
            name="n",
            label="生成数量",
            type=ParameterType.INTEGER,
            description="一次生成的图片数量",
            required=False,
            default=4,
            constraint=ParameterConstraint(min_value=1, max_value=4),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="prompt_extend",
            label="智能改写",
            type=ParameterType.BOOLEAN,
            description="自动优化和扩展提示词",
            required=False,
            default=True,
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="watermark",
            label="水印",
            type=ParameterType.BOOLEAN,
            description="是否添加水印",
            required=False,
            default=False,
            group="generation",
            order=3,
        ),
        ModelParameter(
            name="seed",
            label="随机种子",
            type=ParameterType.INTEGER,
            description="固定种子可复现结果，留空为随机",
            required=False,
            constraint=ParameterConstraint(min_value=0, max_value=2147483647),
            group="generation",
            advanced=True,
            order=4,
        ),
    ],
)


# ============ 服务实现 ============

class Wan26T2IService(BaseModelService[List[str]]):
    """
    万相2.6 文生图服务
    """
    
    def __init__(self, model_info: ModelInfo = WAN26_T2I_MODEL_INFO):
        super().__init__(model_info)
        self._base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            self._base_url = base_url.rstrip('/') + "/services/aigc/text2image/image-synthesis"
    
    def _parse_size(self, size: str = None) -> tuple[int, int]:
        """解析尺寸参数"""
        if size:
            parts = size.split('*')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        return 1280, 1280  # 默认
    
    def _validate_size(self, width: int, height: int) -> bool:
        """验证尺寸是否合法"""
        total_pixels = width * height
        ratio = width / height if height > 0 else 0
        
        min_pixels = 1280 * 1280  # 1638400
        max_pixels = 1440 * 1440  # 2073600
        
        return (
            min_pixels <= total_pixels <= max_pixels and
            0.25 <= ratio <= 4.0
        )
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1280*1280",
        n: int = 4,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """
        生成图片
        
        Returns:
            图片URL列表
        """
        # 创建任务
        task_id = await self.create_task(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            n=n,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
        )
        
        # 等待完成
        max_wait = 300  # 5分钟
        elapsed = 0
        
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)
            if result.status == TaskStatus.SUCCEEDED:
                return result.result or []
            elif result.status == TaskStatus.FAILED:
                raise Exception(f"图片生成失败: {result.error_message}")
            
            await asyncio.sleep(3)
            elapsed += 3
        
        raise Exception("图片生成超时")
    
    async def create_task(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1280*1280",
        n: int = 4,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        **kwargs
    ) -> str:
        """创建图片生成任务"""
        w, h = self._parse_size(size)
        
        # 验证尺寸
        if not self._validate_size(w, h):
            raise ValueError(f"尺寸不合法: {w}x{h}，总像素需在 1638400-2073600 之间")
        
        # 构建请求体
        input_data = {
            "prompt": prompt,
        }
        
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt
        
        parameters = {
            "size": f"{w}*{h}",
            "n": n,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
        }
        
        if seed is not None:
            parameters["seed"] = seed
        
        payload = {
            "model": "wan2.6-t2i",
            "input": input_data,
            "parameters": parameters,
        }
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._base_url,
                json=payload,
                headers=headers,
            )
            
            if response.status_code != 200:
                raise Exception(f"创建任务失败: HTTP {response.status_code} - {response.text}")
            
            result = response.json()
            
            if "output" in result and "task_id" in result["output"]:
                return result["output"]["task_id"]
            
            raise Exception(f"创建任务失败: {result}")
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """获取任务状态"""
        url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        
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
            
            result = TaskResult(
                task_id=task_id,
                status=status,
            )
            
            if status == TaskStatus.SUCCEEDED:
                urls = []
                results = data.get("output", {}).get("results", [])
                for r in results:
                    if "url" in r:
                        urls.append(r["url"])
                result.result = urls
            elif status == TaskStatus.FAILED:
                result.error_message = data.get("output", {}).get("message", "未知错误")
            
            return result


# ============ 注册模型 ============

def register():
    registry.register(WAN26_T2I_MODEL_INFO, Wan26T2IService)


register()
