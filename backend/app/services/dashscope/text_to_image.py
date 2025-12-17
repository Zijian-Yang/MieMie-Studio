"""
阿里云 DashScope 文生图服务封装
参考: https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
"""

from typing import List, Optional, Tuple
from http import HTTPStatus
import dashscope
from dashscope import ImageSynthesis
import httpx
from io import BytesIO
from PIL import Image
import base64

from app.config import get_config, IMAGE_MODELS
from app.services.oss import oss_service


# wan2.6-image 参考图片尺寸限制
WAN26_IMAGE_MIN_DIM = 384
WAN26_IMAGE_MAX_DIM = 5000


async def validate_and_resize_reference_image(
    image_url: str, 
    min_dim: int = WAN26_IMAGE_MIN_DIM, 
    max_dim: int = WAN26_IMAGE_MAX_DIM
) -> Tuple[bool, str, str]:
    """
    验证并调整参考图片尺寸，确保符合 wan2.6-image 要求
    
    Args:
        image_url: 图片URL
        min_dim: 最小尺寸 (默认384)
        max_dim: 最大尺寸 (默认5000)
    
    Returns:
        (is_valid, new_url_or_error, message)
        - is_valid: 是否有效（原图有效或成功调整）
        - new_url_or_error: 新的URL（如果调整了）或错误信息
        - message: 处理信息
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            if response.status_code != 200:
                return False, f"无法获取图片: HTTP {response.status_code}", ""
            
            # 读取图片
            img = Image.open(BytesIO(response.content))
            width, height = img.size
            
            # 检查是否需要调整
            needs_resize = False
            new_width, new_height = width, height
            
            # 检查最小尺寸
            if width < min_dim or height < min_dim:
                needs_resize = True
                # 按比例放大到最小尺寸
                scale = max(min_dim / width, min_dim / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
            
            # 检查最大尺寸
            if new_width > max_dim or new_height > max_dim:
                needs_resize = True
                # 按比例缩小到最大尺寸
                scale = min(max_dim / new_width, max_dim / new_height)
                new_width = int(new_width * scale)
                new_height = int(new_height * scale)
            
            if not needs_resize:
                return True, image_url, f"图片尺寸 {width}x{height} 符合要求"
            
            # 调整图片尺寸
            print(f"[wan2.6-image] 调整参考图尺寸: {width}x{height} -> {new_width}x{new_height}")
            
            # 使用高质量重采样
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为 base64
            buffer = BytesIO()
            # 保存为原格式或默认 PNG
            img_format = img.format or 'PNG'
            if img_format.upper() == 'JPEG':
                resized_img = resized_img.convert('RGB')
            resized_img.save(buffer, format=img_format, quality=95)
            buffer.seek(0)
            
            # 转为 base64 URL
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            mime_type = f"image/{img_format.lower()}"
            if img_format.upper() == 'JPEG':
                mime_type = "image/jpeg"
            elif img_format.upper() == 'PNG':
                mime_type = "image/png"
            
            base64_url = f"data:{mime_type};base64,{img_base64}"
            
            return True, base64_url, f"图片已从 {width}x{height} 调整为 {new_width}x{new_height}"
            
    except Exception as e:
        return False, f"处理图片失败: {str(e)}", ""


class TextToImageService:
    """文生图服务"""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.image_config = config.image
        self.base_url = config.base_url
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
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        project_id: str = ""
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
            watermark: 是否添加水印（仅 wan2.6 支持）
            seed: 种子（使用配置默认值）
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            图片 URL（如果启用 OSS，返回 OSS URL）
        """
        urls = await self.generate_batch(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            n=1,
            model=model,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            project_id=project_id
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
        watermark: Optional[bool] = None,
        seed: Optional[int] = None,
        project_id: str = ""
    ) -> List[str]:
        """
        批量生成图片
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度
            height: 图片高度
            n: 生成数量
            model: 模型名称
            prompt_extend: 智能改写
            watermark: 是否添加水印（仅 wan2.6 支持）
            seed: 种子
            project_id: 项目ID，用于 OSS 上传路径
            
        Returns:
            图片 URL 列表（如果启用 OSS，返回 OSS URL）
        """
        # 使用配置的默认值
        final_width = width if width is not None else self.image_config.width
        final_height = height if height is not None else self.image_config.height
        final_model = model or self.image_config.model
        
        # 获取模型配置
        model_info = IMAGE_MODELS.get(final_model, {})
        use_http = model_info.get('use_http', False)
        is_async = model_info.get('is_async', False)
        
        # 构造 size 参数
        size = f"{final_width}*{final_height}"
        
        # 种子设置
        final_seed = seed if seed is not None else self.image_config.seed
        final_prompt_extend = prompt_extend if prompt_extend is not None else self.image_config.prompt_extend
        final_watermark = watermark if watermark is not None else getattr(self.image_config, 'watermark', False)
        
        # wan2.6-image 使用 HTTP 异步调用（需要轮询）
        if final_model == 'wan2.6-image':
            return await self._generate_batch_wan26_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                size=size,
                n=n,
                prompt_extend=final_prompt_extend,
                watermark=final_watermark,
                seed=final_seed,
                project_id=project_id,
                image_urls=None,  # 纯文生图不需要参考图
                enable_interleave=False
            )
        
        # wan2.6-t2i 使用 HTTP 同步调用
        if use_http:
            return await self._generate_batch_http(
                prompt=prompt,
                negative_prompt=negative_prompt,
                size=size,
                n=n,
                model=final_model,
                prompt_extend=final_prompt_extend,
                watermark=final_watermark,
                seed=final_seed,
                project_id=project_id
            )
        
        # 其他模型使用 SDK 异步调用
        return await self._generate_batch_sdk(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            n=n,
            model=final_model,
            prompt_extend=final_prompt_extend,
            watermark=final_watermark,
            seed=final_seed,
            project_id=project_id
        )
    
    async def _generate_batch_http(
        self,
        prompt: str,
        negative_prompt: str,
        size: str,
        n: int,
        model: str,
        prompt_extend: bool,
        watermark: bool,
        seed: Optional[int],
        project_id: str
    ) -> List[str]:
        """
        使用 HTTP 同步接口生成图片（wan2.6-t2i）
        """
        # 构建请求 URL
        url = f"{self.base_url}/services/aigc/multimodal-generation/generation"
        
        # 构建请求体
        request_body = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            "parameters": {
                "size": size,
                "n": n,
                "prompt_extend": prompt_extend,
                "watermark": watermark,
            }
        }
        
        # 添加可选参数
        if negative_prompt:
            request_body["parameters"]["negative_prompt"] = negative_prompt
        if seed is not None:
            request_body["parameters"]["seed"] = seed
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        print(f"[文生图HTTP] 发送请求到: {url}")
        print(f"[文生图HTTP] 模型: {model}, 尺寸: {size}, 数量: {n}")
        print(f"[文生图HTTP] 提示词: {prompt[:100]}...")
        
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:  # 3分钟超时
                response = await client.post(url, json=request_body, headers=headers)
                
                print(f"[文生图HTTP] 响应状态码: {response.status_code}")
                
                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    error_code = error_data.get('code', 'Unknown')
                    error_message = error_data.get('message', response.text)
                    print(f"[文生图HTTP] 请求失败: {error_code} - {error_message}")
                    raise Exception(f"文生图请求失败: {error_code} - {error_message}")
                
                result = response.json()
                print(f"[文生图HTTP] 响应: request_id={result.get('request_id')}")
                
                # 解析返回的图片 URL
                urls = []
                output = result.get("output", {})
                choices = output.get("choices", [])
                
                for choice in choices:
                    message = choice.get("message", {})
                    content = message.get("content", [])
                    for item in content:
                        if item.get("type") == "image":
                            image_url = item.get("image")
                            if image_url:
                                urls.append(image_url)
                
                print(f"[文生图HTTP] 成功生成 {len(urls)} 张图片")
                
                # 上传到 OSS
                if oss_service.is_enabled() and urls:
                    oss_urls = []
                    for url in urls:
                        oss_url = oss_service.upload_image(url, project_id)
                        oss_urls.append(oss_url)
                    return oss_urls
                
                return urls
                
        except httpx.TimeoutException:
            print(f"[文生图HTTP] 请求超时")
            raise Exception("文生图请求超时")
        except Exception as e:
            print(f"[文生图HTTP] 异常: {str(e)}")
            raise
    
    async def _generate_batch_sdk(
        self,
        prompt: str,
        negative_prompt: str,
        size: str,
        n: int,
        model: str,
        prompt_extend: bool,
        watermark: bool,
        seed: Optional[int],
        project_id: str
    ) -> List[str]:
        """
        使用 SDK 异步接口生成图片（wan2.5 等）
        """
        import asyncio
        
        params = {
            'api_key': self.api_key,
            'model': model,
            'prompt': prompt,
            'n': n,
            'size': size,
            'prompt_extend': prompt_extend,
            'watermark': watermark,  # 水印参数
        }
        
        if negative_prompt:
            params['negative_prompt'] = negative_prompt
        
        if seed is not None:
            params['seed'] = seed
        
        print(f"[文生图SDK] 模型: {model}, 尺寸: {size}, 数量: {n}")
        print(f"[文生图SDK] 智能改写: {prompt_extend}, 水印: {watermark}, 种子: {seed}")
        print(f"[文生图SDK] 提示词: {prompt[:100]}...")
        
        # 创建异步任务
        rsp = ImageSynthesis.async_call(**params)
        
        if rsp.status_code != HTTPStatus.OK:
            raise Exception(f"创建任务失败: {rsp.code} - {rsp.message}")
        
        # 等待任务完成，设置更长的超时时间（最多等待5分钟）
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
                # 如果启用了 OSS，上传图片并返回 OSS URL
                if oss_service.is_enabled():
                    oss_urls = []
                    for url in urls:
                        oss_url = oss_service.upload_image(url, project_id)
                        oss_urls.append(oss_url)
                    return oss_urls
                return urls
            elif task_status == 'FAILED':
                error_msg = getattr(rsp.output, 'message', '未知错误')
                raise Exception(f"图片生成失败: {error_msg}")
            elif task_status in ['PENDING', 'RUNNING']:
                # 继续等待（使用异步 sleep 避免阻塞事件循环）
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
            else:
                raise Exception(f"未知的任务状态: {task_status}")
        
        raise Exception(f"图片生成超时（已等待 {max_wait_time} 秒）")
    
    async def _generate_batch_wan26_image(
        self,
        prompt: str,
        negative_prompt: str,
        size: str,
        n: int,
        prompt_extend: bool,
        watermark: bool,
        seed: Optional[int],
        project_id: str,
        image_urls: Optional[List[str]] = None,
        enable_interleave: bool = False,
        max_images: int = 5
    ) -> List[str]:
        """
        使用 HTTP 异步接口生成图片（wan2.6-image）
        支持：
        - 参考图生图 (enable_interleave=false, 1-3张参考图)
        - 图文混合输出 (enable_interleave=true, 0-1张参考图)
        - 纯文生图 (enable_interleave=false/true, 无参考图)
        
        注意：参考图片尺寸必须在 384-5000 像素之间，否则会自动调整
        """
        import asyncio
        import json
        
        # 构建请求 URL
        url = f"{self.base_url}/services/aigc/image-generation/generation"
        
        # 构建 content 数组
        content = [{"text": prompt}]
        
        # 添加参考图片（验证并调整尺寸）
        if image_urls:
            for i, img_url in enumerate(image_urls):
                print(f"[wan2.6-image] 验证参考图 {i+1}/{len(image_urls)}...")
                is_valid, result, message = await validate_and_resize_reference_image(img_url)
                
                if not is_valid:
                    raise Exception(f"参考图 {i+1} 无效: {result}")
                
                if message:
                    print(f"[wan2.6-image] 参考图 {i+1}: {message}")
                
                content.append({"image": result})
        
        # 构建请求体
        request_body = {
            "model": "wan2.6-image",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            },
            "parameters": {
                "n": n,
                "watermark": watermark
            }
        }
        
        # 添加可选参数
        if size:
            request_body["parameters"]["size"] = size
        
        if negative_prompt:
            request_body["parameters"]["negative_prompt"] = negative_prompt
        
        if enable_interleave:
            request_body["parameters"]["enable_interleave"] = True
            request_body["parameters"]["max_images"] = max_images
            request_body["parameters"]["n"] = 1  # 图文混合模式固定为1
        else:
            request_body["parameters"]["enable_interleave"] = False
            # prompt_extend 仅在 enable_interleave=false 时生效
            request_body["parameters"]["prompt_extend"] = prompt_extend
        
        if seed is not None:
            request_body["parameters"]["seed"] = seed
        
        print(f"[wan2.6-image] 创建异步任务...")
        print(f"[wan2.6-image] 尺寸: {size}, 数量: {n}, 参考图: {len(image_urls) if image_urls else 0}张")
        print(f"[wan2.6-image] enable_interleave: {enable_interleave}, prompt_extend: {prompt_extend}")
        print(f"[wan2.6-image] 提示词: {prompt[:100]}...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-DashScope-Async": "enable"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 步骤1：创建任务
                response = await client.post(url, headers=headers, json=request_body)
                result = response.json()
                
                print(f"[wan2.6-image] 创建任务响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                
                if "output" not in result or "task_id" not in result.get("output", {}):
                    error_code = result.get("code", "Unknown")
                    error_msg = result.get("message", "未知错误")
                    raise Exception(f"创建任务失败: {error_code} - {error_msg}")
                
                task_id = result["output"]["task_id"]
                print(f"[wan2.6-image] 任务已创建，task_id: {task_id}")
                
                # 步骤2：轮询获取结果
                query_url = f"{self.base_url}/tasks/{task_id}"
                max_wait_time = 300  # 5分钟
                poll_interval = 10  # 每10秒检查一次
                elapsed_time = 0
                
                query_headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                while elapsed_time < max_wait_time:
                    await asyncio.sleep(poll_interval)
                    elapsed_time += poll_interval
                    
                    query_response = await client.get(query_url, headers=query_headers)
                    query_result = query_response.json()
                    
                    task_status = query_result.get("output", {}).get("task_status", "UNKNOWN")
                    print(f"[wan2.6-image] 任务状态: {task_status}, 已等待: {elapsed_time}s")
                    
                    if task_status == "SUCCEEDED":
                        # 从 choices 中提取图片 URL
                        choices = query_result.get("output", {}).get("choices", [])
                        urls = []
                        
                        for choice in choices:
                            message_content = choice.get("message", {}).get("content", [])
                            for item in message_content:
                                if item.get("type") == "image" and item.get("image"):
                                    urls.append(item["image"])
                        
                        print(f"[wan2.6-image] 生成成功，共 {len(urls)} 张图片")
                        
                        # 上传到 OSS
                        if oss_service.is_enabled():
                            oss_urls = []
                            for img_url in urls:
                                oss_url = oss_service.upload_image(img_url, project_id)
                                oss_urls.append(oss_url)
                            return oss_urls
                        
                        return urls
                    
                    elif task_status == "FAILED":
                        error_code = query_result.get("output", {}).get("code", "Unknown")
                        error_msg = query_result.get("output", {}).get("message", "未知错误")
                        print(f"[wan2.6-image] 任务失败: {error_code} - {error_msg}")
                        print(f"[wan2.6-image] 完整响应: {json.dumps(query_result, ensure_ascii=False)}")
                        raise Exception(f"图片生成失败: {error_code} - {error_msg}")
                    
                    elif task_status in ["PENDING", "RUNNING"]:
                        continue
                    
                    else:
                        raise Exception(f"未知的任务状态: {task_status}")
                
                raise Exception(f"图片生成超时（已等待 {max_wait_time} 秒）")
                
        except httpx.TimeoutException:
            print(f"[wan2.6-image] 请求超时")
            raise Exception("wan2.6-image 请求超时")
        except Exception as e:
            print(f"[wan2.6-image] 异常: {str(e)}")
            raise
    
    async def generate_with_wan26_image(
        self,
        prompt: str,
        image_urls: Optional[List[str]] = None,
        negative_prompt: str = "",
        n: int = 1,
        size: str = "1280*1280",
        prompt_extend: bool = True,
        watermark: bool = False,
        seed: Optional[int] = None,
        enable_interleave: bool = False,
        max_images: int = 5,
        project_id: str = ""
    ) -> List[str]:
        """
        使用 wan2.6-image 生成图片的公开接口
        
        Args:
            prompt: 正向提示词
            image_urls: 参考图片 URL 列表（最多3张）
            negative_prompt: 负向提示词
            n: 生成数量（enable_interleave=false 时 1-4，true 时固定1）
            size: 输出尺寸
            prompt_extend: 智能改写（仅 enable_interleave=false 时生效）
            watermark: 是否添加水印
            seed: 随机种子
            enable_interleave: 是否启用图文混合模式
            max_images: 图文混合模式下最大生成图数（1-5）
            project_id: 项目ID
        """
        return await self._generate_batch_wan26_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            n=n,
            prompt_extend=prompt_extend,
            watermark=watermark,
            seed=seed,
            project_id=project_id,
            image_urls=image_urls,
            enable_interleave=enable_interleave,
            max_images=max_images
        )
    
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
