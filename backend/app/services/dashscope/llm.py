"""
阿里云 DashScope LLM 服务封装
支持 Qwen 系列模型的调用，包括流式输出
"""

from typing import AsyncGenerator, Optional
import dashscope
from dashscope import Generation

from app.config import get_config, LLM_MODELS


class LLMService:
    """LLM 服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.llm_config = config.llm
        dashscope.base_http_api_url = config.base_url
    
    def _get_model_info(self, model: str) -> dict:
        """获取模型信息"""
        return LLM_MODELS.get(model, {})
    
    async def chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        result_format: Optional[str] = None,
        enable_search: Optional[bool] = None
    ) -> str:
        """
        非流式对话
        """
        model = model or self.llm_config.model
        model_info = self._get_model_info(model)
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        params = {
            'api_key': self.api_key,
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens or self.llm_config.max_tokens,
            'top_p': top_p if top_p is not None else self.llm_config.top_p,
            'temperature': temperature if temperature is not None else self.llm_config.temperature,
        }
        
        # 深度思考（仅支持的模型）
        # 注意：思考模式下不支持 JSON Mode
        thinking_value = enable_thinking if enable_thinking is not None else self.llm_config.enable_thinking
        use_thinking = thinking_value and model_info.get('supports_thinking')
        
        if use_thinking:
            params['enable_thinking'] = True
            budget = thinking_budget or self.llm_config.thinking_budget
            params['thinking_budget'] = budget
        
        # 设置返回格式（思考模式下不支持 JSON Mode）
        # 参考: https://help.aliyun.com/zh/model-studio/json-mode
        format_value = result_format or self.llm_config.result_format
        if format_value == 'json_object' and not use_thinking and model_info.get('supports_json_mode'):
            params['result_format'] = 'message'
            params['response_format'] = {'type': 'json_object'}
        else:
            params['result_format'] = 'message'
        
        # 联网搜索
        search_value = enable_search if enable_search is not None else self.llm_config.enable_search
        if search_value and model_info.get('supports_search'):
            params['enable_search'] = True
        
        response = Generation.call(**params)
        
        if response.status_code != 200:
            raise Exception(f"LLM 调用失败: {response.code} - {response.message}")
        
        return response.output.choices[0].message.content
    
    async def stream_chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        enable_search: Optional[bool] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式对话
        """
        model = model or self.llm_config.model
        model_info = self._get_model_info(model)
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        params = {
            'api_key': self.api_key,
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens or self.llm_config.max_tokens,
            'top_p': top_p if top_p is not None else self.llm_config.top_p,
            'temperature': temperature if temperature is not None else self.llm_config.temperature,
            'result_format': 'message',
            'stream': True,
            'incremental_output': True
        }
        
        # 联网搜索
        search_value = enable_search if enable_search is not None else self.llm_config.enable_search
        if search_value and model_info.get('supports_search'):
            params['enable_search'] = True
        
        # 深度思考
        thinking_value = enable_thinking if enable_thinking is not None else self.llm_config.enable_thinking
        if thinking_value and model_info.get('supports_thinking'):
            params['enable_thinking'] = True
            budget = thinking_budget or self.llm_config.thinking_budget
            params['thinking_budget'] = budget
        
        responses = Generation.call(**params)
        
        for response in responses:
            if response.status_code != 200:
                raise Exception(f"LLM 调用失败: {response.code} - {response.message}")
            
            if response.output.choices:
                content = response.output.choices[0].message.content
                if content:
                    yield content
    
    async def extract_json(
        self,
        prompt: str,
        model: Optional[str] = None
    ) -> str:
        """
        提取 JSON 格式的回复
        注意：JSON Mode 不支持思考模式，此方法强制关闭思考模式
        """
        system_prompt = "你是一个专业的助手。请严格按照要求输出 JSON 格式的结果，不要包含任何其他文字说明。"
        
        result = await self.chat(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            result_format='json_object',
            enable_thinking=False  # JSON Mode 不支持思考模式
        )
        
        # 尝试提取 JSON 部分
        result = result.strip()
        
        # 如果被代码块包裹，提取内容
        if result.startswith("```json"):
            result = result[7:]
        elif result.startswith("```"):
            result = result[3:]
        
        if result.endswith("```"):
            result = result[:-3]
        
        return result.strip()
