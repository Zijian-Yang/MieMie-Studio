"""
远程媒体探测与校验辅助工具

用于在提交第三方视频模型前，先对远程图片/视频做轻量探测，
把文档限制尽量前置到平台侧校验。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import base64
import binascii
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import cv2
import httpx
from PIL import Image, UnidentifiedImageError


def _has_transparent_pixels(image: Image.Image) -> bool:
    if image.mode not in {"RGBA", "LA", "PA"} and "transparency" not in image.info:
        return False

    try:
        alpha = image.getchannel("A") if image.mode in {"RGBA", "LA", "PA"} else image.convert("RGBA").getchannel("A")
        alpha_extrema = alpha.getextrema()
    except (OSError, ValueError):
        return "transparency" in image.info

    return bool(alpha_extrema and alpha_extrema[0] < 255)


def _decode_data_uri(value: str) -> Tuple[bytes, str]:
    header, _, payload = value.partition(",")
    if not payload or ";base64" not in header:
        raise ValueError("data URI 格式无效，需使用 data:<MIME>;base64,<data>")
    mime_type = header.replace("data:", "", 1).split(";", 1)[0] or "application/octet-stream"
    try:
        return base64.b64decode(payload, validate=True), mime_type
    except (binascii.Error, ValueError) as exc:
        raise ValueError("data URI base64 内容无法解码") from exc


async def download_remote_bytes(url: str, timeout: httpx.Timeout | None = None) -> Tuple[bytes, str]:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL 为空")
    if url.startswith("data:"):
        return _decode_data_uri(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"不支持的 URL 协议: {parsed.scheme or '空'}")

    effective_timeout = timeout or httpx.Timeout(30.0, read=180.0)
    try:
        async with httpx.AsyncClient(timeout=effective_timeout, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        content_type = exc.response.headers.get("content-type", "")
        raise ValueError(f"HTTP {exc.response.status_code}，content-type={content_type or '-'}") from exc
    except httpx.TimeoutException as exc:
        raise ValueError("下载超时") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"下载失败: {exc.__class__.__name__}: {exc}") from exc
    return response.content, response.headers.get("content-type", "")


async def inspect_remote_image(url: str) -> Dict[str, Any]:
    content, content_type = await download_remote_bytes(url, timeout=httpx.Timeout(20.0, read=120.0))
    try:
        image = Image.open(BytesIO(content))
        image.load()
    except UnidentifiedImageError as exc:
        raise ValueError(f"不是可识别图片，content-type={content_type or '-'}，bytes={len(content)}") from exc
    except OSError as exc:
        raise ValueError(f"图片解码失败: {exc}，content-type={content_type or '-'}，bytes={len(content)}") from exc

    width, height = image.size
    image_format = (image.format or "").upper()
    has_alpha = _has_transparent_pixels(image)

    return {
        "url": url,
        "content_type": content_type,
        "format": image_format,
        "width": width,
        "height": height,
        "file_size": len(content),
        "aspect_ratio": (width / height) if height else 0,
        "has_alpha": has_alpha,
    }


async def inspect_remote_video(url: str) -> Dict[str, Any]:
    content, content_type = await download_remote_bytes(url, timeout=httpx.Timeout(20.0, read=300.0))
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".mp4"

    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_file.write(content)
    tmp_file.close()

    capture = cv2.VideoCapture(tmp_file.name)
    try:
        if not capture.isOpened():
            raise ValueError("无法打开远程视频文件")

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        if width <= 0 or height <= 0:
            raise ValueError("无法识别视频分辨率")

        duration = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
        return {
            "url": url,
            "content_type": content_type,
            "format": suffix.lstrip(".").lower(),
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration,
            "file_size": len(content),
            "aspect_ratio": (width / height) if height else 0,
            "pixel_count": width * height,
        }
    finally:
        capture.release()
        os.unlink(tmp_file.name)


async def inspect_remote_audio(url: str) -> Dict[str, Any]:
    content, content_type = await download_remote_bytes(url, timeout=httpx.Timeout(20.0, read=300.0))
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".mp3"

    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_file.write(content)
    tmp_file.close()

    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                tmp_file.name,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        probe_data = json.loads(probe.stdout or "{}")
        duration = float((probe_data.get("format") or {}).get("duration") or 0.0)
    except (subprocess.CalledProcessError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("无法识别音频元数据") from exc
    finally:
        os.unlink(tmp_file.name)

    return {
        "url": url,
        "content_type": content_type,
        "format": suffix.lstrip(".").lower(),
        "duration": duration,
        "file_size": len(content),
    }
