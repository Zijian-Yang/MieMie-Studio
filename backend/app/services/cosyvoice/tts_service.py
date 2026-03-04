"""
CosyVoice 文本转语音服务

使用 DashScope SDK 的 SpeechSynthesizer.call() 非流式调用。
SDK 是同步阻塞的，通过 asyncio.to_thread() 包装在异步环境中使用。
"""

import logging
import re
import unicodedata
from typing import Optional, Tuple

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

from app.config import get_config

logger = logging.getLogger(__name__)

AUDIO_FORMAT_MAP = {
    "mp3_8000hz_mono_128kbps": "mp3_8000hz_mono_128kbps",
    "mp3_16000hz_mono_128kbps": "mp3_16000hz_mono_128kbps",
    "mp3_22050hz_mono_256kbps": "mp3_22050hz_mono_256kbps",
    "mp3_24000hz_mono_256kbps": "mp3_24000hz_mono_256kbps",
    "mp3_44100hz_mono_256kbps": "mp3_44100hz_mono_256kbps",
    "mp3_48000hz_mono_256kbps": "mp3_48000hz_mono_256kbps",
    "wav_8000hz_mono_16bit": "wav_8000hz_mono_16bit",
    "wav_16000hz_mono_16bit": "wav_16000hz_mono_16bit",
    "wav_22050hz_mono_16bit": "wav_22050hz_mono_16bit",
    "wav_24000hz_mono_16bit": "wav_24000hz_mono_16bit",
    "wav_44100hz_mono_16bit": "wav_44100hz_mono_16bit",
    "wav_48000hz_mono_16bit": "wav_48000hz_mono_16bit",
    "pcm_8000hz_mono_16bit": "pcm_8000hz_mono_16bit",
    "pcm_16000hz_mono_16bit": "pcm_16000hz_mono_16bit",
    "pcm_22050hz_mono_16bit": "pcm_22050hz_mono_16bit",
    "pcm_24000hz_mono_16bit": "pcm_24000hz_mono_16bit",
    "pcm_44100hz_mono_16bit": "pcm_44100hz_mono_16bit",
    "pcm_48000hz_mono_16bit": "pcm_48000hz_mono_16bit",
}

FORMAT_TO_EXTENSION = {
    "mp3": "mp3",
    "wav": "wav",
    "pcm": "pcm",
}


_CJK_RADICALS_SUPPLEMENT_MAP = {
    0x2E85: '人', 0x2E86: '匚', 0x2E88: '刀', 0x2E89: '刂',
    0x2E8A: '卜', 0x2E8B: '卩', 0x2E8C: '小', 0x2E8D: '小',
    0x2E95: '手', 0x2E96: '手', 0x2E97: '龙', 0x2E98: '日',
    0x2E99: '月', 0x2E9B: '母', 0x2EA7: '毛', 0x2EAA: '水',
    0x2EAB: '水', 0x2EAC: '水', 0x2EAD: '火', 0x2EAE: '火',
    0x2EB3: '牛', 0x2EB6: '示', 0x2EB7: '礻', 0x2EBB: '竹',
    0x2EBC: '米', 0x2EBF: '糸', 0x2EC0: '糸', 0x2EC1: '纟',
    0x2EC5: '见', 0x2EC6: '角', 0x2EC7: '言', 0x2EC8: '讠',
    0x2EC9: '贝', 0x2ECA: '走', 0x2ECB: '车', 0x2ECC: '辶',
    0x2ECD: '辶', 0x2ECF: '邑', 0x2ED1: '长', 0x2ED2: '韦',
    0x2ED4: '页', 0x2ED5: '风', 0x2ED6: '飞', 0x2ED7: '饣',
    0x2ED9: '马', 0x2EDA: '骨', 0x2EDE: '鱼', 0x2EDF: '鸟',
    0x2EE0: '卤', 0x2EE3: '齿', 0x2EE4: '龙', 0x2EE5: '龟',
}

_ASCII_TO_FULLWIDTH = {
    ',': '，', '!': '！', '?': '？', ':': '：',
    ';': '；', '(': '（', ')': '）',
}


def _normalize_text_for_tts(text: str) -> str:
    """规范化文本用于 TTS 合成。

    处理三类问题：
    1. Kangxi Radicals (U+2F00-U+2FDF) - NFKC 可直接修复
    2. CJK Radicals Supplement (U+2E80-U+2EFF) - NFKC 无法修复，需手动映射
    3. 全角标点被 NFKC 转为 ASCII - 需回转为全角
    """
    # 第一步：手动替换 CJK Radicals Supplement 中 NFKC 无法处理的字符
    chars = []
    for ch in text:
        cp = ord(ch)
        if cp in _CJK_RADICALS_SUPPLEMENT_MAP:
            chars.append(_CJK_RADICALS_SUPPLEMENT_MAP[cp])
        elif 0x2E80 <= cp <= 0x2EFF:
            chars.append('')
        else:
            chars.append(ch)
    text = ''.join(chars)

    # 第二步：NFKC 规范化（处理 Kangxi Radicals 等）
    text = unicodedata.normalize('NFKC', text)

    # 第三步：把被 NFKC 误转的 ASCII 标点恢复为中文全角
    result = []
    for ch in text:
        result.append(_ASCII_TO_FULLWIDTH.get(ch, ch))
    return ''.join(result)


