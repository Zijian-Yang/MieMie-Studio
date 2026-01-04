# 数据模型

## 概述

所有数据模型使用 Pydantic v2 定义，存储为 JSON 文件。

## 核心模型

### User（用户）

```python
class User(BaseModel):
    id: str                      # UUID
    username: str                # 用户名（唯一）
    password: str                # 密码（明文存储）
    display_name: Optional[str]  # 显示名称
    created_at: datetime
    last_login: Optional[datetime]
```

存储位置：`data/users.json`

### Project（项目）

```python
class Project(BaseModel):
    id: str                      # UUID
    name: str                    # 项目名称
    description: str = ""        # 描述
    script_content: str = ""     # 分镜脚本内容
    shots: List[Shot] = []       # 分镜列表
    created_at: datetime
    updated_at: datetime
    
class Shot(BaseModel):
    id: str                      # 分镜 ID
    shot_number: int             # 分镜编号
    shot_design: str = ""        # 镜头设计
    scene_type: str = ""         # 景别
    voice_subject: str = ""      # 配音主体
    dialogue: str = ""           # 视频台词
    characters: List[str] = []   # 出镜角色
    character_appearance: str = "" # 角色造型
    character_action: str = ""   # 角色动作
    scene_setting: str = ""      # 场景设置
    lighting: str = ""           # 光线设计
    mood: str = ""               # 情绪基调
    composition: str = ""        # 构图
    props: List[str] = []        # 道具
    sound_effects: str = ""      # 音效
    duration: str = ""           # 视频时长
```

存储位置：`data/users/{user_id}/projects/{id}.json`

### Character（角色）

```python
class Character(BaseModel):
    id: str
    project_id: str              # 所属项目
    name: str                    # 角色名称
    description: str = ""        # 描述
    appearance: str = ""         # 外貌特征
    personality: str = ""        # 性格特点
    
    # 生成的图片（三视图，每组3张，共3组）
    image_groups: List[CharacterImageGroup] = []
    selected_group_index: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

class CharacterImageGroup(BaseModel):
    urls: List[str]              # 图片 URL 列表
    is_selected: bool = False    # 是否选中
```

存储位置：`data/users/{user_id}/characters/{id}.json`

### Scene（场景）

```python
class Scene(BaseModel):
    id: str
    project_id: str
    name: str                    # 场景名称
    description: str = ""        # 描述
    environment: str = ""        # 环境特征
    lighting: str = ""           # 光线
    mood: str = ""               # 氛围
    
    image_groups: List[SceneImageGroup] = []
    selected_group_index: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime
```

### Prop（道具）

```python
class Prop(BaseModel):
    id: str
    project_id: str
    name: str                    # 道具名称
    description: str = ""        # 描述
    material: str = ""           # 材质
    color: str = ""              # 颜色
    
    image_groups: List[PropImageGroup] = []
    selected_group_index: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime
```

### Frame（分镜首帧）

```python
class Frame(BaseModel):
    id: str
    project_id: str
    shot_id: str                 # 关联的分镜 ID
    shot_number: int             # 分镜编号
    prompt: str = ""             # 生成提示词
    
    image_groups: List[FrameImageGroup] = []
    selected_group_index: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime
```

### Video（视频）

```python
class Video(BaseModel):
    id: str
    project_id: str
    shot_id: str                 # 关联的分镜 ID
    shot_number: int
    frame_id: Optional[str]      # 关联的首帧 ID
    
    prompt: str = ""             # 视频提示词
    model: str                   # 使用的模型
    resolution: str              # 分辨率
    duration: int                # 时长（秒）
    
    task: Optional[VideoTask]    # API 任务信息
    video_groups: List[VideoGroup] = []
    selected_group_index: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime

class VideoTask(BaseModel):
    task_id: str                 # DashScope 任务 ID
    status: str                  # pending | processing | succeeded | failed
    video_url: Optional[str]     # 生成的视频 URL
    error_message: Optional[str]
```

### StudioTask（图片工作室任务）

