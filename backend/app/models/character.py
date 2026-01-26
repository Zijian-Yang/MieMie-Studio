"""
角色数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class CharacterImage(BaseModel):
    """角色图片（三视图）"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_index: int = 0  # 组索引（0-2，共3组）
    front_url: Optional[str] = None  # 正面图 URL
    side_url: Optional[str] = None  # 侧面图 URL
    back_url: Optional[str] = None  # 背面图 URL
    prompt_used: Optional[str] = None  # 生成时使用的提示词
    created_at: datetime = Field(default_factory=datetime.now)


class VoiceConfig(BaseModel):
    """角色音色配置"""
    voice_id: Optional[str] = None  # 预设音色ID
    custom_audio_url: Optional[str] = None  # 自定义克隆音频 URL
    test_text: str = "你好，我是这个角色的配音。"  # 测试文本


class Character(BaseModel):
    """角色"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str  # 所属项目ID
    name: str  # 角色名称
    description: str = ""  # 角色描述
    appearance: str = ""  # 外观描述（用于生成提示词）
    personality: str = ""  # 性格特点
    
    # 提示词
    common_prompt: str = "全身人物立绘，纯白色背景，T-pose或自然站立姿势，中性表情，简洁基础服装，高清细节，均匀柔和光线，角色设计参考图风格"  # 通用提示词
    character_prompt: str = ""  # 角色特定提示词（AI生成）
    negative_prompt: str = "复杂背景, 道具, 武器, 复杂服饰, 夸张表情, 动态姿势, 文字, 水印, 模糊, 低质量, 阴影, 特效"  # 负向提示词（用于避免生成某些元素）
    
    # 图片
    image_groups: List[CharacterImage] = []  # 三视图组（最多3组）
    selected_group_index: int = 0  # 选中的组索引
    
    # 音色
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    
    # 最近一次生成的任务ID（用于追踪）
    last_task_id: Optional[str] = None  # DashScope 任务ID
    last_request_id: Optional[str] = None  # DashScope 请求ID
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def avatar_url(self) -> Optional[str]:
        """获取头像URL（选中组的正面图）"""
        if self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index].front_url
        return None
    
    @property
    def selected_images(self) -> Optional[CharacterImage]:
        """获取选中的三视图组"""
        if self.image_groups and self.selected_group_index < len(self.image_groups):
            return self.image_groups[self.selected_group_index]
        return None

