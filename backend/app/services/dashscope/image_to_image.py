"""
图像编辑服务（图生图/风格迁移）
参考: https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference

使用说明：
1. 图片风格参考生图（使用 image2image 端点）
   - 适用于：基于风格参考图 + 文字描述生成新图
   - 模型：wan2.5-i2i-preview（图像编辑模型）
   - images: 参考图片URL列表
   - 在 prompt 中说明"参考该图片的风格生成..."

2. 文本风格生图（使用 text2image 端点）
   - 适用于：基于纯文本风格描述生成新图
   - 模型：wan2.5-t2i-preview（文生图模型）
   - 将风格文本嵌入提示词
"""

import asyncio
import requests
from typing import Optional, List
from http import HTTPStatus
import dashscope
from dashscope import ImageSynthesis

from app.config import get_config, IMAGE_EDIT_MODELS, IMAGE_MODELS
from app.services.oss import oss_service


class ImageToImageService:
    """图像编辑/风格迁移服务"""

    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.image_edit_config = config.image_edit
        self.image_config = config.image
        self.base_url = config.base_url
        dashscope.base_http_api_url = config.base_url

    def _validate_size(self, model: str, width: int, height: int):
        """验证图片尺寸是否符合模型限制"""
        # 首先尝试在图像编辑模型中查找
        model_info = IMAGE_EDIT_MODELS.get(model)
        if not model_info:
            # 然后尝试在文生图模型中查找
            model_info = IMAGE_MODELS.get(model)
        if not model_info:
            # 使用默认值
            model_info = {
                "min_pixels": 65536,
                "max_pixels": 4194304,
                "min_ratio": 0.25,
                "max_ratio": 4.0
            }

        min_pixels = model_info.get("min_pixels", 0)
        max_pixels = model_info.get("max_pixels", float('inf'))
        min_ratio = model_info.get("min_ratio", 0)
        max_ratio = model_info.get("max_ratio", float('inf'))

        current_pixels = width * height
        current_ratio = width / height if height > 0 else 1

        if not (min_pixels <= current_pixels <= max_pixels):
            raise ValueError(f"图片总像素 ({current_pixels}) 超出模型限制 [{min_pixels}, {max_pixels}]")
        if not (min_ratio <= current_ratio <= max_ratio):
            raise ValueError(f"图片宽高比 ({current_ratio:.2f}) 超出模型限制 [{min_ratio:.2f}, {max_ratio:.2f}]")

    async def generate_with_style_image(
        self,
        prompt: str,
        style_image_url: str,
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        model: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None,
        project_id: str = ""
    ) -> str:
        """
        使用单张图片风格生成新图片（图生图）
        使用 image2image 端点 + 图像编辑模型
        
        Args:
            prompt: 生成提示词（应包含"参考该图片的风格"等描述）
            style_image_url: 风格参考图片 URL（单张）
            negative_prompt: 负向提示词
            width: 图片宽度
            height: 图片高度
            model: 使用的模型（默认 wan2.5-i2i-preview）
            prompt_extend: 是否智能改写
            seed: 随机种子
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            生成的图片 URL（如果启用 OSS，返回 OSS URL）
        """
        return await self.generate_with_multi_images(
            prompt=prompt,
            image_urls=[style_image_url],
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            model=model,
            prompt_extend=prompt_extend,
            seed=seed,
            project_id=project_id
        )
    
    async def generate_with_multi_images(
        self,
        prompt: str,
        image_urls: List[str],
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        model: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None,
        project_id: str = ""
    ) -> str:
        """
        使用多张参考图片生成新图片（多图生图）
        使用 image2image 端点 + 图像编辑模型
        
        根据阿里云 API 文档 (https://www.alibabacloud.com/help/zh/model-studio/wan2-5-image-edit-api-reference):
        - images 字段接受多个 URL 列表
        - 多图生图时，可以在 prompt 中使用"第一个图"、"第二个图"等方式引用不同的参考图
        
        Args:
            prompt: 生成提示词（可使用"第一个图中的xxx"引用不同参考图）
            image_urls: 参考图片 URL 列表（按顺序对应"第一个图"、"第二个图"等）
            negative_prompt: 负向提示词
            width: 图片宽度
            height: 图片高度
            model: 使用的模型（默认 wan2.5-i2i-preview）
            prompt_extend: 是否智能改写
            seed: 随机种子
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            生成的图片 URL（如果启用 OSS，返回 OSS URL）
        """
        if not image_urls:
            raise ValueError("至少需要一张参考图片")
        
        # 使用图像编辑模型配置
        final_model = model or self.image_edit_config.model  # wan2.5-i2i-preview
        final_width = width or self.image_edit_config.width
        final_height = height or self.image_edit_config.height
        final_prompt_extend = prompt_extend if prompt_extend is not None else self.image_edit_config.prompt_extend

        self._validate_size(final_model, final_width, final_height)

        # 使用 HTTP API 调用 image2image 端点
        url = f"{self.base_url}/services/aigc/image2image/image-synthesis"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }
        
        # 根据 API 文档，使用 images 字段传递参考图片列表
        # 多图生图时，prompt 中可以使用"第一个图"、"第二个图"等引用
        payload = {
            "model": final_model,
            "input": {
                "prompt": prompt,
                "images": image_urls  # 传递完整的图片 URL 列表，保持顺序
            },
            "parameters": {
                "size": f"{final_width}*{final_height}",
                "n": 1
            }
        }
        
        if negative_prompt:
            payload["input"]["negative_prompt"] = negative_prompt
        
        if final_prompt_extend:
            payload["parameters"]["prompt_extend"] = final_prompt_extend
            
        final_seed = seed if seed is not None else self.image_edit_config.seed
        if final_seed is not None:
            payload["parameters"]["seed"] = final_seed

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            result = response.json()
            
            if response.status_code != 200:
                error_msg = result.get("message", result.get("error", {}).get("message", str(result)))
                raise Exception(f"API错误 ({response.status_code}): {error_msg}")
                
        except requests.exceptions.Timeout:
            raise Exception("请求超时")
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")
        
        if "output" not in result or "task_id" not in result["output"]:
            error_msg = result.get("message", str(result))
            raise Exception(f"创建任务失败: {error_msg}")
        
        task_id = result["output"]["task_id"]
        
        # 轮询任务状态
        return await self._poll_task(task_id, project_id)

    async def _poll_task(self, task_id: str, project_id: str = "") -> str:
        """轮询任务状态直到完成"""
        status_url = f"{self.base_url}/tasks/{task_id}"
        timeout = 300  # 5分钟超时
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise Exception("图片生成任务超时")
            
            try:
                status_response = requests.get(
                    status_url, 
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
                status_result = status_response.json()
            except requests.exceptions.RequestException as e:
                raise Exception(f"查询任务失败: {str(e)}")
            
            task_status = status_result.get("output", {}).get("task_status", "")
            
            if task_status == "SUCCEEDED":
                results = status_result.get("output", {}).get("results", [])
                if results and "url" in results[0]:
                    image_url = results[0]["url"]
                    # 如果启用了 OSS，上传图片并返回 OSS URL
                    if oss_service.is_enabled():
                        return oss_service.upload_image(image_url, project_id)
                    return image_url
                raise Exception("图片生成成功但未返回URL")
            elif task_status == "FAILED":
                error_msg = status_result.get("output", {}).get("message", "未知错误")
                code = status_result.get("output", {}).get("code", "")
                raise Exception(f"图片生成失败: {code} - {error_msg}")
            elif task_status in ["PENDING", "RUNNING"]:
                await asyncio.sleep(3)
            else:
                raise Exception(f"未知的任务状态: {task_status}")
