"""
大语言模型 (LLM) 注册

包含的模型：
- qwen3-max: Qwen3 Max（仅非思考模式）
- qwen-plus-latest: Qwen Plus Latest（支持思考模式）

API 文档：
- 通用: https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api
- JSON Mode: https://help.aliyun.com/zh/model-studio/json-mode
- 深度思考: https://help.aliyun.com/zh/model-studio/deep-thinking
- 联网搜索: https://help.aliyun.com/zh/model-studio/web-search
"""

from . import qwen

# 导出
from .qwen import (
    QWEN3_MAX_MODEL_INFO,
    QWEN_PLUS_MODEL_INFO,
    QwenLLMService,
)

__all__ = [
    "QWEN3_MAX_MODEL_INFO",
    "QWEN_PLUS_MODEL_INFO",
    "QwenLLMService",
]

