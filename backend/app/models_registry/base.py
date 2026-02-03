"""
模型注册系统 - 基础定义

该模块定义了模型注册系统的核心概念：
1. ModelParameter - 模型参数定义
2. ModelCapability - 模型能力声明
3. ModelInfo - 模型元信息
4. BaseModelService - 模型服务基类
5. ModelRegistry - 模型注册中心

添加新模型时，只需：
1. 在 models_registry/ 下创建模型定义文件
2. 继承 BaseModelService 实现服务
3. 调用 registry.register() 注册模型
"""

from abc import ABC, abstractmethod
from typing import (
    Any, Dict, List, Optional, Union, Callable, 
    TypeVar, Generic, AsyncGenerator, Literal
)
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio


# ============ 参数类型定义 ============

class ParameterType(str, Enum):
    """参数类型"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    SELECT = "select"  # 下拉选择
    MULTI_SELECT = "multi_select"  # 多选
    TEXT = "text"  # 长文本
    IMAGE_URL = "image_url"  # 图片URL
    IMAGE_URLS = "image_urls"  # 多图片URL
    AUDIO_URL = "audio_url"  # 音频URL
    VIDEO_URL = "video_url"  # 视频URL
    FILE = "file"  # 文件上传


class SelectOption(BaseModel):
    """下拉选项"""
    value: Any
    label: str
    description: str = ""


class ParameterConstraint(BaseModel):
    """参数约束"""
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # 正则表达式
    options: Optional[List[SelectOption]] = None  # SELECT 类型的选项
    depends_on: Optional[str] = None  # 依赖其他参数
    depends_value: Optional[Any] = None  # 依赖参数的值
    custom_validator: Optional[str] = None  # 自定义验证函数名


class ModelParameter(BaseModel):
    """
    模型参数定义
    
    用于描述模型支持的参数，包括：
    - 参数类型和约束
    - 默认值
    - 是否必填
    - 参数分组（用于前端展示）
    - 高级选项标记
    """
    name: str  # 参数名（API中使用）
    label: str  # 显示名称
    type: ParameterType
    description: str = ""
    required: bool = False
    default: Optional[Any] = None
    constraint: Optional[ParameterConstraint] = None
    group: str = "basic"  # 参数分组：basic, advanced, audio, etc.
    advanced: bool = False  # 是否为高级参数
    order: int = 0  # 显示顺序
    
    def validate_value(self, value: Any) -> tuple[bool, str]:
        """验证参数值"""
        if value is None:
            if self.required:
                return False, f"参数 {self.label} 是必填的"
            return True, ""
        
        constraint = self.constraint
        if not constraint:
            return True, ""
        
        # 数值范围验证
        if self.type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            if constraint.min_value is not None and value < constraint.min_value:
                return False, f"{self.label} 不能小于 {constraint.min_value}"
            if constraint.max_value is not None and value > constraint.max_value:
                return False, f"{self.label} 不能大于 {constraint.max_value}"
        
        # 字符串长度验证
        if self.type in [ParameterType.STRING, ParameterType.TEXT]:
            if constraint.min_length is not None and len(str(value)) < constraint.min_length:
                return False, f"{self.label} 长度不能少于 {constraint.min_length}"
            if constraint.max_length is not None and len(str(value)) > constraint.max_length:
                return False, f"{self.label} 长度不能超过 {constraint.max_length}"
        
        # 选项验证
        if self.type == ParameterType.SELECT and constraint.options:
            valid_values = [opt.value for opt in constraint.options]
            if value not in valid_values:
                return False, f"{self.label} 的值必须是: {valid_values}"
        
        return True, ""


# ============ 尺寸定义 ============

class SizeOption(BaseModel):
    """
    尺寸选项
    
    用于定义模型支持的预设尺寸
    """
    width: int
    height: int
    label: str
    aspect_ratio: Optional[str] = None
    
    @property
    def total_pixels(self) -> int:
        """总像素数"""
        return self.width * self.height
    
    @property
    def size_string(self) -> str:
        """尺寸字符串 (width*height)"""
        return f"{self.width}*{self.height}"


class SizeConstraints(BaseModel):
    """
    尺寸约束
    
    定义模型对尺寸的限制
    """
    min_pixels: Optional[int] = None  # 最小总像素
    max_pixels: Optional[int] = None  # 最大总像素
    min_ratio: Optional[float] = None  # 最小宽高比 (width/height)
    max_ratio: Optional[float] = None  # 最大宽高比
    min_width: Optional[int] = None
    max_width: Optional[int] = None
    min_height: Optional[int] = None
    max_height: Optional[int] = None
    
    def validate(self, width: int, height: int) -> tuple[bool, str]:
        """验证尺寸是否符合约束"""
        total_pixels = width * height
        ratio = width / height if height > 0 else 0
        
        if self.min_pixels and total_pixels < self.min_pixels:
            return False, f"总像素 {total_pixels} 小于最小值 {self.min_pixels}"
        if self.max_pixels and total_pixels > self.max_pixels:
            return False, f"总像素 {total_pixels} 大于最大值 {self.max_pixels}"
        if self.min_ratio and ratio < self.min_ratio:
            return False, f"宽高比 {ratio:.2f} 小于最小值 {self.min_ratio}"
        if self.max_ratio and ratio > self.max_ratio:
            return False, f"宽高比 {ratio:.2f} 大于最大值 {self.max_ratio}"
        if self.min_width and width < self.min_width:
            return False, f"宽度 {width} 小于最小值 {self.min_width}"
        if self.max_width and width > self.max_width:
            return False, f"宽度 {width} 大于最大值 {self.max_width}"
        if self.min_height and height < self.min_height:
            return False, f"高度 {height} 小于最小值 {self.min_height}"
        if self.max_height and height > self.max_height:
            return False, f"高度 {height} 大于最大值 {self.max_height}"
        
        return True, ""


# ============ 模型能力声明 ============

class ModelType(str, Enum):
    """模型类型"""
    LLM = "llm"  # 大语言模型
    TEXT_TO_IMAGE = "text_to_image"  # 文生图
    IMAGE_TO_IMAGE = "image_to_image"  # 图生图
    IMAGE_TO_VIDEO = "image_to_video"  # 图生视频
    TEXT_TO_VIDEO = "text_to_video"  # 文生视频
    REFERENCE_TO_VIDEO = "reference_to_video"  # 参考生视频
    KEYFRAME_TO_VIDEO = "keyframe_to_video"  # 关键帧生视频
    TEXT_TO_AUDIO = "text_to_audio"  # 文生音频
    AUDIO_TO_TEXT = "audio_to_text"  # 语音识别


class ModelCapability(BaseModel):
    """
    模型能力声明
    
    描述模型支持的功能和限制
    """
    supports_streaming: bool = False  # 支持流式输出
    supports_batch: bool = False  # 支持批量处理
    supports_async: bool = True  # 支持异步调用
    max_concurrent: int = 5  # 最大并发数
    rate_limit: Optional[int] = None  # 每分钟请求限制
    
    # LLM 特有能力
    supports_thinking: bool = False  # 支持深度思考
    supports_search: bool = False  # 支持联网搜索
    supports_json_mode: bool = False  # 支持 JSON 输出
    supports_tools: bool = False  # 支持工具调用
    max_context_length: Optional[int] = None  # 最大上下文长度
    
    # 图像/视频特有能力
    supports_negative_prompt: bool = False  # 支持负面提示词
    supports_seed: bool = False  # 支持种子
    supports_prompt_extend: bool = False  # 支持智能改写
    supports_watermark: bool = False  # 支持水印控制
    supports_audio: bool = False  # 支持音频（视频模型）
    
    # 图像特有能力
    supports_reference_images: bool = False  # 支持参考图
    max_reference_images: int = 0  # 最大参考图数量
    supports_interleave: bool = False  # 支持图文混合模式


class ModelInfo(BaseModel):
    """
    模型元信息
    
    完整描述一个模型的所有信息
    """
    # 基本信息
    id: str  # 模型ID（唯一标识）
    name: str  # 显示名称
    type: ModelType  # 模型类型
    provider: str = "dashscope"  # 提供商
    description: str = ""
    version: str = "1.0"
    
    # 能力声明
    capabilities: ModelCapability = Field(default_factory=ModelCapability)
    
    # 参数定义
    parameters: List[ModelParameter] = []
    
    # 尺寸约束（图像/视频模型）
    size_constraints: Optional[SizeConstraints] = None
    common_sizes: List[SizeOption] = []
    
    # API 信息
    api_model_name: str = ""  # API 中使用的模型名
    api_endpoint: str = ""  # API 端点
    
    # 文档链接
    doc_url: str = ""
    
    # 状态
    enabled: bool = True
    deprecated: bool = False
    deprecated_message: str = ""
    recommended: bool = False  # 推荐模型标记
    
    def get_parameter(self, name: str) -> Optional[ModelParameter]:
        """获取参数定义"""
        for param in self.parameters:
            if param.name == name:
                return param
        return None
    
    def get_parameters_by_group(self, group: str) -> List[ModelParameter]:
        """按分组获取参数"""
        return [p for p in self.parameters if p.group == group]
    
    def get_default_values(self) -> Dict[str, Any]:
        """获取所有参数的默认值"""
        return {p.name: p.default for p in self.parameters if p.default is not None}
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证参数"""
        errors = []
        for param in self.parameters:
            value = params.get(param.name)
            valid, error = param.validate_value(value)
            if not valid:
                errors.append(error)
        return len(errors) == 0, errors
    
    def validate_size(self, width: int, height: int) -> tuple[bool, str]:
        """验证尺寸是否符合约束"""
        if self.size_constraints:
            return self.size_constraints.validate(width, height)
        return True, ""
    
    def get_common_sizes_for_frontend(self) -> List[Dict[str, Any]]:
        """获取前端使用的尺寸选项"""
        return [
            {
                "width": s.width,
                "height": s.height,
                "label": s.label,
                "aspect_ratio": s.aspect_ratio,
                "value": s.size_string,
            }
            for s in self.common_sizes
        ]


