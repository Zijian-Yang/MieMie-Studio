"""
视频生成模型注册

包含的模型：
- wan2.5-i2v-preview: 万相2.5 图生视频（支持音频）
- wanx2.1-i2v-turbo: 万相2.1 图生视频 Turbo（快速生成）

API 文档：
- https://www.alibabacloud.com/help/zh/model-studio/image-to-video-api-reference
"""

from . import wan25_i2v
from . import wanx21_i2v

# 导出模型信息和服务类
from .wan25_i2v import WAN25_I2V_MODEL_INFO, Wan25I2VService
from .wanx21_i2v import WANX21_I2V_MODEL_INFO, Wanx21I2VService

__all__ = [
    "WAN25_I2V_MODEL_INFO",
    "Wan25I2VService",
    "WANX21_I2V_MODEL_INFO",
    "Wanx21I2VService",
]

