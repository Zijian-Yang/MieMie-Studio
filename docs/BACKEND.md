# 后端开发规范

> 2026-04 更新：`config.py` 现在是**配置与兼容层**，不是复杂工作室模型的唯一真相来源。
> 图片/视频工作室的主规范优先看 `models_registry/`、`video_capabilities.py`、`video_adapters.py` 与 `docs/STUDIO_MODEL_INTEGRATION_GUIDE.md`。

## 目录结构

```
backend/app/
├── main.py              # FastAPI 应用入口
├── config.py            # 🔧 配置与兼容层（用户配置、默认值、兼容旧路径）
├── dependencies.py      # 依赖注入
├── logger.py            # 日志配置
├── middleware/          # 中间件
│   └── auth.py          # 认证中间件
├── models/              # Pydantic 数据模型
│   ├── base.py          # 基础模型
│   ├── user.py          # 用户模型
│   ├── project.py       # 项目模型
│   ├── character.py     # 角色模型
│   ├── scene.py         # 场景模型
│   ├── prop.py          # 道具模型
│   ├── frame.py         # 分镜首帧模型
│   ├── video.py         # 视频模型
│   ├── gallery.py       # 图库模型
│   ├── studio.py        # 图片工作室模型
│   ├── media.py         # 媒体库模型（音频、视频、文本）
│   └── style.py         # 风格模型
├── routers/             # API 路由
│   ├── auth.py          # 认证 API
│   ├── settings.py      # 设置 API
│   ├── projects.py      # 项目 API
│   ├── scripts.py       # 分镜脚本 API
│   ├── characters.py    # 角色 API
│   ├── scenes.py        # 场景 API
│   ├── props.py         # 道具 API
│   ├── frames.py        # 分镜首帧 API
│   ├── videos.py        # 视频生成 API
│   ├── gallery.py       # 图库 API
│   ├── studio.py        # 图片工作室 API
│   ├── video_studio.py  # 视频工作室 API
│   └── ...
├── services/            # 业务服务
│   ├── storage.py       # JSON 存储服务
│   ├── user_service.py  # 用户服务
│   ├── oss.py           # OSS 服务
│   ├── file_parser.py   # 文件解析
│   └── dashscope/       # DashScope API 封装
│       ├── llm.py            # LLM 服务
│       ├── text_to_image.py  # 文生图服务
│       ├── image_to_image.py # 图生图服务
│       ├── image_to_video.py # 图生视频服务
│       ├── reference_to_video.py # 视频生视频服务
│       └── vace_video_edit.py # VACE 视频重绘/局部编辑服务
└── prompts/             # 提示词模板
    └── defaults.py      # 默认提示词
```

## 添加新 API 路由

### 1. 创建路由文件

```python
# routers/new_feature.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.services.storage import StorageService
from app.dependencies import get_storage

router = APIRouter()


class NewFeatureRequest(BaseModel):
    """请求模型"""
    project_id: str
    name: str
    # ... 其他字段


class NewFeatureResponse(BaseModel):
    """响应模型"""
    id: str
    name: str
    # ... 其他字段


@router.get("")
async def list_items(
    project_id: str,
    storage: StorageService = Depends(get_storage)  # 关键：注入用户存储
):
    """列出项目下的所有项目"""
    items = storage.get_items_by_project(project_id)
    return {"items": items}


@router.post("")
async def create_item(
    request: NewFeatureRequest,
    storage: StorageService = Depends(get_storage)
):
    """创建新项目"""
    # 业务逻辑...
    return {"item": item}
```

### 2. 注册路由

```python
# main.py
from app.routers import new_feature

app.include_router(
    new_feature.router,
    prefix="/api/new-feature",
    tags=["新功能"]
)
```

### 3. 导出路由

```python
# routers/__init__.py
from app.routers import (
    ...,
    new_feature  # 添加
)
```

## 添加新模型

### 工作室模型（图片/视频/音频）

