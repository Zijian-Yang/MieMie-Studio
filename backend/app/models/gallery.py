"""
图库数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class GalleryImage(BaseModel):
    """图库图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str = ""  # 图片名称
    description: str = ""  # 图片描述
    url: str  # 图片 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    source: str = "studio"  # 来源：studio（图片工作室）、upload（上传）
    task_id: Optional[str] = None  # 关联的生成任务ID
    tags: List[str] = []  # 标签
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

