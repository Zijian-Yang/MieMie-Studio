"""
图片工作室数据模型
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class StudioTaskImage(BaseModel):
    """生成任务中的单张图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    storage_source: str = "remote"  # remote / oss / local_fallback / local_expired
    storage_warning: Optional[str] = None  # 存储告警信息
    retry_count: int = 0  # 本地回退后的自动/手动重传次数
    last_retry_error: Optional[str] = None  # 最近一次重传失败原因
    last_retry_at: Optional[datetime] = None  # 最近一次重传时间
    next_retry_at: Optional[datetime] = None  # 下次自动重传时间
    fallback_created_at: Optional[datetime] = None  # 本地回退文件生成时间
    prompt_used: Optional[str] = None  # 使用的提示词
    is_selected: bool = False  # 是否被选中保存到图库
    markers: List[str] = []  # 用户标记: star, flag, check, cross
    created_at: datetime = Field(default_factory=datetime.now)


class ReferenceItem(BaseModel):
    """参考素材项"""
    type: str  # character, scene, prop, gallery
    id: str  # 素材ID
    name: str = ""  # 素材名称（用于显示）
    url: Optional[str] = None  # 素材图片URL


class StudioTask(BaseModel):
    """图片工作室生成任务"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str = ""  # 任务名称
    description: str = ""  # 任务描述
    
    # 生成设置
    model: str = "wan2.5-i2i-preview"  # 使用的模型
    model_id: Optional[str] = None  # 规范化模型ID
    provider: str = "wan"  # 厂商分组
    task_kind: str = "image_edit"  # text_to_image / image_edit / interactive_edit / sequential_generation
    prompt: str = ""  # 生成提示词
    negative_prompt: str = ""  # 负向提示词
    n: int = 1  # 每次请求生成的图片数量
    group_count: int = 3  # 并发请求数（总图片数 = n * group_count）
    
    # 高级生成参数（持久化保存）
    size: Optional[str] = None  # 输出尺寸，如 "1280*1280"
    prompt_extend: bool = True  # 智能改写
    watermark: bool = False  # 水印
    seed: Optional[int] = None  # 随机种子
    
    # wan2.6-image 专用参数
    enable_interleave: bool = False  # 图文混合模式
    max_images: int = 5  # 图文混合模式下最大生成图数
    audio_url: Optional[str] = None  # 预留，便于与统一 schema 对齐

    # wan2.7-image / wan2.7-image-pro 专用参数
    enable_sequential: bool = False  # 组图模式
    thinking_mode: Optional[bool] = None  # 思考模式（仅纯文生图）
    bbox_list: List[List[List[int]]] = []  # 交互式编辑框选区域
    color_palette: List[Dict[str, str]] = []  # 色板 [{"hex": "#FFFFFF", "ratio": "25.00%"}]
    size_mode: Optional[str] = None  # preset / custom
    size_preset: Optional[str] = None  # 1K / 2K / 4K
    custom_width: Optional[int] = None
    custom_height: Optional[int] = None

    # 火山引擎 Seedream 专用参数
    output_format: Optional[str] = None  # jpeg / png（仅 5.0 lite）
    web_search: bool = False  # 联网搜索（仅 5.0 lite）
    
    # 参考素材
    references: List[ReferenceItem] = []  # 参考素材列表
    input_assets: Dict[str, Any] = {}
    normalized_params: Dict[str, Any] = {}

    # 生成结果
    images: List[StudioTaskImage] = []
    
    # 状态
    status: str = "pending"  # pending, generating, completed, failed
    error_message: Optional[str] = None
    warnings: List[str] = []  # 非阻塞告警，如 OSS 转存失败后回落本地

    # API 追踪ID
    last_task_id: Optional[str] = None  # DashScope 任务ID（兼容旧数据）
    last_request_id: Optional[str] = None  # DashScope 请求ID（兼容旧数据）
    task_ids: List[str] = []  # 所有外部任务 ID
    request_ids: List[str] = []  # 所有并发组的 request_id 列表
    provider_payload_snapshot: Optional[Dict[str, Any]] = None
    provider_result_meta: Dict[str, Any] = {}

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
