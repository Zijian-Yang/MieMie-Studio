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
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

import cv2
import httpx
from PIL import Image


async def download_remote_bytes(url: str, timeout: httpx.Timeout | None = None) -> Tuple[bytes, str]:
    effective_timeout = timeout or httpx.Timeout(30.0, read=180.0)
    async with httpx.AsyncClient(timeout=effective_timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "")


async def inspect_remote_image(url: str) -> Dict[str, Any]:
    content, content_type = await download_remote_bytes(url, timeout=httpx.Timeout(20.0, read=120.0))
    image = Image.open(BytesIO(content))
    width, height = image.size
    image_format = (image.format or "").upper()
    has_alpha = image.mode in {"RGBA", "LA", "PA"} or ("transparency" in image.info)

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
