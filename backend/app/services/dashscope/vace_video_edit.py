"""
VACE 视频编辑服务

支持：
1. 视频重绘（video_repainting）
2. 局部编辑（video_edit）
"""

import base64
import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple
from urllib.parse import urlparse

import cv2
import httpx
from PIL import Image

from ...config import get_config
from ..oss import oss_service


class VaceVideoEditService:
    """wanx2.1-vace-plus 视频编辑服务"""

    MODEL_NAME = "wanx2.1-vace-plus"
    SUPPORTED_IMAGE_FORMATS = {"JPEG", "JPG", "PNG", "BMP", "TIFF", "WEBP"}
    MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
    MIN_VIDEO_FPS = 16
    MAX_VIDEO_DURATION = 5.0
    MAX_OUTPUT_PIXELS = 1280 * 720
    URL_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.base_url = config.base_url

    async def create_video_repainting_task(
        self,
        *,
        prompt: str,
        source_video_url: str,
        reference_image_url: Optional[str] = None,
        control_condition: str,
        strength: Optional[float] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None,
        watermark: Optional[bool] = None,
        model: Optional[str] = None,
    ) -> str:
        input_data = {
            "function": "video_repainting",
            "prompt": prompt,
            "video_url": source_video_url,
        }
        if reference_image_url:
            input_data["ref_images_url"] = [reference_image_url]

        parameters = {
            "control_condition": control_condition,
        }
        if reference_image_url:
            # VACE 当前在传入参考图时要求同步声明图像用途；
            # 现阶段视频工作室仅支持单图主体参考，因此默认按 obj 处理。
            parameters["obj_or_bg"] = ["obj"]
        if strength is not None:
            parameters["strength"] = strength
        if prompt_extend is not None:
            parameters["prompt_extend"] = prompt_extend
        if seed is not None:
            parameters["seed"] = seed
        if watermark is not None:
            parameters["watermark"] = watermark

        return await self._create_task(model or self.MODEL_NAME, input_data, parameters)

    async def create_video_edit_task(
        self,
        *,
        prompt: str,
        source_video_url: str,
        mask_image_url: str,
        mask_frame_id: int = 1,
        reference_image_url: Optional[str] = None,
        control_condition: Optional[str] = None,
        mask_type: Optional[str] = None,
        expand_ratio: Optional[float] = None,
        expand_mode: Optional[str] = None,
        size: Optional[str] = None,
        prompt_extend: Optional[bool] = None,
        seed: Optional[int] = None,
        watermark: Optional[bool] = None,
        model: Optional[str] = None,
    ) -> str:
        input_data = {
            "function": "video_edit",
            "prompt": prompt,
            "video_url": source_video_url,
            "mask_image_url": mask_image_url,
            "mask_frame_id": mask_frame_id,
        }
        if reference_image_url:
            input_data["ref_images_url"] = [reference_image_url]

        parameters = {}
        if reference_image_url:
            # 当前前端只支持单张参考图，默认按主体参考处理。
            parameters["obj_or_bg"] = ["obj"]
        if control_condition:
            parameters["control_condition"] = control_condition
        if mask_type:
            parameters["mask_type"] = mask_type
        if expand_ratio is not None:
            parameters["expand_ratio"] = expand_ratio
        if expand_mode:
            parameters["expand_mode"] = expand_mode
        if size:
            parameters["size"] = size
        if prompt_extend is not None:
            parameters["prompt_extend"] = prompt_extend
        if seed is not None:
            parameters["seed"] = seed
        if watermark is not None:
            parameters["watermark"] = watermark

        return await self._create_task(model or self.MODEL_NAME, input_data, parameters)

    async def get_task_status(self, task_id: str, project_id: str = "") -> Tuple[str, Optional[str]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            result = response.json()

        output = result.get("output", {})
        status = output.get("task_status", "UNKNOWN")
        request_id = result.get("request_id", "N/A")
        print(f"[VACE任务状态查询] status_code: {response.status_code}")
        print(f"[VACE任务状态查询] request_id: {request_id}")
        print(f"[VACE任务状态查询] task_status: {status}")
        if response.status_code != 200:
            raise Exception(f"查询任务状态失败: {result.get('code', 'Unknown')} - {result.get('message', 'Unknown error')}")

        if status == "FAILED":
            error_code = output.get("code") or result.get("code") or "Unknown"
            error_message = output.get("message") or result.get("message") or "未知错误"
            print(f"\n{'!'*60}")
            print("[VACE任务失败] 详细错误信息:")
            print(json.dumps({
                "request_id": request_id,
                "output": {
                    "task_id": task_id,
                    "task_status": status,
                    "code": error_code,
                    "message": error_message,
                }
            }, ensure_ascii=False, indent=4))
            print(f"{'!'*60}\n")
            raise Exception(f"VACE任务失败: {error_code} - {error_message}")

        video_url = output.get("video_url") if status == "SUCCEEDED" else None
        if status == "SUCCEEDED" and video_url:
            if not oss_service.is_enabled():
                raise Exception("OSS未启用，无法持久化VACE生成视频")
            video_url = await oss_service.upload_video_async(video_url, project_id)

        return status, video_url

    async def prepare_source_video(self, project_id: str, video_url: str) -> dict:
        metadata, preview_bytes = await self._inspect_video(video_url, require_preview=True)
        preview_data_url = self._to_data_url(preview_bytes, "image/jpeg")

        preview_url = None
        if oss_service.is_enabled():
            filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
            preview_url = await oss_service.upload_bytes_async(
                preview_bytes,
                f"video_studio/previews/{project_id}/{filename}",
            )

        return {
            "preview_image_data_url": preview_data_url,
            "preview_image_url": preview_url,
            "metadata": metadata,
            "warnings": metadata.get("warnings", []),
        }

    async def validate_source_video(self, video_url: str) -> dict:
        metadata, _ = await self._inspect_video(video_url, require_preview=False)
        return metadata

    async def validate_reference_image(self, image_url: str) -> dict:
        content, _ = await self._download_bytes(image_url, timeout=httpx.Timeout(20.0, read=120.0))
        if len(content) > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError("参考图大小不能超过10MB")

        try:
            image = Image.open(BytesIO(content))
            image_format = (image.format or "").upper()
        except Exception as exc:
            raise ValueError(f"无法读取参考图: {exc}") from exc

        if image_format not in self.SUPPORTED_IMAGE_FORMATS:
            raise ValueError("参考图格式仅支持 JPG/JPEG/PNG/BMP/TIFF/WEBP")

        width, height = image.size
        if min(width, height) < 360 or max(width, height) > 2000:
            raise ValueError("参考图分辨率宽高需在360-2000像素之间")

        return {
            "format": image_format,
            "width": width,
            "height": height,
            "file_size": len(content),
        }

    async def validate_mask_image(self, mask_image_url: str, expected_width: int, expected_height: int) -> dict:
        content, _ = await self._download_bytes(mask_image_url, timeout=httpx.Timeout(20.0, read=120.0))
        return self._normalize_and_validate_mask(content, expected_width, expected_height, enforce_binary=True)

    async def upload_mask(self, project_id: str, source_video_url: str, mask_bytes: bytes) -> dict:
        if not oss_service.is_enabled():
            raise ValueError("OSS未启用，请先在设置中配置并启用OSS")

        metadata = await self.validate_source_video(source_video_url)
        normalized = self._normalize_and_validate_mask(
            mask_bytes,
            metadata["width"],
            metadata["height"],
            enforce_binary=False,
        )
        filename = f"{datetime.now().strftime('%Y%m%d/%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
        mask_url = await oss_service.upload_bytes_async(
            normalized["normalized_bytes"],
            f"video_studio/masks/{project_id}/{filename}",
        )
        return {
            "mask_image_url": mask_url,
            "width": metadata["width"],
            "height": metadata["height"],
        }

    async def _create_task(self, model_name: str, input_data: dict, parameters: dict) -> str:
        request_body = {
            "model": model_name,
            "input": input_data,
            "parameters": parameters,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/video-generation/video-synthesis",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
                json=request_body,
            )
            result = response.json()

        if response.status_code != 200:
            raise Exception(f"创建任务失败: {result.get('code', 'Unknown')} - {result.get('message', 'Unknown error')}")

        task_id = result.get("output", {}).get("task_id")
        if not task_id:
            raise Exception("创建任务失败: 未返回 task_id")
        return task_id

    async def _download_bytes(self, url: str, timeout: httpx.Timeout) -> Tuple[bytes, str]:
        self._validate_url(url)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise ValueError(f"无法下载文件: HTTP {response.status_code}")
            return response.content, response.headers.get("content-type", "")

    async def _inspect_video(self, video_url: str, require_preview: bool) -> Tuple[dict, Optional[bytes]]:
        content, content_type = await self._download_bytes(
            video_url,
            timeout=httpx.Timeout(20.0, read=300.0),
        )
        file_size = len(content)
        if file_size > self.MAX_VIDEO_SIZE_BYTES:
            raise ValueError("源视频大小不能超过50MB")

        parsed = urlparse(video_url)
        path = parsed.path.lower()
        if not path.endswith(".mp4") and "mp4" not in content_type.lower():
            raise ValueError("源视频格式仅支持MP4")

        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_file.write(content)
        tmp_file.close()

        cap = cv2.VideoCapture(tmp_file.name)
        try:
            if not cap.isOpened():
                raise ValueError("无法打开源视频文件")

            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

            if fps < self.MIN_VIDEO_FPS:
                raise ValueError("源视频帧率需大于等于16FPS")
            if width <= 0 or height <= 0:
                raise ValueError("无法识别源视频分辨率")

            duration = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
            warnings = []
            if duration > self.MAX_VIDEO_DURATION:
                warnings.append("输入视频超过5秒，模型只会使用前5秒")
            if width * height > self.MAX_OUTPUT_PIXELS:
                warnings.append("输入视频超过720P，模型会按比例缩放到不超过720P")

            preview_bytes = None
            if require_preview:
                ret, frame = cap.read()
                if not ret or frame is None:
                    raise ValueError("无法提取源视频首帧")
                success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if not success:
                    raise ValueError("源视频首帧编码失败")
                preview_bytes = buffer.tobytes()

            metadata = {
                "width": width,
                "height": height,
                "fps": fps,
                "duration": duration,
                "frame_count": frame_count,
                "file_size": file_size,
                "format": "mp4",
                "warnings": warnings,
            }
            return metadata, preview_bytes
        finally:
            cap.release()
            os.unlink(tmp_file.name)

    def _normalize_and_validate_mask(
        self,
        mask_bytes: bytes,
        expected_width: int,
        expected_height: int,
        *,
        enforce_binary: bool,
    ) -> dict:
        if len(mask_bytes) > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError("Mask图片大小不能超过10MB")

        try:
            image = Image.open(BytesIO(mask_bytes))
            image_format = (image.format or "").upper()
        except Exception as exc:
            raise ValueError(f"无法读取Mask图片: {exc}") from exc

        if image_format not in self.SUPPORTED_IMAGE_FORMATS:
            raise ValueError("Mask图片格式仅支持 JPG/JPEG/PNG/BMP/TIFF/WEBP")

        if image.size != (expected_width, expected_height):
            raise ValueError("Mask图片分辨率必须与源视频完全一致")

        grayscale = image.convert("L")
        pixels = set(grayscale.getdata())
        if enforce_binary and not pixels.issubset({0, 255}):
            raise ValueError("Mask图片必须是严格黑白二值图")

        binary = grayscale.point(lambda p: 255 if p >= 128 else 0, mode="1").convert("L")
        if binary.getbbox() is None:
            raise ValueError("Mask不能为空，请至少涂抹一个区域")

        mask_rgb = Image.merge("RGB", (binary, binary, binary))
        output = BytesIO()
        mask_rgb.save(output, format="PNG", optimize=True)
        normalized_bytes = output.getvalue()

        return {
            "format": image_format,
            "width": expected_width,
            "height": expected_height,
            "normalized_bytes": normalized_bytes,
        }

    def _validate_url(self, url: str) -> None:
        if self.URL_CHINESE_RE.search(url):
            raise ValueError("URL地址中不能包含中文字符")

    @staticmethod
    def _to_data_url(data: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