不要再走“`config.py + router 分支 + 页面硬编码 if/else`”的老路径。

正确顺序：

1. 阅读 `docs/STUDIO_MODEL_INTEGRATION_GUIDE.md`
2. 先判断复用现有 `task_kind` 还是新增能力
3. 先补 schema / capabilities，再补 adapter / service
4. 先打通 `preview-payload`，再接真实提交
5. 保证开发者模式可见 canonical request / provider payload / task ids / request ids
6. 补测试、文档、checklist

### 模型注册中心中的通用模型

如果是注册中心可表达的模型能力：

1. 在 `backend/app/models_registry/{image,video,llm}/` 新增模型定义
2. 在对应 `__init__.py` 导入并注册
3. 若需要前端动态表单消费，确保 `/api/models/*` 可返回完整参数信息
4. 若模型属于工作室能力，仍应以 schema / capabilities 为最终交互入口

## 视频工作室能力 Schema

视频工作室现在以 `GET /api/video-studio/capabilities` 作为主配置源，核心文件：
- `backend/app/services/video_capabilities.py`
- `backend/app/services/video_adapters.py`
- `backend/app/routers/video_studio.py`

### 核心字段

- `task_kind`
  - 平台级任务能力，例如 `text_to_video`、`reference_to_video`、`video_edit_local`
- `provider`
  - 当前模型厂商，例如 `wan`、`kling`、`vidu`
- `model_id`
  - 厂商模型 ID
- `input_roles`
  - 当前任务需要的素材角色
- `parameters`
  - 当前模型在当前能力下支持的参数列表
- `ui_hints`
  - 前端辅助渲染信息，例如素材位帮助、Prompt 帮助、尺寸联动

### 参数帮助结构

视频工作室参数帮助统一在后端 schema 中维护，字段包括：

```python
{
    "summary": "短说明",
    "meaning": "参数真正控制什么",
    "limits": ["限制1", "限制2"],
    "how_to_choose": ["选择建议1", "选择建议2"],
    "examples": ["示例"],
    "notes": ["补充说明"]
}
```

补充位置：
- 参数级帮助：`parameter.help`
- 素材位帮助：`ui_hints.asset_help`
- Prompt 帮助：`ui_hints.prompt_help`

要求：
- 所有前端可见参数至少要有 `description` 或 `help`
- 重要参数优先使用完整 `help`
- 选择类参数应尽量在 `options[].description` 中补短说明，方便前端直接展示差异

### Wan 局部编辑为什么不暴露 `obj_or_bg`

当前平台没有把 `obj_or_bg` 暴露给 `video_edit_local`，原因是：
- 本地官方文档 `wan2.1视频编辑.md` 明确把 `obj_or_bg` 公开列在 `image_reference`
- `video_edit` 只说明“单张参考图可作为主体或背景使用”，但没有把 `obj_or_bg` 列为局部编辑公开参数

为了与官方公开文档保持一致并降低误用风险，本轮不在局部编辑表单中暴露该开关。

## DashScope 服务封装

### 服务类模板

```python
# services/dashscope/new_service.py
"""
新服务封装
参考: https://help.aliyun.com/...  # 添加官方文档链接
"""

import logging
from typing import Optional, List
import httpx

from app.config import get_config, NEW_MODELS
from app.services.oss import oss_service

logger = logging.getLogger(__name__)


class NewService:
    """新服务"""

    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.config = config.new_model
        self.base_url = config.base_url

    async def create_task(
        self,
        prompt: str,
        model: Optional[str] = None,
        # ... 其他参数
    ) -> str:
        """
        创建任务

        Args:
            prompt: 提示词
            model: 模型名称

        Returns:
            任务 ID
        """
        model_name = model or self.config.model

        # 构建请求
        request_body = {
            "model": model_name,
            "input": {"prompt": prompt},
            "parameters": {}
        }

        # 记录请求日志
        print(f"[{self.__class__.__name__}请求] 模型: {model_name}")
        print(f"[{self.__class__.__name__}请求] Body: {request_body}")

        # 发送请求
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/xxx/xxx",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json=request_body
            )

            result = response.json()

            # 记录响应日志
            print(f"[{self.__class__.__name__}响应] {result}")

            if response.status_code != 200:
                raise Exception(f"调用失败: {result.get('message')}")

            return result["output"]["task_id"]

    async def get_task_status(self, task_id: str) -> tuple:
        """查询任务状态"""
        # ...
```

