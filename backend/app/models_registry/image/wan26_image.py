"""
万相2.6 图生图模型 (wan2.6-image)

API 文档: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference

模型特点：
- 最强模型，支持参考图生图、图文混合、纯文生图
- HTTP异步调用
- 支持 0-3 张参考图
- 支持图文混合输出模式 (enable_interleave)
- 总像素范围 [768*768, 1280*1280]
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

WAN26_IMAGE_COMMON_SIZES = [
    SizeOption(width=1280, height=1280, label="1:1 方形 (默认)", aspect_ratio="1:1"),
    SizeOption(width=1024, height=1024, label="1:1 方形 (中)", aspect_ratio="1:1"),
    SizeOption(width=896, height=896, label="1:1 方形 (小)", aspect_ratio="1:1"),
    SizeOption(width=1280, height=720, label="16:9 横屏", aspect_ratio="16:9"),
    SizeOption(width=720, height=1280, label="9:16 竖屏", aspect_ratio="9:16"),
    SizeOption(width=1152, height=896, label="4:3 横屏", aspect_ratio="4:3"),
    SizeOption(width=896, height=1152, label="3:4 竖屏", aspect_ratio="3:4"),
    SizeOption(width=1200, height=800, label="3:2 横屏", aspect_ratio="3:2"),
    SizeOption(width=800, height=1200, label="2:3 竖屏", aspect_ratio="2:3"),
]

WAN26_IMAGE_SIZE_CONSTRAINTS = SizeConstraints(
    min_pixels=768 * 768,  # 589,824
    max_pixels=1280 * 1280,  # 1,638,400
    min_ratio=0.25,  # 1:4
    max_ratio=4.0,  # 4:1
)

WAN26_IMAGE_MODEL_INFO = ModelInfo(
    id="wan2.6-image",
    name="万相2.6 图生图",
    type=ModelType.IMAGE_TO_IMAGE,
    provider="dashscope",
    description="最强模型，支持参考图生图、图文混合、纯文生图，HTTP异步调用",
    version="2.6",
    
    api_model_name="wan2.6-image",
    doc_url="https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference",
    
    capabilities=ModelCapability(
        supports_streaming=False,
        supports_batch=True,
        supports_async=True,
        max_concurrent=5,
        supports_negative_prompt=True,
        supports_seed=True,
        supports_prompt_extend=True,
        supports_reference_images=True,
        max_reference_images=3,
        supports_interleave=True,  # 图文混合模式
    ),
    
    size_constraints=WAN26_IMAGE_SIZE_CONSTRAINTS,
    common_sizes=WAN26_IMAGE_COMMON_SIZES,
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
        
        # === 参考图参数 ===
        ModelParameter(
            name="images",
            label="参考图片",
            type=ParameterType.IMAGE_URLS,
            description="参考图片URL列表（0-3张，图文混合模式下最多1张）",
            required=False,
            constraint=ParameterConstraint(
                min_length=0,
                max_length=3,
            ),
            group="reference",
            order=1,
        ),
        
        # === 尺寸参数 ===
        ModelParameter(
            name="size",
            label="图片尺寸",
            type=ParameterType.SELECT,
            description="预设尺寸，总像素需在 589824-1638400 之间",
            required=False,
            default="1280*1280",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="1280*1280", label="1280×1280 (1:1 方形)"),
                    SelectOption(value="1024*1024", label="1024×1024 (1:1 方形中)"),
                    SelectOption(value="896*896", label="896×896 (1:1 方形小)"),
                    SelectOption(value="1280*720", label="1280×720 (16:9 横屏)"),
                    SelectOption(value="720*1280", label="720×1280 (9:16 竖屏)"),
                    SelectOption(value="1152*896", label="1152×896 (4:3 横屏)"),
                    SelectOption(value="896*1152", label="896×1152 (3:4 竖屏)"),
                    SelectOption(value="1200*800", label="1200×800 (3:2 横屏)"),
                    SelectOption(value="800*1200", label="800×1200 (2:3 竖屏)"),
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
            description="一次生成的图片数量（图文混合模式下固定为1）",
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
            description="自动优化和扩展提示词（图文混合模式下不生效）",
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
        
        # === 高级参数：图文混合模式 ===
        ModelParameter(
            name="enable_interleave",
            label="图文混合模式",
            type=ParameterType.BOOLEAN,
            description="启用后生成图文并茂内容，参考图最多1张，生成数量固定为1",
            required=False,
            default=False,
            group="advanced",
            advanced=True,
            order=1,
        ),
        ModelParameter(
            name="max_images",
            label="最大生成图数",
            type=ParameterType.INTEGER,
            description="图文混合模式下最大生成图片数（1-5）",
            required=False,
            default=5,
            constraint=ParameterConstraint(
                min_value=1,
                max_value=5,
                depends_on="enable_interleave",
                depends_value=True,
            ),
            group="advanced",
            advanced=True,
            order=2,
        ),
    ],
)


# ============ 服务实现 ============

class Wan26ImageService(BaseModelService[List[str]]):
    """
    万相2.6 图生图服务
    
    支持三种模式：
    1. 纯文生图：不传参考图
    2. 参考图生图：传入1-3张参考图
    3. 图文混合：enable_interleave=True
    """
    
    def __init__(self, model_info: ModelInfo = WAN26_IMAGE_MODEL_INFO):
        super().__init__(model_info)
        self._base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/image-synthesis"
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            # 替换域名部分
            self._base_url = base_url.rstrip('/') + "/services/aigc/image2image/image-synthesis"
    
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
        
        min_pixels = 768 * 768  # 589824
        max_pixels = 1280 * 1280  # 1638400
        
        return (
            min_pixels <= total_pixels <= max_pixels and
            0.25 <= ratio <= 4.0
        )
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        images: List[str] = None,
        size: str = "1280*1280",
        n: int = 4,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        enable_interleave: bool = False,
        max_images: int = 5,
        **kwargs
    ) -> List[str]:
        """
        生成图片
        
        Args:
            prompt: 提示词
            negative_prompt: 负面提示词
            images: 参考图片URL列表
            size: 尺寸 "width*height"
            n: 生成数量
            prompt_extend: 智能改写
            watermark: 水印
            seed: 随机种子
            enable_interleave: 图文混合模式
            max_images: 图文混合模式下最大图片数
            
        Returns:
            图片URL列表
        """
        # 创建任务
        task_id = await self.create_task(
            prompt=prompt,
            negative_prompt=negative_prompt,
            images=images,
            size=size,
            n=n,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            enable_interleave=enable_interleave,
            max_images=max_images,
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
        images: List[str] = None,
        size: str = "1280*1280",
        n: int = 4,
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        enable_interleave: bool = False,
        max_images: int = 5,
        **kwargs
    ) -> str:
        """创建图片生成任务"""
        w, h = self._parse_size(size)
        
        # 验证尺寸
        if not self._validate_size(w, h):
            raise ValueError(f"尺寸不合法: {w}x{h}，总像素需在 589824-1638400 之间")
        
        # 构建请求体
        input_data = {
            "prompt": prompt,
        }
        
        if images:
            input_data["images"] = images
        
        parameters = {
            "size": f"{w}*{h}",
            "watermark": watermark,
        }
        
        if negative_prompt:
            parameters["negative_prompt"] = negative_prompt
        
        if enable_interleave:
            # 图文混合模式
            parameters["enable_interleave"] = True
            parameters["max_images"] = max_images
            parameters["n"] = 1  # 固定为1
        else:
            # 普通模式
            parameters["n"] = n
            parameters["prompt_extend"] = prompt_extend
        
        if seed is not None:
            parameters["seed"] = seed
        
        payload = {
            "model": "wan2.6-image",
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
                # 提取所有图片URL
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
    registry.register(WAN26_IMAGE_MODEL_INFO, Wan26ImageService)


register()
