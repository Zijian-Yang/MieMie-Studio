"""
基础数据模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid.uuid4())[:8]


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ============== 设置相关 ==============

class SettingsUpdate(BaseModel):
    """设置更新请求"""
    dashscope_api_key: Optional[str] = None


class SettingsResponse(BaseModel):
    """设置响应"""
    dashscope_api_key: str = ""
    has_api_key: bool = False


# ============== 分镜脚本相关 ==============

class ScriptScene(BaseModel):
    """分镜场景"""
    id: str = Field(default_factory=generate_id)
    scene_number: int = 0
    shot_design: str = ""  # 镜头设计
    shot_type: str = ""  # 景别
    voice_subject: str = ""  # 配音主体
    dialogue: str = ""  # 视频台词
    characters: List[str] = []  # 出镜角色
    character_appearance: str = ""  # 角色造型
    character_action: str = ""  # 角色动作
    scene_setting: str = ""  # 场景设置
    lighting: str = ""  # 光线设计
    mood: str = ""  # 情绪基调
    composition: str = ""  # 构图
    props: List[str] = []  # 道具
    sound_effects: str = ""  # 音效
    duration: float = 2.0  # 视频时长（秒）
    
    # 生成内容
    first_frame_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None


class Script(BaseModel):
    """剧本/分镜脚本"""
    id: str = Field(default_factory=generate_id)
    project_id: str = ""
    title: str = ""
    original_content: str = ""  # 原始剧本内容
    processed_content: str = ""  # AI 处理后的内容
    scenes: List[ScriptScene] = []  # 分镜列表
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ScriptGenerateRequest(BaseModel):
    """剧本生成请求"""
    content: str
    model: str = "qwen3-max"
    prompt: Optional[str] = None  # 自定义提示词


class ScriptSaveRequest(BaseModel):
    """剧本保存请求"""
    project_id: str
    content: str
    scenes: List[ScriptScene] = []


# ============== 角色相关 ==============

class CharacterImageSet(BaseModel):
    """角色图片组（三视图）"""
    id: str = Field(default_factory=generate_id)
    front_url: Optional[str] = None  # 正面
    side_url: Optional[str] = None  # 侧面
    back_url: Optional[str] = None  # 背面
    selected: bool = False


class Character(BaseModel):
    """角色"""
    id: str = Field(default_factory=generate_id)
    project_id: str = ""
    name: str = ""
    description: str = ""  # 角色描述
    appearance: str = ""  # 外貌特征
    prompt: str = ""  # 生图提示词
    image_sets: List[CharacterImageSet] = []  # 三组三视图
    selected_set_id: Optional[str] = None  # 选中的图片组ID
    
    # 音色设置（预留）
    voice_id: Optional[str] = None
    voice_sample_url: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class CharacterExtractRequest(BaseModel):
    """角色提取请求"""
    project_id: str
    script_content: str


class CharacterGenerateRequest(BaseModel):
    """角色图片生成请求"""
    character_id: str
    set_index: int = 0  # 生成第几组（0, 1, 2）
    common_prompt: Optional[str] = None  # 通用提示词
    character_prompt: Optional[str] = None  # 角色提示词


class CharacterUpdateRequest(BaseModel):
    """角色更新请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    prompt: Optional[str] = None
    selected_set_id: Optional[str] = None
    voice_id: Optional[str] = None


# ============== 场景相关 ==============

class SceneImage(BaseModel):
    """场景图片"""
    id: str = Field(default_factory=generate_id)
    url: Optional[str] = None
    selected: bool = False


class Scene(BaseModel):
    """场景"""
    id: str = Field(default_factory=generate_id)
    project_id: str = ""
    name: str = ""
    description: str = ""
    prompt: str = ""  # 生图提示词
    images: List[SceneImage] = []  # 多个版本
    selected_image_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SceneExtractRequest(BaseModel):
    """场景提取请求"""
    project_id: str
    script_content: str


class SceneGenerateRequest(BaseModel):
    """场景图片生成请求"""
    scene_id: str
    prompt: Optional[str] = None


# ============== 道具相关 ==============

class PropImage(BaseModel):
    """道具图片"""
    id: str = Field(default_factory=generate_id)
    url: Optional[str] = None
    selected: bool = False


class Prop(BaseModel):
    """道具"""
    id: str = Field(default_factory=generate_id)
    project_id: str = ""
    name: str = ""
    description: str = ""
    prompt: str = ""
    images: List[PropImage] = []
    selected_image_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PropExtractRequest(BaseModel):
    """道具提取请求"""
    project_id: str
    script_content: str


class PropGenerateRequest(BaseModel):
    """道具图片生成请求"""
    prop_id: str
    prompt: Optional[str] = None


# ============== 分镜首帧相关 ==============

class FrameGenerateRequest(BaseModel):
    """分镜首帧生成请求"""
    project_id: str
    scene_id: str  # 分镜场景ID
    prompt: Optional[str] = None


# ============== 视频生成相关 ==============

class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    project_id: str
    scene_id: str  # 分镜场景ID
    first_frame_url: str
    prompt: Optional[str] = None
    duration: float = 2.0


class VideoStatusResponse(BaseModel):
    """视频生成状态响应"""
    task_id: str
    status: TaskStatus
    video_url: Optional[str] = None
    error_message: Optional[str] = None


# ============== 项目相关 ==============

class Project(BaseModel):
    """项目"""
    id: str = Field(default_factory=generate_id)
    name: str = ""
    description: str = ""
    script: Optional[Script] = None
    characters: List[Character] = []
    scenes: List[Scene] = []
    props: List[Prop] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProjectCreateRequest(BaseModel):
    """项目创建请求"""
    name: str
    description: str = ""


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    projects: List[Project]
    total: int

