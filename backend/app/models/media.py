"""
媒体库模型（音频库、视频库、文本库）
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
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
    
    支持六种任务类型：
    1. 图生视频（image_to_video）：使用 first_frame_url
    2. 参考生视频（reference_to_video）：使用 reference_video_urls（支持视频+图片）
    3. 文生视频（text_to_video）：纯文本生成视频
    4. 首尾帧生视频（keyframe_to_video）：使用 first_frame_url 和 last_frame_url
    5. 视频重绘（video_repainting）：使用 source_video_url，可选 reference_image_url
    6. 局部编辑（video_edit）：使用 source_video_url + mask_image_url，可选 reference_image_url
    7. 视频续写（video_extension）：使用 first_clip_url，可选 last_frame_url
    
    图生视频参数说明（根据官方文档）：
    - resolution: 分辨率档位，wan2.5/2.6 支持 480P/720P/1080P（默认1080P）
    - duration: 视频时长，wan2.6 支持 5/10/15 秒，wan2.5 支持 5/10 秒，wanx2.1 支持 3/4/5 秒
    - prompt_extend: 智能改写，默认 True
    - watermark: 水印标识（右下角"AI生成"），默认 False
    - auto_audio: 自动配音（仅 wan2.5/2.6 支持），默认 True
    - audio_url: 自定义音频URL（传入时 audio 参数无效）
    - seed: 随机种子，范围 [0, 2147483647]
    - shot_type: 镜头类型（仅 wan2.6 支持），single/multi
    
    参考生视频参数说明（wan2.6-r2v）：
    - size: 分辨率（宽*高格式，如 1920*1080），默认1080P 16:9
    - duration: 视频时长，2-10秒整数
    - shot_type: 镜头类型，single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    
    文生视频参数说明（wan2.6-t2v）：
    - size: 分辨率（宽*高格式，如 1920*1080），720P/1080P档位
    - duration: 视频时长，wan2.6支持5/10/15秒，wan2.5支持5/10秒，其他固定5秒
    - t2v_prompt_extend: 智能改写，默认 True
    - shot_type: 镜头类型（仅wan2.6支持），single/multi
    - watermark: 是否添加水印
    - seed: 随机种子
    - auto_audio: 是否自动配音（仅wan2.5及以上支持），默认True
    - audio_url: 自定义音频URL
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str = ""  # 任务名称
    
    # 兼容旧任务类型: image_to_video / reference_to_video / text_to_video / keyframe_to_video / video_repainting / video_edit
    task_type: str = "image_to_video"
    task_kind: str = "image_to_video"
    provider: str = "wan"
    key_profile: Optional[str] = None
    model_id: Optional[str] = None
    narrative_mode: str = "single"

    # 新架构的规范化输入与参数
    input_assets: Dict[str, Any] = {}
    normalized_params: Dict[str, Any] = {}
    provider_payload_snapshot: Optional[Dict[str, Any]] = None
    provider_result_meta: Dict[str, Any] = {}
    
    # 生成模式（图生视频使用）
    mode: str = "first_frame"  # first_frame: 首帧生视频, first_last_frame: 首尾帧生视频
    
    # 输入参数 - 图生视频
    first_frame_url: Optional[str] = None  # 首帧图URL（从图库选择）
    last_frame_url: Optional[str] = None  # 尾帧图URL（首尾帧模式）
    first_clip_url: Optional[str] = None  # 首段视频URL（视频续写）
    
    # 输入参数 - 参考生视频
    reference_video_urls: List[str] = []  # 参考素材URL列表（视频+图片，总数≤5）

    # 输入参数 - VACE 视频编辑
    source_video_url: Optional[str] = None  # 源视频URL（从视频库选择）
    source_video_preview_url: Optional[str] = None  # 源视频首帧预览图URL
    reference_image_url: Optional[str] = None  # 单张参考图URL（从图库选择）
    mask_image_url: Optional[str] = None  # 局部编辑mask图URL
    mask_frame_id: Optional[int] = None  # mask对应帧ID，当前固定为1
    
    # 通用输入参数
    audio_url: Optional[str] = None  # 自定义音频URL
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
    
    # 生成参数 - 参考生视频专用
    size: str = "1920*1080"  # 分辨率（宽*高格式）
    ratio: Optional[str] = None  # 画面比例
    audio_setting: Optional[str] = None  # 视频声音设置

    # 生成参数 - 文生视频专用
    t2v_prompt_extend: bool = True  # 文生视频的智能改写，默认开启

    # 生成参数 - VACE 专用
    control_condition: Optional[str] = None  # 视频特征提取方式
    strength: Optional[float] = None  # 视频重绘控制强度
    mask_type: Optional[str] = None  # 局部编辑mask行为：tracking/fixed
    expand_ratio: Optional[float] = None  # tracking时的向外扩展比例
    expand_mode: Optional[str] = None  # tracking时的包裹模式：hull/bbox/original
    
    # 生成结果
    group_count: int = 1  # 生成组数
    video_urls: List[str] = []  # 生成的视频URL列表
    selected_video_url: Optional[str] = None  # 选中的视频URL
    thumbnail_url: Optional[str] = None  # 任务封面缩略图URL
    video_markers: dict = {}  # 视频标记 {video_url: [marker_type, ...]}, marker: star/flag/check/cross
    
    # 任务状态
    task_ids: List[str] = []  # 各组的任务ID
    request_ids: List[str] = []  # 各组的请求ID（用于追踪）
    status: str = "pending"  # pending, processing, succeeded, failed
    error_message: Optional[str] = None
    submit_state: str = "idle"  # idle, submitting, submitted, failed
    submit_started_at: Optional[datetime] = None  # 当前提交尝试开始时间
    submit_attempt_id: Optional[str] = None  # 当前提交尝试ID，用于丢弃迟到后台结果
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
