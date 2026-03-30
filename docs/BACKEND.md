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
