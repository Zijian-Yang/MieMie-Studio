"""
模型注册系统

这是一个模块化的模型管理系统，支持：
- 文本模型 (LLM)
- 图像生成模型 (Text-to-Image, Image-to-Image)
- 视频生成模型 (Image-to-Video, Text-to-Video)
- 音频模型 (Text-to-Audio, Audio-to-Text)

每个模型都是自描述的，包含：
- 基本信息（名称、描述、版本）
- 能力声明（支持的功能）
- 参数定义（包含类型、约束、默认值）
- 服务实现（API调用逻辑）

使用方法：
```python
from app.models_registry import registry, ModelType

# 获取所有视频模型
video_models = registry.list_models(ModelType.IMAGE_TO_VIDEO)

# 创建服务实例
service = registry.create_service("wan2.5-i2v-preview", api_key, base_url)

# 调用服务
result = await service.generate(img_url="...", prompt="...")
```

添加新模型：
1. 在对应目录下创建模型文件（如 video/my_model.py）
2. 定义 ModelInfo 和 Service 类
3. 调用 registry.register() 注册
4. 在该目录的 __init__.py 中导入模型文件
"""

from .base import (
    # 类型定义
    ParameterType,
    SelectOption,
    ParameterConstraint,
    ModelParameter,
    ModelType,
    ModelCapability,
    ModelInfo,
    TaskStatus,
    TaskResult,
    # 尺寸定义
    SizeOption,
    SizeConstraints,
    # 基类
    BaseModelService,
    # 注册中心
    ModelRegistry,
    registry,
)

# 导入并注册所有模型
# 注意：导入顺序不影响功能，但建议按类型分组

# LLM 模型
from .llm import qwen

# 图像模型（按版本排序，新版本在前）
from .image import wan26_t2i, wan26_image  # 万相2.6
from .image import wan25_t2i, wan25_i2i    # 万相2.5
from .image import qwen_image_edit          # 通义千问

# 视频模型（按版本排序，新版本在前）
from .video import wan26_t2v, wan26_i2v, wan26_r2v  # 万相2.6
from .video import wan25_i2v  # 万相2.5
from .video import wanx21_i2v  # 万相2.1


__all__ = [
    # 类型
    "ParameterType",
    "SelectOption", 
    "ParameterConstraint",
    "ModelParameter",
    "ModelType",
    "ModelCapability",
    "ModelInfo",
    "TaskStatus",
    "TaskResult",
    # 尺寸定义
    "SizeOption",
    "SizeConstraints",
    # 基类
    "BaseModelService",
    # 注册中心
    "ModelRegistry",
    "registry",
]

