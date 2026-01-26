"""
道具数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class PropImage(BaseModel):
    """道具图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    created_at: datetime = Field(default_factory=datetime.now)


class Prop(BaseModel):
    """道具"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str  # 道具名称
    description: str = ""  # 道具描述（用于说明，不参与生图）
    
    # 提示词
    common_prompt: str = "单一物品特写，纯白色背景，居中构图，高清细节，产品摄影风格，均匀柔和光线，无阴影"  # 通用提示词
    prop_prompt: str = ""  # 道具特定提示词（AI生成，用于生图）
    negative_prompt: str = "人物, 角色, 手, 场景背景, 其他物品, 文字, 水印, 模糊, 低质量, 复杂背景, 阴影"  # 负向提示词
    
    # 图片
    image_groups: List[PropImage] = []  # 道具图片组
    selected_group_index: int = 0  # 选中的组索引
    
    # 最近一次生成的任务ID（用于追踪）
    last_task_id: Optional[str] = None  # DashScope 任务ID
    last_request_id: Optional[str] = None  # DashScope 请求ID
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def thumbnail_url(self) -> Optional[str]:
        """获取缩略图URL"""
        if self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index].url
        return None

