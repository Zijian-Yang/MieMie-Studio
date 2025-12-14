"""
Qwen 系列大语言模型

API 文档：
- 通用调用: https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api
- JSON Mode: https://help.aliyun.com/zh/model-studio/json-mode
- 深度思考: https://help.aliyun.com/zh/model-studio/deep-thinking
- 联网搜索: https://help.aliyun.com/zh/model-studio/web-search

模型特点：
- qwen3-max: 最大输出 65536 tokens，仅非思考模式，支持 JSON Mode 和联网搜索
- qwen-plus-latest: 最大输出 32768 tokens，支持思考/非思考模式，支持 JSON Mode 和联网搜索
"""

from typing import Optional, AsyncGenerator
import dashscope
from dashscope import Generation

from ..base import (
    ModelInfo, ModelType, ModelCapability, ModelParameter,
    ParameterType, ParameterConstraint, SelectOption,
    BaseModelService, TaskResult, TaskStatus, registry
)


# ============ Qwen3-Max 模型定义 ============

QWEN3_MAX_MODEL_INFO = ModelInfo(
    id="qwen3-max",
    name="Qwen3-Max",
    type=ModelType.LLM,
    provider="dashscope",
    description="最强大的 Qwen3 模型，最大输出 65536 tokens，仅支持非思考模式",
    version="3.0",
    
    api_model_name="qwen3-max",
    doc_url="https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api",
    
    capabilities=ModelCapability(
        supports_streaming=True,
        supports_async=True,
        supports_thinking=False,  # 不支持思考模式
        supports_search=True,
        supports_json_mode=True,
        supports_tools=True,
        max_context_length=32768,
    ),
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="用户消息",
            type=ParameterType.TEXT,
            description="用户输入的消息内容",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="system_prompt",
            label="系统提示词",
            type=ParameterType.TEXT,
            description="设置 AI 的角色和行为规则",
            required=False,
            group="basic",
            order=2,
        ),
        
        # === 生成参数 ===
        ModelParameter(
            name="max_tokens",
            label="最大输出长度",
            type=ParameterType.INTEGER,
            description="生成文本的最大 token 数量",
            required=False,
            default=8192,
            constraint=ParameterConstraint(min_value=1, max_value=65536),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="temperature",
            label="温度",
            type=ParameterType.FLOAT,
            description="控制输出的随机性，值越高越随机",
            required=False,
            default=0.7,
            constraint=ParameterConstraint(min_value=0.0, max_value=2.0),
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="top_p",
            label="Top P",
            type=ParameterType.FLOAT,
            description="核采样参数",
            required=False,
            default=0.8,
            constraint=ParameterConstraint(min_value=0.0, max_value=1.0),
            group="generation",
            order=3,
        ),
        
        # === 高级参数 ===
        ModelParameter(
            name="result_format",
            label="输出格式",
            type=ParameterType.SELECT,
            description="返回格式",
            required=False,
            default="message",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="message", label="普通文本"),
                    SelectOption(value="json_object", label="JSON 格式"),
                ]
            ),
            group="advanced",
            advanced=True,
            order=1,
        ),
        ModelParameter(
            name="enable_search",
            label="联网搜索",
            type=ParameterType.BOOLEAN,
            description="启用联网搜索获取最新信息",
            required=False,
            default=False,
            group="advanced",
            advanced=True,
            order=2,
        ),
    ],
)


# ============ Qwen-Plus-Latest 模型定义 ============