# ============ 任务状态 ============

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskResult(BaseModel):
    """任务结果"""
    task_id: str
    status: TaskStatus
    progress: float = 0.0
    result: Optional[Any] = None  # 生成结果（URL、文本等）
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}


# ============ 服务基类 ============

T = TypeVar('T')


class BaseModelService(ABC, Generic[T]):
    """
    模型服务基类
    
    所有模型服务必须继承此类并实现相关方法
    """
    
    def __init__(self, model_info: ModelInfo):
        self.model_info = model_info
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None
    
    def configure(self, api_key: str, base_url: str = ""):
        """配置 API 密钥和基础 URL"""
        self._api_key = api_key
        self._base_url = base_url
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证参数"""
        return self.model_info.validate_params(params)
    
    @abstractmethod
    async def generate(self, **params) -> T:
        """
        同步生成（对于支持同步的模型）
        或提交任务并等待完成
        """
        pass
    
    async def create_task(self, **params) -> str:
        """
        创建异步任务，返回任务ID
        默认实现：调用 generate 并包装
        """
        raise NotImplementedError("此模型不支持异步任务")
    
    async def get_task_status(self, task_id: str) -> TaskResult:
        """获取任务状态"""
        raise NotImplementedError("此模型不支持异步任务")
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        raise NotImplementedError("此模型不支持取消任务")
    
    async def stream_generate(self, **params) -> AsyncGenerator[str, None]:
        """流式生成（仅 LLM）"""
        raise NotImplementedError("此模型不支持流式输出")


# ============ 模型注册中心 ============

class ModelRegistry:
    """
    模型注册中心
    
    负责管理所有已注册的模型
    """
    
    _instance: Optional['ModelRegistry'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models: Dict[str, ModelInfo] = {}
            cls._instance._services: Dict[str, type[BaseModelService]] = {}
        return cls._instance
    
    def register(
        self, 
        model_info: ModelInfo, 
        service_class: type[BaseModelService]
    ):
        """注册模型"""
        self._models[model_info.id] = model_info
        self._services[model_info.id] = service_class
    
    def unregister(self, model_id: str):
        """注销模型"""
        self._models.pop(model_id, None)
        self._services.pop(model_id, None)
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self._models.get(model_id)
    
    def get_service_class(self, model_id: str) -> Optional[type[BaseModelService]]:
        """获取服务类"""
        return self._services.get(model_id)
    
    def create_service(self, model_id: str, api_key: str, base_url: str = "") -> Optional[BaseModelService]:
        """创建服务实例"""
        model_info = self.get_model_info(model_id)
        service_class = self.get_service_class(model_id)
        
        if not model_info or not service_class:
            return None
        
        service = service_class(model_info)
        service.configure(api_key, base_url)
        return service
    
    def list_models(self, model_type: Optional[ModelType] = None) -> List[ModelInfo]:
        """列出所有模型"""
        models = list(self._models.values())
        if model_type:
            models = [m for m in models if m.type == model_type]
        return [m for m in models if m.enabled]
    
    def list_models_by_type(self) -> Dict[ModelType, List[ModelInfo]]:
        """按类型列出模型"""
        result: Dict[ModelType, List[ModelInfo]] = {}
        for model in self._models.values():
            if not model.enabled:
                continue
            if model.type not in result:
                result[model.type] = []
            result[model.type].append(model)
        return result
    
    def get_all_model_info_for_frontend(self) -> Dict[str, Any]:
        """
        获取所有模型信息（用于前端）
        返回格式化的模型配置，前端可直接使用
        """
        result = {}
        for model_id, model_info in self._models.items():
            if not model_info.enabled:
                continue
            result[model_id] = {
                "id": model_info.id,
                "name": model_info.name,
                "type": model_info.type.value,
                "description": model_info.description,
                "capabilities": model_info.capabilities.model_dump(),
                "parameters": [p.model_dump() for p in model_info.parameters],
                "default_values": model_info.get_default_values(),
                "deprecated": model_info.deprecated,
                "deprecated_message": model_info.deprecated_message,
                "recommended": model_info.recommended,
                "size_constraints": model_info.size_constraints.model_dump() if model_info.size_constraints else None,
                "common_sizes": model_info.get_common_sizes_for_frontend(),
            }
        return result
    
    def get_image_models(self) -> List[ModelInfo]:
        """获取所有图像生成模型（文生图 + 图生图）"""
        return [
            m for m in self._models.values()
            if m.enabled and m.type in [ModelType.TEXT_TO_IMAGE, ModelType.IMAGE_TO_IMAGE]
        ]
    
    def get_video_models(self) -> List[ModelInfo]:
        """获取所有视频生成模型"""
        return [
            m for m in self._models.values()
            if m.enabled and m.type in [
                ModelType.TEXT_TO_VIDEO, 
                ModelType.IMAGE_TO_VIDEO,
                ModelType.REFERENCE_TO_VIDEO,
                ModelType.KEYFRAME_TO_VIDEO,
            ]
        ]


# 全局注册中心实例
registry = ModelRegistry()

