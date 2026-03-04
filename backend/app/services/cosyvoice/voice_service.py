"""
CosyVoice 声音复刻 + 声音设计服务

- 声音复刻：使用 DashScope SDK VoiceEnrollmentService
- 声音设计：使用 REST API（SDK 不支持声音设计）
"""

import logging
import base64
from typing import Optional, List, Dict, Any, Tuple

import httpx
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService

from app.config import get_config

logger = logging.getLogger(__name__)

TARGET_MODEL = "cosyvoice-v3-flash"

VOICE_DESIGN_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


class CosyVoiceCloneService:
    """声音复刻服务（SDK）"""

    def __init__(self):
        self._configure_sdk()

    def _configure_sdk(self):
        config = get_config()
        dashscope.api_key = config.dashscope_api_key
        dashscope.base_http_api_url = config.base_url
        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

    def create_voice(
        self,
        prefix: str,
        url: str,
        language_hints: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        创建复刻音色。同步阻塞，需通过 asyncio.to_thread() 调用。

        Returns:
            (voice_id, request_id)
        """
        self._configure_sdk()
        service = VoiceEnrollmentService()

        kwargs = {
            "target_model": TARGET_MODEL,
            "prefix": prefix,
            "url": url,
        }
        if language_hints:
            kwargs["language_hints"] = [language_hints]

        logger.info(f"[声音复刻] 创建音色: prefix={prefix}, target_model={TARGET_MODEL}")
        voice_id = service.create_voice(**kwargs)
        request_id = service.get_last_request_id() or ""
        logger.info(f"[声音复刻] 创建成功: voice_id={voice_id}, request_id={request_id}")
        return voice_id, request_id

    def query_voice(self, voice_id: str) -> Dict[str, Any]:
        """
        查询音色状态。

        Returns:
            dict with keys: status, gmt_create, gmt_modified, etc.
        """
        self._configure_sdk()
        service = VoiceEnrollmentService()
        info = service.query_voice(voice_id=voice_id)
        logger.info(f"[声音复刻] 查询音色: voice_id={voice_id}, status={info.get('status')}")
        return info

    def list_voices(self, prefix: Optional[str] = None, page_index: int = 0, page_size: int = 100) -> List[Dict]:
        """查询已创建的音色列表"""
        self._configure_sdk()
        service = VoiceEnrollmentService()
        voices = service.list_voices(prefix=prefix, page_index=page_index, page_size=page_size)
        return voices or []

    def delete_voice(self, voice_id: str) -> None:
        """删除音色"""
        self._configure_sdk()
        service = VoiceEnrollmentService()
        service.delete_voice(voice_id=voice_id)
        logger.info(f"[声音复刻] 删除音色: voice_id={voice_id}")


class CosyVoiceDesignService:
    """声音设计服务（REST API）"""

    async def create_voice(
        self,
        voice_prompt: str,
        preview_text: str,
        prefix: str,
        sample_rate: int = 24000,
        response_format: str = "wav",
    ) -> Tuple[str, bytes, str]:
        """
        创建设计音色。

        Returns:
            (voice_id, preview_audio_bytes, request_id)
        """
        config = get_config()
        api_key = config.dashscope_api_key

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": "voice-enrollment",
            "input": {
                "action": "create_voice",
                "target_model": TARGET_MODEL,
                "voice_prompt": voice_prompt,
                "preview_text": preview_text,
                "prefix": prefix,
            },
            "parameters": {
                "sample_rate": sample_rate,
                "response_format": response_format,
            },
        }

        logger.info(f"[声音设计] 创建音色: prefix={prefix}, prompt={voice_prompt[:50]}...")

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(VOICE_DESIGN_URL, headers=headers, json=data)

        if resp.status_code != 200:
            error_text = resp.text
            logger.error(f"[声音设计] 请求失败: HTTP {resp.status_code}, {error_text}")
            raise RuntimeError(f"声音设计请求失败: HTTP {resp.status_code} - {error_text}")

        result = resp.json()
        output = result.get("output", {})
        voice_id = output.get("voice_id", "")
        request_id = result.get("request_id", "")

        preview_audio_data = output.get("preview_audio", {}).get("data", "")
        preview_bytes = base64.b64decode(preview_audio_data) if preview_audio_data else b""

        if not voice_id:
            raise RuntimeError(f"声音设计失败: 未返回 voice_id (request_id={request_id})")

        logger.info(f"[声音设计] 创建成功: voice_id={voice_id}, preview={len(preview_bytes)} bytes")
        return voice_id, preview_bytes, request_id
