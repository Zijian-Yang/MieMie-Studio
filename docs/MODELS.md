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
    images: List[StudioTaskImage] = []  # 每张图含 markers: List[str]
    status: str = "pending"      # pending | generating | completed | failed
    error_message: Optional[str] = None
    request_ids: List[str] = []  # 所有并发组的 request_id

    created_at: datetime
    updated_at: datetime

class StudioTaskImage(BaseModel):
    id: str
    group_index: int = 0
    url: Optional[str] = None
    prompt_used: Optional[str] = None
    is_selected: bool = False
    markers: List[str] = []      # 用户标记: star, flag, check, cross
    created_at: datetime
```

### ImageBenchmarkDataset / Suite / Run（图片测评）

```python
class ImageBenchmarkDataset(BaseModel):
    id: str
    project_id: str
    name: str
    description: str = ""
    task_kind: Literal["text_to_image", "image_edit"]
    schema_version: str = "2.0"
    max_image_slot_index: int = 0
    items: List[ImageBenchmarkDatasetItem] = []
    created_at: datetime
    updated_at: datetime

class ImageBenchmarkDatasetItem(BaseModel):
    id: str
    name: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    sort_order: int = 0
    tags: List[str] = []
    image_slots: List[ImageBenchmarkImageSlot] = []

class ImageBenchmarkImageSlot(BaseModel):
    position: int                 # 图1 / 图2 / 图N 的顺序语义
    image: ImageBenchmarkDatasetImage

class ImageBenchmarkSuite(BaseModel):
    id: str
    project_id: str
    dataset_id: str
    task_kind: Literal["text_to_image", "image_edit"]
    selected_models: List[str] = []
    baseline_params: Dict[str, Any] = {}
    model_overrides: Dict[str, Dict[str, Any]] = {}
    latest_run_id: Optional[str] = None

class ImageBenchmarkRun(BaseModel):
    id: str
    suite_id: str
    project_id: str
    dataset_id: str
    dataset_snapshot: Dict[str, Any] = {}
    model_snapshots: List[Dict[str, Any]] = []
    cell_results: List[ImageBenchmarkCellResult] = []
    stats: Dict[str, Any] = {}

class ImageBenchmarkCellResult(BaseModel):
    case_id: str
    model_id: str
    status: Literal["pending", "running", "completed", "failed", "skipped", "unsupported"]
    output_images: List[ImageBenchmarkOutputImage] = []
    error_message: Optional[str] = None
    request_ids: List[str] = []
    task_ids: List[str] = []
    canonical_request: Optional[Dict[str, Any]] = None
    provider_payload: Optional[Dict[str, Any]] = None
    provider_result_meta: Dict[str, Any] = {}
    attempt_count: int = 1
    auto_retry_count: int = 0
```

存储位置：
- `data/users/{user_id}/image_benchmark_datasets/{id}.json`
- `data/users/{user_id}/image_benchmark_suites/{id}.json`
- `data/users/{user_id}/image_benchmark_runs/{id}.json`

说明：
- `image_slots` 替代旧版 `input_images`，用 `position` 保证图片顺序语义稳定。
- 数据集导入时可启用图片转存到当前 OSS，但数据模型仍只保存 URL，不保存图片二进制。
- `unsupported` 代表前置校验未通过，常见于模型不支持、输入图无法读取或暂时下载失败。
- 自动重试时最终 `cell_results` 会累计所有尝试产生的 `task_ids` 和 `request_ids`。

### VideoStudioTask（视频工作室任务）

```python
class VideoStudioTask(BaseModel):
    id: str
    project_id: str
    name: str

    # 任务类型
    task_type: str = "image_to_video"
    # image_to_video | reference_to_video | text_to_video | keyframe_to_video | video_repainting | video_edit

    # 图生视频参数
    first_frame_url: Optional[str]     # 首帧图
    last_frame_url: Optional[str]      # 尾帧图（首尾帧生视频）
    audio_url: Optional[str]           # 自定义音频

    # 参考生视频参数
    reference_video_urls: List[str] = []  # 参考素材（视频最多3个/图片最多5张）

    # VACE 视频编辑参数
    source_video_url: Optional[str]       # 输入视频 URL（视频重绘/局部编辑）
    source_video_preview_url: Optional[str]  # 源视频首帧预览图 URL
    reference_image_url: Optional[str]    # 单张参考图 URL
    mask_image_url: Optional[str]         # 局部编辑 Mask 图 URL（OSS）
    mask_frame_id: Optional[int]          # 当前固定为 1（首帧）
    control_condition: Optional[str]      # posebodyface | posebody | depth | scribble
    strength: Optional[float]             # 视频重绘控制强度 [0, 1]
    mask_type: Optional[str]              # tracking | fixed
    expand_ratio: Optional[float]         # tracking 模式下有效 [0, 1]
    expand_mode: Optional[str]            # hull | bbox | original

    # 通用参数
    prompt: str = ""
    negative_prompt: str = ""
    model: str
    duration: int = 5
    watermark: bool = False
    seed: Optional[int] = None
    shot_type: Optional[str] = None    # single | multi
    auto_audio: bool = True            # 有声/无声切换（仅支持 audio_toggle 的模型）

    # 图生视频专用
    resolution: str = "1080P"
    prompt_extend: bool = True

    # 文生视频专用
    size: str = "1920*1080"            # 视频分辨率（宽*高）
    t2v_prompt_extend: bool = True     # 文生视频智能改写

    # 参考生视频专用
    r2v_prompt_extend: bool = True

    # 任务状态
    group_count: int = 1
    task_ids: List[str] = []           # API 任务 ID 列表
    request_ids: List[str] = []        # 各组的请求 ID
    video_urls: List[str] = []         # 生成的视频 URL
    selected_video_url: Optional[str] = None
    video_markers: dict = {}           # 视频标记 {video_url: [marker_type, ...]}, marker: star/flag/check/cross
    status: str = "pending"
    error_message: Optional[str] = None

    created_at: datetime
    updated_at: datetime
```

补充说明：
- `video_repainting` 与 `video_edit` 固定使用 `wanx2.1-vace-plus`
- `video_edit` 当前只支持 `mask_image_url`，不支持 `mask_video_url`
- 局部编辑的 Mask 由前端首帧编辑器生成，服务端会二值化后上传 OSS
- `source_video_preview_url` 用于任务卡片和详情页展示首帧缩略图

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

### AudioStudioTask（音频工作室任务）

```python
class AudioStudioTask(BaseModel):
    id: str
    project_id: str
    task_type: str = "tts"       # tts | voice_clone | voice_design
    name: str = ""

    # TTS 参数
    text: str = ""
    voice: str = ""
    format: str = "mp3_22050hz_mono_256kbps"
    volume: int = 50
    speech_rate: float = 1.0
    pitch_rate: float = 1.0
    seed: Optional[int] = None
    instruction: Optional[str] = None

    # 结果
    result_audio_url: Optional[str] = None
    result_voice_id: Optional[str] = None
    audio_duration: Optional[float] = None
    saved_to_library: bool = False
    markers: List[str] = []      # 用户标记: star, flag, check, cross

    # 状态
    status: str = "pending"      # pending | processing | succeeded | failed
    error_message: Optional[str] = None
    request_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime
```

---

## 数据迁移

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

*最后更新: 2026-02-06*
