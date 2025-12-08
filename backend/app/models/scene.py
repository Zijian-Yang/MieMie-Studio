"""
场景数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class SceneImage(BaseModel):
    """场景图片"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引
    url: Optional[str] = None  # 图片 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    created_at: datetime = Field(default_factory=datetime.now)


class Scene(BaseModel):
    """场景"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str  # 场景名称
    description: str = ""  # 场景描述（用于说明，不参与生图）
    
    # 提示词
    common_prompt: str = "空镜头场景，无人物，无道具，环境概念设计，高清画质，电影感，专业摄影，宽屏构图"  # 通用提示词
    scene_prompt: str = ""  # 场景特定提示词（AI生成，用于生图）
    negative_prompt: str = "人物, 角色, 道具, 物品, 动物, 文字, 水印, 模糊, 低质量, UI元素"  # 负向提示词
    
    # 图片
    image_groups: List[SceneImage] = []  # 场景图片组
    selected_group_index: int = 0  # 选中的组索引
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def thumbnail_url(self) -> Optional[str]:
        """获取缩略图URL"""
        if self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index].url
        return None