QWEN_PLUS_MODEL_INFO = ModelInfo(
    id="qwen-plus-latest",
    name="Qwen-Plus-Latest",
    type=ModelType.LLM,
    provider="dashscope",
    description="Qwen Plus 最新版，支持思考模式和非思考模式",
    version="latest",
    
    api_model_name="qwen-plus-latest",
    doc_url="https://help.aliyun.com/zh/model-studio/deep-thinking",
    
    capabilities=ModelCapability(
        supports_streaming=True,
        supports_async=True,
        supports_thinking=True,  # 支持思考模式
        supports_search=True,
        supports_json_mode=True,
        supports_tools=True,
        max_context_length=131072,
    ),
    
    parameters=[
        # === 基础参数 ===
        ModelParameter(
            name="prompt",
            label="用户消息",
            type=ParameterType.TEXT,
            description="用户输入的消息内容",
            required=True,
            group="basic",
            order=1,
        ),
        ModelParameter(
            name="system_prompt",
            label="系统提示词",
            type=ParameterType.TEXT,
            description="设置 AI 的角色和行为规则",
            required=False,
            group="basic",
            order=2,
        ),
        
        # === 生成参数 ===
        ModelParameter(
            name="max_tokens",
            label="最大输出长度",
            type=ParameterType.INTEGER,
            description="生成文本的最大 token 数量",
            required=False,
            default=8192,
            constraint=ParameterConstraint(min_value=1, max_value=32768),
            group="generation",
            order=1,
        ),
        ModelParameter(
            name="temperature",
            label="温度",
            type=ParameterType.FLOAT,
            description="控制输出的随机性，值越高越随机",
            required=False,
            default=0.7,
            constraint=ParameterConstraint(min_value=0.0, max_value=2.0),
            group="generation",
            order=2,
        ),
        ModelParameter(
            name="top_p",
            label="Top P",
            type=ParameterType.FLOAT,
            description="核采样参数",
            required=False,
            default=0.8,
            constraint=ParameterConstraint(min_value=0.0, max_value=1.0),
            group="generation",
            order=3,
        ),
        
        # === 思考模式参数 ===
        ModelParameter(
            name="enable_thinking",
            label="深度思考",
            type=ParameterType.BOOLEAN,
            description="启用深度思考模式（启用后不支持 JSON Mode）",
            required=False,
            default=False,
            group="thinking",
            order=1,
        ),
        ModelParameter(
            name="thinking_budget",
            label="思考预算",
            type=ParameterType.INTEGER,
            description="思考过程的最大 token 数",
            required=False,
            default=4096,
            constraint=ParameterConstraint(
                min_value=1,
                max_value=32768,
                depends_on="enable_thinking",
                depends_value=True,
            ),
            group="thinking",
            order=2,
        ),
        
        # === 高级参数 ===
        ModelParameter(
            name="result_format",
            label="输出格式",
            type=ParameterType.SELECT,
            description="返回格式（思考模式下不支持 JSON）",
            required=False,
            default="message",
            constraint=ParameterConstraint(
                options=[
                    SelectOption(value="message", label="普通文本"),
                    SelectOption(value="json_object", label="JSON 格式"),
                ],
                depends_on="enable_thinking",
                depends_value=False,
            ),
            group="advanced",
            advanced=True,
            order=1,
        ),
        ModelParameter(
            name="enable_search",
            label="联网搜索",
            type=ParameterType.BOOLEAN,
            description="启用联网搜索获取最新信息",
            required=False,
            default=False,
            group="advanced",
            advanced=True,
            order=2,
        ),
    ],
)


# ============ 服务实现 ============

class QwenLLMService(BaseModelService[str]):
    """
    Qwen 系列 LLM 服务
    
    支持 qwen3-max 和 qwen-plus-latest 两种模型
    """
    
    def __init__(self, model_info: ModelInfo):
        super().__init__(model_info)
    
    def configure(self, api_key: str, base_url: str = ""):
        super().configure(api_key, base_url)
        if base_url:
            dashscope.base_http_api_url = base_url
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.8,
        enable_thinking: bool = False,
        thinking_budget: int = 4096,
        result_format: str = "message",
        enable_search: bool = False,
        **kwargs
    ) -> str:
        """
        非流式对话
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'messages': messages,
            'max_tokens': max_tokens,
            'top_p': top_p,
            'temperature': temperature,
        }
        
        # 深度思考模式
        use_thinking = (
            enable_thinking and 
            self.model_info.capabilities.supports_thinking
        )
        
        if use_thinking:
            params['enable_thinking'] = True
            params['thinking_budget'] = thinking_budget
        
        # JSON Mode（思考模式下不支持）
        if (result_format == 'json_object' and 
            not use_thinking and 
            self.model_info.capabilities.supports_json_mode):
            params['result_format'] = 'message'
            params['response_format'] = {'type': 'json_object'}
        else:
            params['result_format'] = 'message'
        
        # 联网搜索
        if enable_search and self.model_info.capabilities.supports_search:
            params['enable_search'] = True
        
        # 调用 API
        response = Generation.call(**params)
        
        if response.status_code != 200:
            raise Exception(f"API 调用失败: {response.code} - {response.message}")
        
        return response.output.choices[0].message.content
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.8,
        enable_thinking: bool = False,
        thinking_budget: int = 4096,
        result_format: str = "message",
        enable_search: bool = False,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式对话
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        params = {
            'api_key': self._api_key,
            'model': self.model_info.api_model_name,
            'messages': messages,
            'max_tokens': max_tokens,
            'top_p': top_p,
            'temperature': temperature,
            'stream': True,
            'incremental_output': True,
        }
        
        # 深度思考模式
        use_thinking = (
            enable_thinking and 
            self.model_info.capabilities.supports_thinking
        )
        
        if use_thinking:
            params['enable_thinking'] = True
            params['thinking_budget'] = thinking_budget
        
        # JSON Mode（思考模式下不支持）
        if (result_format == 'json_object' and 
            not use_thinking and 
            self.model_info.capabilities.supports_json_mode):
            params['result_format'] = 'message'
            params['response_format'] = {'type': 'json_object'}
        else:
            params['result_format'] = 'message'
        
        # 联网搜索
        if enable_search and self.model_info.capabilities.supports_search:
            params['enable_search'] = True
        
        # 流式调用
        responses = Generation.call(**params)
        
        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content
            else:
                raise Exception(f"API 调用失败: {response.code} - {response.message}")


# ============ 注册模型 ============

def register():
    """注册所有 Qwen 模型"""
    registry.register(QWEN3_MAX_MODEL_INFO, QwenLLMService)
    registry.register(QWEN_PLUS_MODEL_INFO, QwenLLMService)


# 自动注册
register()