## 数据存储规范

### StorageService 方法命名

```python
# 保存
save_xxx(item: XxxModel) -> None

# 获取单个
get_xxx(id: str) -> Optional[XxxModel]

# 获取项目下所有
get_xxx_by_project(project_id: str) -> List[XxxModel]

# 删除
delete_xxx(id: str) -> None
```

### 添加新存储类型

```python
# services/storage.py

class StorageService:
    def __init__(self, data_dir=None):
        # ... 现有目录
        self.new_dir = self.data_dir / "new_type"
        # 确保目录存在
        self._ensure_dirs()

    def _ensure_dirs(self):
        for dir_path in [
            # ... 现有目录
            self.new_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ============ NewType ============

    def save_new_item(self, item: NewModel) -> None:
        """保存新类型项"""
        item.updated_at = datetime.now()
        file_path = self.new_dir / f"{item.id}.json"
        self._write_json_with_lock(file_path, item.model_dump())

    def get_new_item(self, item_id: str) -> Optional[NewModel]:
        """获取新类型项"""
        file_path = self.new_dir / f"{item_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return NewModel(**data)
        return None

    # ... 其他方法
```

## 错误处理

```python
from fastapi import HTTPException

# 资源不存在
raise HTTPException(status_code=404, detail="资源不存在")

# 参数错误
raise HTTPException(status_code=400, detail="参数错误: xxx")

# 未授权
raise HTTPException(status_code=401, detail="未登录")

# 服务器错误（包装外部服务异常）
try:
    result = await external_service.call()
except Exception as e:
    raise HTTPException(status_code=500, detail=f"调用失败: {str(e)}")
```

## 日志规范

```python
import logging

logger = logging.getLogger(__name__)

# 普通信息
logger.info("操作完成")

# 调试信息
logger.debug("详细信息: %s", data)

# 警告
logger.warning("注意: xxx")

# 错误（带异常堆栈）
logger.exception("操作失败")

# API 调用日志（使用 print，会自动记录到日志文件）
print(f"[服务名请求] 参数: {params}")
print(f"[服务名响应] 结果: {result}")
```

## 后台任务执行

图片工作室的 `/generate` 端点使用后台异步执行模式：

```python
# 端点立即返回，后台执行生成
asyncio.create_task(_background_generate(task, user_id, user_config_dir, ...))
return {"task": task}  # status: "generating"
```

### ContextVar 传递

由于 AuthMiddleware 在请求结束后清除用户上下文，后台任务需要在启动前捕获并在执行时恢复：

```python
user_id = get_current_user_id()
user_config_dir = get_user_config_dir()

async def _background_generate(...):
    set_current_user(user_id)
    set_user_config_dir(user_config_dir)
    # ... 执行生成 ...
```

### 同步 API 包装

DashScope SDK 的同步调用（如 `MultiModalConversation.call`）通过 `asyncio.to_thread()` 包装：

```python
response = await asyncio.to_thread(MultiModalConversation.call, api_key=key, **params)
```

## HTTP 客户端规范

所有 HTTP 调用统一使用 `httpx`：
- 异步调用：`httpx.AsyncClient`
- 同步调用（线程池中）：`httpx.Client` 或 `httpx.get()`
- 已移除 `requests` 和 `aiohttp` 依赖

## API 限流

使用 `slowapi` 中间件进行全局限流：
- 默认限制：200 请求/分钟/IP
- 配置位于 `backend/app/main.py`

---

*最后更新: 2026-02-05*
# 视频工作室补充说明

