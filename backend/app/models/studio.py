"""
图片工作室数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class StudioTaskImage(BaseModel):
    """生成任务中的单张图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    prompt_used: Optional[str] = None  # 使用的提示词
    is_selected: bool = False  # 是否被选中保存到图库
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
    
    # 参考素材
    references: List[ReferenceItem] = []  # 参考素材列表
    
    # 生成结果
    images: List[StudioTaskImage] = []
    
    # 状态
    status: str = "pending"  # pending, generating, completed, failed
    error_message: Optional[str] = None
    
    # 最近一次生成的任务ID（用于追踪）
    last_task_id: Optional[str] = None  # DashScope 任务ID
    last_request_id: Optional[str] = None  # DashScope 请求ID
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

