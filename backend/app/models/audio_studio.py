"""
音频工作室数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class AudioStudioTask(BaseModel):
    """音频工作室任务

    支持三种任务类型：
    1. tts - 文本转语音：使用 CosyVoice 模型将文本合成为语音
    2. voice_clone - 声音复刻：从音频样本提取音色特征，创建自定义音色
    3. voice_design - 声音设计：通过文本描述生成自定义音色
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str

    task_type: str = "tts"  # tts, voice_clone, voice_design
    name: str = ""

    # === TTS 参数 ===
    text: str = ""
    voice: str = ""  # 系统音色 ID 或自定义音色 ID
    format: str = "mp3_22050hz_mono_256kbps"
    volume: int = 50  # [0, 100]
    speech_rate: float = 1.0  # [0.5, 2.0]
    pitch_rate: float = 1.0  # [0.5, 2.0]
    seed: Optional[int] = None  # [0, 65535]
    language_hints: Optional[str] = None  # zh/en/fr/de/ja/ko/ru
    instruction: Optional[str] = None  # 情感/方言指令，最长 100 字符
    enable_ssml: bool = False

    # === 声音复刻参数 ===
    audio_url: Optional[str] = None  # 音频样本 URL（从音频库选择）
    prefix: str = ""  # 音色前缀，仅数字和小写字母，不超过 10 字符
    clone_language_hints: Optional[str] = None

    # === 声音设计参数 ===
    voice_prompt: Optional[str] = None  # 声音描述
    preview_text: Optional[str] = None  # 试听文本
    design_sample_rate: int = 24000  # 16000/24000/48000
    design_response_format: str = "wav"  # pcm/wav/mp3

    # === 结果 ===
    result_audio_url: Optional[str] = None  # TTS 结果音频 URL / 设计预览音频 URL
    result_voice_id: Optional[str] = None  # 复刻或设计产生的音色 ID
    audio_duration: Optional[float] = None  # 生成音频时长（秒）
    saved_to_library: bool = False  # 是否已保存到音频库
    markers: List[str] = []  # 用户标记: star, flag, check, cross

    # === 状态 ===
    status: str = "pending"  # pending, processing, succeeded, failed
    error_message: Optional[str] = None
    request_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VoiceProfile(BaseModel):
    """用户音色档案（复刻 / 设计产生的音色）"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    voice_id: str  # DashScope 返回的音色 ID
    name: str = ""
    source: str = "clone"  # clone / design
    target_model: str = "cosyvoice-v3-flash"
    prefix: str = ""
    status: str = "deploying"  # deploying, ok, undeployed

    # 声音设计专属
    voice_prompt: Optional[str] = None
    preview_text: Optional[str] = None
    preview_audio_url: Optional[str] = None

    # 声音复刻专属
    audio_url: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