def _get_extension(format_str: str) -> str:
    """从格式字符串提取文件扩展名"""
    for prefix in ("mp3", "wav", "pcm", "ogg"):
        if format_str.lower().startswith(prefix):
            return prefix
    return "mp3"


def _resolve_audio_format(format_str: str):
    """将格式字符串转为 SDK AudioFormat 枚举"""
    from dashscope.audio.tts_v2 import AudioFormat
    name = format_str.upper().replace("HZ", "HZ").replace("MONO", "MONO")
    fmt = getattr(AudioFormat, name, None)
    if fmt:
        return fmt
    for attr_name in dir(AudioFormat):
        if attr_name.upper() == format_str.upper().replace("-", "_"):
            return getattr(AudioFormat, attr_name)
    return AudioFormat.MP3_22050HZ_MONO_256KBPS


_SYSTEM_INSTRUCT_PATTERN = re.compile(
    r'^你说话的情感是\w+。$'
    r'|^你正在进行.+，你说话的情感是\w+。$'
    r'|^你说话的角色是.+，你说话的情感是\w+。$'
    r'|^你现在说话的角色是.+，你说话的情感是\w+。$'
    r'|^你正在以一个.+的身份说话，你说话的情感是\w+。$'
)


def _validate_instruction(instruction: str, voice: str) -> Optional[str]:
    """校验 instruction 格式。

    系统音色必须使用固定格式，不符合时丢弃并记录 warning。
    复刻/设计音色（voice ID 含 prefix 段较长）允许任意文本。
    """
    instruction = instruction.strip()
    if not instruction:
        return None

    is_likely_custom_voice = (
        voice.startswith("cosyvoice-") and voice.count("-") >= 3
    )
    if is_likely_custom_voice:
        return instruction

    if _SYSTEM_INSTRUCT_PATTERN.match(instruction):
        return instruction

    logger.warning(
        f"[CosyVoice TTS] instruction 格式不合规，已跳过: "
        f"voice={voice}, instruction={instruction!r}"
    )
    return None


class CosyVoiceTTSService:
    """CosyVoice 文本转语音服务"""

    MODEL = "cosyvoice-v3-flash"

    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = config.base_url
        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

    def synthesize(
        self,
        text: str,
        voice: str,
        format: str = "mp3_22050hz_mono_256kbps",
        volume: int = 50,
        speech_rate: float = 1.0,
        pitch_rate: float = 1.0,
        seed: Optional[int] = None,
        language_hints: Optional[str] = None,
        instruction: Optional[str] = None,
        enable_ssml: bool = False,
    ) -> Tuple[bytes, str]:
        """
        同步合成语音。在异步环境中请通过 asyncio.to_thread() 调用。

        Returns:
            (audio_bytes, request_id)
        """
        config = get_config()
        dashscope.api_key = config.dashscope_api_key
        dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

        audio_format = _resolve_audio_format(format)

        kwargs = {
            "model": self.MODEL,
            "voice": voice,
            "format": audio_format,
            "volume": volume,
            "speech_rate": speech_rate,
            "pitch_rate": pitch_rate,
        }

        additional_params = {}
        if enable_ssml:
            additional_params["enable_ssml"] = True

        if seed is not None:
            kwargs["seed"] = seed
        if language_hints:
            kwargs["language_hints"] = [language_hints]
        if instruction:
            instruction = _validate_instruction(instruction, voice)
        if instruction:
            kwargs["instruction"] = instruction
        if additional_params:
            kwargs["additional_params"] = additional_params

        text = _normalize_text_for_tts(text)

        logger.info(f"[CosyVoice TTS] 开始合成: voice={voice}, model={self.MODEL}, "
                     f"format={format}, text_len={len(text)}, instruction={kwargs.get('instruction', None)!r}")

        synthesizer = SpeechSynthesizer(**kwargs)
        audio_data = synthesizer.call(text)
        request_id = synthesizer.get_last_request_id() or ""

        if not audio_data:
            error_detail = ""
            try:
                resp = synthesizer.get_response()
                if resp:
                    header = resp if isinstance(resp, dict) else {}
                    error_detail = header.get("error_message", "") or header.get("header", {}).get("error_message", "")
            except Exception:
                pass
            raise RuntimeError(
                f"语音合成失败: {error_detail or '未返回音频数据'} (request_id={request_id})"
            )

        logger.info(f"[CosyVoice TTS] 合成完成: {len(audio_data)} bytes, request_id={request_id}")
        return audio_data, request_id