## payload 预览
- 新增 `POST /api/video-studio/preview-payload`
- 请求体沿用视频工作室 canonical 草稿
- 返回：
  - `canonical_request`
  - `provider_payload`
  - `validation_warnings`
- 该接口只做规范化、校验与请求体构造，不真正提交厂商任务

## 任务缩略图
- 视频工作室任务在状态查询进入 `succeeded` 后，会尝试从输出视频抽取首帧缩略图
- 缩略图通过 OSS 保存，回写到 `VideoStudioTask.thumbnail_url`
- 列表页优先展示 `thumbnail_url`

## 通知设置
- `AppConfig` 新增 `video_task_notifications_enabled`
- 设置接口同步返回与保存该开关
# 图片工作室更新

- `/api/studio/models/available` 现在优先使用 registry 元数据，避免同名模型被旧配置覆盖
- 图片工作室继续保留 `/api/studio/preview-payload` 作为开发者模式预览入口
- 图片工作室生成结果统一走 `OSSService.persist_generated_image_with_fallback_async()`：
  - 厂商临时 URL 先下载到 `backend/data/assets/oss_staging/...`
  - 再使用本地文件上传 OSS
  - OSS 成功后删除本地暂存
  - 瞬时失败重试耗尽后保留 `/assets/...` 本地回退并写入 `StudioTask.warnings`
- 本地回退图的补偿重传由 `GET /api/studio` / `GET /api/studio/{id}` 懒触发后台任务，避免多 worker 全局常驻扫描：
  - `next_retry_at` 到期时调度 `_background_retry_task_local_fallbacks`
  - 手动接口为 `POST /api/studio/{id}/retry-oss` 与 `POST /api/studio/project/{project_id}/retry-oss`
  - 本地回退文件 7 天后标记 `local_expired` 并清理
  - 本地回退图不能保存到图库，必须先重传到 OSS
- `wan2.7` 相关校验已在 `studio.py` 中集中处理：
  - `task_kind` 与模型兼容性
  - `interactive_edit` 下的 `bbox_list` 长度与框数
  - `color_palette` 数量和百分比总和
  - `4K` 仅限 `wan2.7-image-pro` 的纯文生图
- `wan2.7` 输入图预检由 `remote_media_validation.inspect_remote_image()` 负责：
  - 支持 HTTP/HTTPS 和 `data:image/...;base64,...`
  - 下载失败会返回 HTTP 状态、content-type 或超时/协议错误
  - 图片解码失败会返回内容类型和字节数
  - 平台不再因透明 PNG 直接阻断，是否最终支持以厂商返回结果为准
  - 预检会做短间隔重试，避免一次网络抖动直接把测评单元标为 `unsupported`
- 视频工作室新增 `video_extension` 任务类型，当前默认由 `wan2.7-i2v` 承载
- `WanVideoAdapter` 已加入 `wan2.7-i2v`、临时快照 `wan2.7-i2v-2026-04-25`、`wan2.7-videoedit` 的专用校验与 payload builder：
  - `wan2.7-i2v` / `wan2.7-i2v-2026-04-25`：支持 `first_frame`、`last_frame`、`driving_audio`、`first_clip`；两者是独立模型 ID，payload 不做别名改写
  - `wan2.7-videoedit`：支持 1 个 `video` + 最多 3 个 `reference_image`
- `preview-payload` 与真实提交共用同一套构参逻辑，开发者模式可直接核对 `wan2.7` 请求体

# 图片测评运行时

