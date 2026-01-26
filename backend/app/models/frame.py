"""
分镜首帧数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class FrameImage(BaseModel):
    """首帧图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    created_at: datetime = Field(default_factory=datetime.now)


class Frame(BaseModel):
    """分镜首帧"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    shot_id: str  # 关联的分镜ID
    shot_number: int = 0  # 镜头序号
    
    # 提示词
    prompt: str = ""  # 生成首帧的完整提示词
    
    # 图片
    image_groups: List[FrameImage] = []  # 首帧图片组（最多3组）
    selected_group_index: int = 0  # 选中的组索引
    
    # 最近一次生成的任务ID（用于追踪）
    last_task_id: Optional[str] = None  # DashScope 任务ID
    last_request_id: Optional[str] = None  # DashScope 请求ID
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def selected_url(self) -> Optional[str]:
        """获取选中的首帧URL"""
        if self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index].url
        return None

