"""
图像生成模型注册

包含的模型：
- wan2.6-t2i: 万相2.6 文生图（高分辨率）
- wan2.6-image: 万相2.6 图生图（最强，支持图文混合）
- wan2.5-t2i-preview: 万相2.5 文生图
- wan2.5-i2i-preview: 万相2.5 图生图（风格迁移）
- qwen-image-edit-plus: 通义千问图像编辑（单图编辑/多图融合）

API 文档：
- 万相2.6: https://help.aliyun.com/zh/model-studio/wan-image-generation-api-reference
- 文生图: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
- 图生图: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference
- 图像编辑: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api
"""

# 万相2.6 模型（推荐）
from . import wan26_t2i
from . import wan26_image

# 万相2.5 模型
from . import wan25_t2i
from . import wan25_i2i

# 通义千问图像编辑
from . import qwen_image_edit

# 导出
from .wan26_t2i import WAN26_T2I_MODEL_INFO, Wan26T2IService
from .wan26_image import WAN26_IMAGE_MODEL_INFO, Wan26ImageService
from .wan25_t2i import WAN25_T2I_MODEL_INFO, Wan25T2IService
from .wan25_i2i import WAN25_I2I_MODEL_INFO, Wan25I2IService
from .qwen_image_edit import QWEN_IMAGE_EDIT_PLUS_MODEL_INFO, QwenImageEditService

__all__ = [
    # 万相2.6
    "WAN26_T2I_MODEL_INFO",
    "Wan26T2IService",
    "WAN26_IMAGE_MODEL_INFO",
    "Wan26ImageService",
    # 万相2.5
    "WAN25_T2I_MODEL_INFO",
    "Wan25T2IService",
    "WAN25_I2I_MODEL_INFO",
    "Wan25I2IService",
    # 通义千问
    "QWEN_IMAGE_EDIT_PLUS_MODEL_INFO",
    "QwenImageEditService",
]

