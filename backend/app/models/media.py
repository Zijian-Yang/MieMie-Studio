"""
媒体库模型（音频库、视频库、文本库）
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class MediaItem(BaseModel):
    """媒体项基类"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str  # 媒体名称
    description: str = ""  # 描述
    url: str  # 媒体URL（OSS）
    file_type: str = ""  # 文件类型 (mp3, wav, mp4, etc.)
    file_size: int = 0  # 文件大小（字节）
    duration: Optional[float] = None  # 时长（秒）
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AudioItem(MediaItem):
    """音频项"""
    sample_rate: Optional[int] = None  # 采样率
    channels: Optional[int] = None  # 声道数
    

class VideoItem(MediaItem):
    """视频项"""
    width: Optional[int] = None  # 视频宽度
    height: Optional[int] = None  # 视频高度
    fps: Optional[float] = None  # 帧率
    thumbnail_url: Optional[str] = None  # 缩略图URL


class TextItemVersion(BaseModel):
    """文本项版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str  # 文本内容
    created_at: datetime = Field(default_factory=datetime.now)
    description: str = ""  # 版本描述


class TextItem(BaseModel):
    """文本项"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str  # 文本名称
    content: str  # 当前文本内容
    category: str = ""  # 分类（如：提示词、脚本、描述等）
    versions: List[TextItemVersion] = []  # 版本历史
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VideoStudioTask(BaseModel):
    """视频工作室任务
    
    支持两种任务类型：
    1. 图生视频（image_to_video）：使用 first_frame_url
    2. 视频生视频（reference_to_video）：使用 reference_video_urls
    
    图生视频参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5/2.6 支持 480P/720P/1080P（默认1080P）
    - duration: 视频时长，wan2.6 支持 5/10/15 秒，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - auto_audio: 自动配音（仅 wan2.5/2.6 支持），默认 True
    - audio_url: 自定义音频URL（传入时 audio 参数无效）
    - seed: 随机种子，范围 [0, 2147483647]
    - shot_type: 镜头类型（仅 wan2.6 支持），single/multi
    
    视频生视频参数说明（wan2.6-r2v）：
    - size: 分辨率（宽*高格式，如 1920*1080）
    - duration: 视频时长，5 或 10 秒
    - shot_type: 镜头类型，single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    - audio: 是否生成音频
    - r2v_prompt_extend: 提示词改写，默认 True
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str = ""  # 任务名称
    
    # 任务类型
    task_type: str = "image_to_video"  # image_to_video: 图生视频, reference_to_video: 视频生视频
    
    # 生成模式（图生视频使用）
    mode: str = "first_frame"  # first_frame: 首帧生视频, first_last_frame: 首尾帧生视频
    
    # 输入参数 - 图生视频
    first_frame_url: Optional[str] = None  # 首帧图URL（从图库选择）
    last_frame_url: Optional[str] = None  # 尾帧图URL（首尾帧模式）
    
    # 输入参数 - 视频生视频
    reference_video_urls: List[str] = []  # 参考视频URL列表（最多3个）
    
    # 通用输入参数
    audio_url: Optional[str] = None  # 自定义音频URL（从音频库选择，仅图生视频支持）
    prompt: str = ""  # 提示词
    negative_prompt: str = ""  # 负面提示词
    
    # 生成参数 - 通用
    model: str = "wan2.5-i2v-preview"  # 使用的模型
    duration: int = 5  # 视频时长（秒）
    watermark: bool = False  # 水印
    seed: Optional[int] = None  # 随机种子
    shot_type: Optional[str] = None  # 镜头类型，single/multi
    auto_audio: bool = True  # 自动配音（默认开启）
    
    # 生成参数 - 图生视频专用
    resolution: str = "1080P"  # 分辨率档位（默认1080P）
    prompt_extend: bool = True  # 智能改写
    
    # 生成参数 - 视频生视频专用
    size: str = "1920*1080"  # 分辨率（宽*高格式）
    r2v_prompt_extend: bool = True  # 视频生视频的提示词改写，默认开启
    
    # 生成结果
    group_count: int = 1  # 生成组数
    video_urls: List[str] = []  # 生成的视频URL列表
    selected_video_url: Optional[str] = None  # 选中的视频URL
    
    # 任务状态
    task_ids: List[str] = []  # 各组的任务ID
    status: str = "pending"  # pending, processing, succeeded, failed
    error_message: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

