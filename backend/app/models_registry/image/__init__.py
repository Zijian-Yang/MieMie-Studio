"""
图像生成模型注册

包含的模型：
- wan2.5-t2i-preview: 万相2.5 文生图
- wan2.5-i2i-preview: 万相2.5 图生图（风格迁移）
- qwen-image-edit-plus: 通义千问图像编辑（单图编辑/多图融合）

API 文档：
- 文生图: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
- 图生图: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference
- 图像编辑: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api
"""

from . import wan25_t2i
from . import wan25_i2i
from . import qwen_image_edit

# 导出
from .wan25_t2i import WAN25_T2I_MODEL_INFO, Wan25T2IService
from .wan25_i2i import WAN25_I2I_MODEL_INFO, Wan25I2IService
from .qwen_image_edit import QWEN_IMAGE_EDIT_PLUS_MODEL_INFO, QwenImageEditService

__all__ = [
    "WAN25_T2I_MODEL_INFO",
    "Wan25T2IService",
    "WAN25_I2I_MODEL_INFO",
    "Wan25I2IService",
    "QWEN_IMAGE_EDIT_PLUS_MODEL_INFO",
    "QwenImageEditService",
]