```python
class StudioTask(BaseModel):
    id: str
    project_id: str
    name: str                    # 任务名称
    description: str = ""
    
    # 生成配置
    model: str                   # 模型
    prompt: str = ""
    negative_prompt: str = ""
    n: int = 4                   # 每次生成数量
    group_count: int = 3         # 并发组数
    size: str = "1280*1280"      # 输出尺寸
    prompt_extend: bool = True
    watermark: bool = False
    seed: Optional[int] = None
    
    # wan2.6-image 特有参数
    enable_interleave: bool = False  # 图文混合模式
    max_images: int = 5              # 图文混合最大图数
    
    # 参考图/素材
    references: List[TaskReference] = []
    
    # 生成结果
    generated_images: List[GeneratedImage] = []
    status: str = "pending"      # pending | generating | completed | failed
    
    created_at: datetime
    updated_at: datetime
```

### VideoStudioTask（视频工作室任务）

```python
class VideoStudioTask(BaseModel):
    id: str
    project_id: str
    name: str
    
    # 任务类型
    task_type: str = "image_to_video"  # image_to_video | reference_to_video
    
    # 图生视频参数
    first_frame_url: Optional[str]     # 首帧图
    audio_url: Optional[str]           # 自定义音频
    
    # 视频生视频参数
    reference_video_urls: List[str] = []  # 参考视频（最多3个）
    
    # 通用参数
    prompt: str = ""
    negative_prompt: str = ""
    model: str
    duration: int = 5
    watermark: bool = False
    seed: Optional[int] = None
    shot_type: Optional[str] = None    # single | multi
    auto_audio: bool = True
    
    # 图生视频专用
    resolution: str = "1080P"
    prompt_extend: bool = True
    
    # 视频生视频专用
    size: str = "1920*1080"
    r2v_prompt_extend: bool = True
    
    # 任务状态
    group_count: int = 1
    task_ids: List[str] = []           # API 任务 ID 列表
    video_urls: List[str] = []         # 生成的视频 URL
    status: str = "pending"
    error_message: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
```

### GalleryImage（图库图片）

```python
class GalleryImage(BaseModel):
    id: str
    project_id: str
    name: str = ""
    description: str = ""
    url: str                     # 图片 URL
    thumbnail_url: Optional[str] # 缩略图 URL
    source: str = "upload"       # upload | generate | import
    tags: List[str] = []
    width: Optional[int]
    height: Optional[int]
    
    created_at: datetime
    updated_at: datetime
```

### 媒体库模型

```python
class AudioItem(BaseModel):
    id: str
    project_id: str
    name: str
    description: str = ""
    url: str
    file_type: str = ""          # mp3 | wav | ...
    file_size: int = 0
    duration: Optional[float]    # 时长（秒）
    
    created_at: datetime
    updated_at: datetime

class VideoItem(BaseModel):
    id: str
    project_id: str
    name: str
    description: str = ""
    url: str
    file_type: str = ""
    file_size: int = 0
    duration: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    thumbnail_url: Optional[str]
    
    created_at: datetime
    updated_at: datetime

class TextItem(BaseModel):
    id: str
    project_id: str
    name: str
    description: str = ""
    content: str = ""
    category: str = ""           # prompt | script | ...
    
    created_at: datetime
    updated_at: datetime
```

## 配置模型

```python
class AppConfig(BaseModel):
    # API 配置
    dashscope_api_key: str = ""
    api_region: str = "beijing"
    
    # LLM 配置
    llm: LLMConfig
    
    # 图像生成配置
    image: ImageConfig
    image_edit: ImageEditConfig
    
    # 视频生成配置
    video: VideoConfig
    ref_video: RefVideoConfig
    
    # OSS 配置
    oss: OSSConfig
```

## 数据迁移

### 添加新字段

Pydantic 模型支持默认值，新字段会自动使用默认值：

```python
class Model(BaseModel):
    existing_field: str
    new_field: str = "default"  # 旧数据加载时自动使用默认值
```

### 重命名字段

使用别名保持向后兼容：

```python
from pydantic import Field

class Model(BaseModel):
    new_name: str = Field(..., alias="old_name")
    
    class Config:
        populate_by_name = True  # 允许同时使用新名和别名
```

---

*最后更新: 2025-12-30*

