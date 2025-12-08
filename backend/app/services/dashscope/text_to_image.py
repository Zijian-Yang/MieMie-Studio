"""
阿里云 DashScope 文生图服务封装
参考: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
"""

from typing import List, Optional
from http import HTTPStatus
import dashscope
from dashscope import ImageSynthesis

from app.config import get_config, IMAGE_MODELS


class TextToImageService:
    """文生图服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.image_config = config.image
        dashscope.base_http_api_url = config.base_url
    
    def validate_size(self, width: int, height: int, model: str = None) -> bool:
        """验证图片尺寸是否在允许范围内"""
        model_name = model or self.image_config.model
        model_info = IMAGE_MODELS.get(model_name, {})
        
        min_pixels = model_info.get("min_pixels", 768 * 768)
        max_pixels = model_info.get("max_pixels", 1440 * 1440)
        min_ratio = model_info.get("min_ratio", 0.25)
        max_ratio = model_info.get("max_ratio", 4.0)
        
        total_pixels = width * height
        ratio = width / height if height > 0 else 0
        
        return (min_pixels <= total_pixels <= max_pixels and 
                min_ratio <= ratio <= max_ratio)
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        model: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None
    ) -> str:
        """
        生成单张图片
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度（使用配置默认值）
            height: 图片高度（使用配置默认值）
            model: 模型名称（使用配置默认值）
            prompt_extend: 智能改写（使用配置默认值）
            seed: 种子（使用配置默认值）
            
        Returns:
            图片 URL
        """
        urls = await self.generate_batch(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            n=1,
            model=model,
            prompt_extend=prompt_extend,
            seed=seed
        )
        return urls[0] if urls else ""
    
    async def generate_batch(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        n: int = 1,
        model: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None
    ) -> List[str]:
        """
        批量生成图片
        """
        # 使用配置的默认值
        final_width = width if width is not None else self.image_config.width
        final_height = height if height is not None else self.image_config.height
        final_model = model or self.image_config.model
        
        # 构造 size 参数
        size = f"{final_width}*{final_height}"
        
        params = {
            'api_key': self.api_key,
            'model': final_model,
            'prompt': prompt,
            'n': n,
            'size': size,
            'prompt_extend': prompt_extend if prompt_extend is not None else self.image_config.prompt_extend,
        }
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        # 种子设置
        final_seed = seed if seed is not None else self.image_config.seed
        if final_seed is not None:
            params['seed'] = final_seed
        
        # 创建异步任务
        rsp = ImageSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建任务失败: {rsp.code} - {rsp.message}")
        
        # 等待任务完成，设置更长的超时时间（最多等待5分钟）
        import time
        task_id = rsp.output.task_id
        max_wait_time = 300  # 5分钟
        poll_interval = 3  # 每3秒检查一次
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            rsp = ImageSynthesis.fetch(task=task_id, api_key=self.api_key)
            
            if rsp.status_code != HTTPStatus.OK:
                raise Exception(f"查询任务状态失败: {rsp.code} - {rsp.message}")
            
            task_status = rsp.output.task_status
            
            if task_status == 'SUCCEEDED':
                urls = [result.url for result in rsp.output.results]
                return urls
            elif task_status == 'FAILED':
                error_msg = getattr(rsp.output, 'message', '未知错误')
                raise Exception(f"图片生成失败: {error_msg}")
            elif task_status in ['PENDING', 'RUNNING']:
                # 继续等待
                time.sleep(poll_interval)
                elapsed_time += poll_interval
            else:
                raise Exception(f"未知的任务状态: {task_status}")
        
        raise Exception(f"图片生成超时（已等待 {max_wait_time} 秒）")
    
    async def generate_character_views(
        self,
        base_prompt: str,
        common_prompt: str = "半身人物肖像，白色纯净背景，高清细节，一致的光线，专业摄影风格"
    ) -> dict:
        """
        生成角色三视图
        """
        views = {
            "front": "正面视角，面向镜头",
            "side": "侧面视角，面向右侧",
            "back": "背面视角，背对镜头"
        }
        
        result = {}
        
        for view_name, view_prompt in views.items():
            full_prompt = f"{common_prompt}, {base_prompt}, {view_prompt}"
            url = await self.generate(full_prompt)
            result[view_name] = url
        
        return result
