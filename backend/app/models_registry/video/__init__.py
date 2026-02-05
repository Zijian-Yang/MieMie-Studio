"""
视频生成模型注册

包含的模型：
- wan2.6-t2v: 万相2.6 文生视频（最新，支持多镜头叙事）
- wan2.6-i2v-flash: 万相2.6 图生视频 极速版
- wan2.6-i2v: 万相2.6 图生视频 标准版
- wan2.6-r2v: 万相2.6 参考生视频（角色一致性）
- wan2.5-i2v-preview: 万相2.5 图生视频
- wanx2.1-i2v-turbo: 万相2.1 图生视频 Turbo

API 文档：
- 文生视频: https://help.aliyun.com/zh/model-studio/text-to-video-api
- 图生视频: https://help.aliyun.com/zh/model-studio/image-to-video-api-reference
- 参考生视频: https://help.aliyun.com/zh/model-studio/wan-video-to-video-api-reference
"""

# 万相2.6 视频模型（推荐）
from . import wan26_t2v
from . import wan26_i2v
from . import wan26_r2v

# 万相2.5 视频模型
from . import wan25_i2v

# 万相2.1 视频模型
from . import wanx21_i2v

# 导出模型信息和服务类
from .wan26_t2v import WAN26_T2V_MODEL_INFO, Wan26T2VService
from .wan26_i2v import WAN26_I2V_FLASH_MODEL_INFO, WAN26_I2V_MODEL_INFO, Wan26I2VService
from .wan26_r2v import WAN26_R2V_MODEL_INFO, Wan26R2VService
from .wan25_i2v import WAN25_I2V_MODEL_INFO, Wan25I2VService
from .wanx21_i2v import WANX21_I2V_MODEL_INFO, Wanx21I2VService

__all__ = [
    # 万相2.6
    "WAN26_T2V_MODEL_INFO",
    "Wan26T2VService",
    "WAN26_I2V_FLASH_MODEL_INFO",
    "WAN26_I2V_MODEL_INFO",
    "Wan26I2VService",
    "WAN26_R2V_MODEL_INFO",
    "Wan26R2VService",
    # 万相2.5
    "WAN25_I2V_MODEL_INFO",
    "Wan25I2VService",
    # 万相2.1
    "WANX21_I2V_MODEL_INFO",
    "Wanx21I2VService",
]

