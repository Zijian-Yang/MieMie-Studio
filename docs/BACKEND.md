# 后端开发规范

## 目录结构

```
backend/app/
├── main.py              # FastAPI 应用入口
├── config.py            # 🔧 配置中心（模型定义在此！）
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

### 1. 在 config.py 添加模型配置

```python
# config.py

# 新模型配置
NEW_MODELS = {
    "model-name": {
        "name": "显示名称",
        "description": "模型描述",
        "max_n": 4,
        "supports_xxx": True,
        "common_sizes": [
            {"width": 1280, "height": 720, "label": "16:9"},
            # ...
        ]
    }
}
```

### 2. 添加配置类

```python
# config.py

class NewModelConfig(BaseModel):
    """新模型配置"""
    model: str = "model-name"
    param1: bool = True
    param2: int = 5
    # ...
```

### 3. 在 AppConfig 中添加

```python
class AppConfig(BaseModel):
    # ...
    new_model: NewModelConfig = NewModelConfig()
```

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
- `wan2.7` 相关校验已在 `studio.py` 中集中处理：
  - `task_kind` 与模型兼容性
  - `bbox_list` 长度与框数
  - `color_palette` 数量和百分比总和
  - `4K` 仅限 `wan2.7-image-pro` 的纯文生图
- `wan2.7` 输入图预检由 `remote_media_validation.inspect_remote_image()` 负责：
  - 支持 HTTP/HTTPS 和 `data:image/...;base64,...`
  - 下载失败会返回 HTTP 状态、content-type 或超时/协议错误
  - 图片解码失败会返回内容类型和字节数
  - 预检会做短间隔重试，避免一次网络抖动直接把测评单元标为 `unsupported`
- 视频工作室新增 `video_extension` 任务类型，当前由 `wan2.7-i2v` 承载
- `WanVideoAdapter` 已加入 `wan2.7-i2v` / `wan2.7-videoedit` 的专用校验与 payload builder：
  - `wan2.7-i2v`：支持 `first_frame`、`last_frame`、`driving_audio`、`first_clip`
  - `wan2.7-videoedit`：支持 1 个 `video` + 最多 3 个 `reference_image`
- `preview-payload` 与真实提交共用同一套构参逻辑，开发者模式可直接核对 `wan2.7` 请求体

# 图片测评运行时

- 图片测评由 `routers/image_benchmark.py` 提供 API，由 `services/image_benchmark_runtime.py` 复用图片工作室的模型能力、payload 构造和生成函数。
- 数据集支持 `schema_version=2.0` 的 `image_slots`，使用 `position` 保留“图1 / 图2 / 图N”的顺序语义；旧版 `input_images` 会在导入时迁移为槽位。
- 跨环境导入数据集时可传 `migrate_images_to_oss=true`：
  - 后端会把输入图下载并上传到当前用户 OSS
  - 成功后把数据集中的 URL 替换为当前环境 OSS URL
  - 重复 URL 只上传一次，转存失败会写入 `migration_report.errors`
- 运行前会阻止图片编辑数据集中存在槽位空缺的情况，避免提示词中的“图1 / 图2”与实际数组顺序错位。
- 单元结果 `ImageBenchmarkCellResult` 会保留：
  - `canonical_request`
  - `provider_payload`
  - `provider_result_meta`
  - `task_ids`
  - `request_ids`
- 自动重试会去重累计每次尝试产生的所有 `task_ids` 和 `request_ids`，便于后续对账和厂商工单排查。
- 手动重试范围包括 `failed` 与 `unsupported`。其中 `unsupported` 主要代表前置校验失败，不一定是模型能力不支持。
