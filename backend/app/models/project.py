"""
项目和剧本数据模型
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class ProjectLLMConfig(BaseModel):
    """项目级别的 LLM 配置，仅对该项目生效"""
    model: str = ""  # 空字符串表示使用全局默认
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    enable_thinking: Optional[bool] = None
    thinking_budget: Optional[int] = None
    result_format: Optional[str] = None
    enable_search: Optional[bool] = None


class Shot(BaseModel):
    """分镜脚本单个镜头"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shot_number: int = 0  # 镜头序号
    shot_design: str = ""  # 镜头设计
    scene_type: str = ""  # 景别：远景、中景、近景、特写
    voice_subject: str = ""  # 配音主体
    dialogue: str = ""  # 视频台词
    characters: List[str] = []  # 出镜角色名称
    character_appearance: str = ""  # 角色造型
    character_action: str = ""  # 角色动作
    scene_setting: str = ""  # 场景设置
    lighting: str = ""  # 光线设计
    mood: str = ""  # 情绪基调
    composition: str = ""  # 构图
    props: List[str] = []  # 道具名称
    sound_effects: str = ""  # 音效
    duration: float = 5.0  # 视频时长（秒），不超过10秒
    
    # 关联的素材ID（用于首帧生成）
    character_ids: List[str] = []  # 关联的角色ID列表
    scene_id: Optional[str] = None  # 关联的场景ID
    prop_ids: List[str] = []  # 关联的道具ID列表
    
    # 生成的素材
    first_frame_url: Optional[str] = None  # 首帧图 URL
    video_url: Optional[str] = None  # 视频 URL（选中的最终视频）
    selected_video_id: Optional[str] = None  # 选中的候选视频ID
    video_prompt: Optional[str] = None  # 用户编辑的视频生成提示词
    audio_url: Optional[str] = None  # 配音 URL


class ScriptVersion(BaseModel):
    """剧本版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    content: str = ""  # 版本的剧本内容
    original_content: str = ""  # 原始内容
    model_used: Optional[str] = None
    prompt_used: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class PromptVersion(BaseModel):
    """提示词版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    prompt: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class Script(BaseModel):
    """剧本/分镜脚本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    original_content: str = ""  # 原始剧本内容
    processed_content: str = ""  # 处理后的内容（AI优化后）
    model_used: Optional[str] = None  # 使用的模型
    prompt_used: Optional[str] = None  # 使用的提示词
    custom_prompt: str = ""  # 自定义提示词
    shots: List[Shot] = []  # 分镜列表
    # 版本历史
    script_versions: List[ScriptVersion] = []
    prompt_versions: List[PromptVersion] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Project(BaseModel):
    """项目"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    script: Optional[Script] = None
    character_ids: List[str] = []  # 角色ID列表
    scene_ids: List[str] = []  # 场景ID列表
    prop_ids: List[str] = []  # 道具ID列表
    style_ids: List[str] = []  # 风格ID列表
    # 项目级别的模型配置，覆盖全局设置
    llm_configs: Dict[str, ProjectLLMConfig] = Field(default_factory=dict)  # key 为模型名称
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