- 图片测评由 `routers/image_benchmark.py` 提供 API，由 `services/image_benchmark_runtime.py` 复用图片工作室的模型能力、payload 构造和生成函数。
- 数据集支持 `schema_version=2.0` 的 `image_slots`，使用 `position` 保留“图1 / 图2 / 图N”的顺序语义；旧版 `input_images` 会在导入时迁移为槽位。
- 测评任务类型包含 `text_to_image`、`image_edit`、`interactive_edit`。`interactive_edit` 仅由 wan2.7 image 系列承载，复用图片工作室的 `bbox_list` 构参和坐标归一化逻辑；`image_edit` 会显式剥离遗留 `bbox_list`。
- `ImageBenchmarkDatasetItem.bbox_list` 与 `image_slots` 一起存储、导出和导入，长度必须与有效输入图数量一致；每张图最多 2 个框，不需要框选的位置必须保留空数组 `[]`。
- 跨环境导入数据集时可传 `migrate_images_to_oss=true`：
  - 后端会把输入图下载并上传到当前用户 OSS
  - 成功后把数据集中的 URL 替换为当前环境 OSS URL
  - 重复 URL 只上传一次，转存失败会写入 `migration_report.errors`
- 运行前会阻止图片编辑/交互式编辑数据集中存在槽位空缺的情况，避免提示词中的“图1 / 图2”与实际数组顺序错位；交互式编辑还会阻止 bbox 长度或格式不合法的样例。
- 单元结果 `ImageBenchmarkCellResult` 会保留：
  - `canonical_request`
  - `provider_payload`
  - `provider_result_meta`
  - `task_ids`
  - `request_ids`
- 自动重试会去重累计每次尝试产生的所有 `task_ids` 和 `request_ids`，便于后续对账和厂商工单排查。
- 图片工作室失败任务同样会保留 `provider_result_meta`，至少包含 `request_id / error_code / error_message / raw_output`，开发者模式与任务详情都应可见。
- 手动重试范围包括 `failed` 与 `unsupported`。其中 `unsupported` 主要代表前置校验失败，不一定是模型能力不支持。
- 测评报告导出由后端统一渲染：
  - `export-md-file` / `export-html-file` 返回附件文件，是前端按钮当前使用的推荐接口
  - `export-md` / `export-html` 返回 JSON，仅用于兼容旧调用或自动化检查
  - `inline_images=true` 会下载输入图 / 输出图原始字节并转为 `data:` 内嵌；下载采用限流并发和多次重试，明显失效 URL 回退原 URL
  - `inline_images=false` 是快速导出，跳过图片下载并保留原 URL
  - 响应头 `X-Embedded-Image-Count` / `X-Fallback-Url-Count` 用于前端提示和排障

# 视频测评运行时

- 视频测评由 `routers/video_benchmark.py` 提供 API，由 `services/video_benchmark_runtime.py` 复用视频工作室 `video_capabilities.py` 与 `video_adapters.py`。
- v1 固定支持 `image_to_video` 首帧生视频；capabilities 会自动筛选所有支持该任务类型的视频模型。
- 数据集独立存储在 `video_benchmark_datasets`，样例包含首帧图、prompt、负向提示词、标签、可选驱动音频和可选样例级 `duration`。
- 单元参数合并顺序为模型默认值、suite `baseline_params`、suite `model_overrides[model_id]`、case `duration`。case 时长仅影响当前单元，不回写 suite。
- capabilities 会注入测评层 `group_count`（生成数量，1-5），用于一个 case × model 单元生成多条视频。`group_count` 会进入 `effective_params` / `canonical_request`，但 adapter validate / submit / fetch 使用移除该参数后的 provider request，避免下发给厂商。
- 运行时按 case × model 构造 `NormalizedVideoTaskRequest`，执行 adapter validate / submit / fetch，并保存：
  - `effective_params`
  - `canonical_request`
  - `provider_payload`
  - `provider_result_meta`
  - `task_ids`
  - `request_ids`
  - `output_videos`
- 并发按模型 capability 的 `capabilities.max_concurrent` 执行；未声明时默认 1。同一单元从提交到终态都占用该模型 semaphore。
- case `duration` 对某个模型不合法时，该单元标记为 `unsupported`，其他模型继续运行。
- 报告导出只保留视频 URL；HTML 报告使用 `<video controls preload="metadata">`，不下载或内嵌视频字节。
