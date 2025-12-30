# DashScope 集成指南

## 概述

本平台集成阿里云 DashScope（通义万相）的多种 AI 模型服务。

## 支持的模型

### 文生图模型

| 模型 | 调用方式 | 特点 |
|------|----------|------|
| `wan2.6-t2i` | HTTP 同步 | 快速生成，无需轮询 |
| `wan2.5-t2i-preview` | SDK 异步 | 需要轮询获取结果 |
| `wan2.6-image` | HTTP 异步 | 支持参考图、图文混合 |

### 图生图模型

| 模型 | 调用方式 | 特点 |
|------|----------|------|
| `wan2.5-i2i-preview` | SDK 异步 | 风格迁移、局部编辑 |
| `qwen-image-edit-plus` | HTTP 异步 | 智能编辑 |

### 图生视频模型

| 模型 | 调用方式 | 特点 |
|------|----------|------|
| `wan2.5-i2v-preview` | SDK 异步 | 基础图生视频 |
| `wan2.6-i2v-preview` | HTTP 异步 | 支持 15 秒、镜头类型 |
| `wanx2.1-i2v-preview` | SDK 异步 | 快速生成 |

### 视频生视频模型

| 模型 | 调用方式 | 特点 |
|------|----------|------|
| `wan2.6-r2v` | HTTP 异步 | 参考视频角色/音色生成 |

### LLM 模型

| 模型 | 特点 |
|------|------|
| `qwen3-max` | 高质量，支持联网搜索 |
| `qwen-plus-latest` | 支持深度思考模式 |

## 配置说明

### 模型配置位置

所有模型配置在 `backend/app/config.py`：

```python
# 文生图模型配置
IMAGE_MODELS = {
    "wan2.6-t2i": {
        "name": "文生图 wan2.6-t2i",
        "use_http": True,          # 使用 HTTP 调用
        "is_async": False,         # 同步调用
        "max_n": 4,                # 最多生成 4 张
        "supports_prompt_extend": True,
        "supports_watermark": True,
        "supports_seed": True,
        "common_sizes": [...]
    },
    ...
}

# 视频模型配置
VIDEO_MODELS = {...}

# 视频生视频模型配置
REF_VIDEO_MODELS = {...}
```

## 添加新模型

### 1. 添加模型配置

```python
# config.py

NEW_MODELS = {
    "new-model-name": {
        "name": "显示名称",
        "description": "模型描述",
        "use_http": True,  # 或 False
        "is_async": True,  # 或 False
        "max_n": 4,
        "supports_xxx": True,
        "common_sizes": [...]
    }
}

class NewModelConfig(BaseModel):
    model: str = "new-model-name"
    param1: bool = True
    ...
```

### 2. 实现服务类

```python
# services/dashscope/new_model.py

class NewModelService:
    def __init__(self):
        config = get_config()
        self.api_key = config.dashscope_api_key
        self.base_url = config.base_url
    
    async def create_task(self, ...) -> str:
        """创建任务"""
        # HTTP 调用
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/services/aigc/...",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"  # 异步调用
                },
                json={...}
            )
        # 或 SDK 调用
        response = dashscope.ModelName.call(...)
    
    async def get_task_status(self, task_id: str) -> tuple:
        """查询状态"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
```

### 3. 更新路由

```python
# routers/xxx.py

from app.services.dashscope.new_model import NewModelService

@router.post("/generate")
async def generate(...):
    service = NewModelService()
    task_id = await service.create_task(...)
```

### 4. 更新前端

```typescript
// services/api.ts

export interface NewModelConfig {
  model: string
  param1: boolean
  ...
}

// 更新 ConfigResponse 接口
export interface ConfigResponse {
  ...
  new_model: NewModelConfig
  available_new_models: Record<string, NewModelInfo>
}
```

## API 调用模式

### 同步调用（HTTP）

```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{base_url}/services/aigc/xxx",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=request_body
    )
    result = response.json()
    # 直接获取结果
    image_url = result["output"]["results"][0]["url"]
```

### 异步调用（HTTP + 轮询）

```python
# 1. 创建任务
response = await client.post(
    f"{base_url}/services/aigc/xxx",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"  # 关键！
    },
    json=request_body
)
task_id = response.json()["output"]["task_id"]

# 2. 轮询状态
while True:
    status_response = await client.get(
        f"{base_url}/tasks/{task_id}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    status = status_response.json()["output"]["task_status"]
    
    if status == "SUCCEEDED":
        result_url = status_response.json()["output"]["xxx_url"]
        break
    elif status == "FAILED":
        raise Exception("任务失败")
    
    await asyncio.sleep(5)  # 等待 5 秒
```

### SDK 异步调用

```python
import dashscope
from dashscope import ImageSynthesis

# 1. 提交任务
response = ImageSynthesis.async_call(
    model="wan2.5-t2i-preview",
    prompt=prompt,
    n=4,
    size=f"{width}*{height}"
)
task_id = response.output.task_id

# 2. 等待结果
result = ImageSynthesis.wait(
    task=response,
    timeout=300
)
image_urls = [r.url for r in result.output.results]
```

## 常见问题

### 图片尺寸限制

- `wan2.6-image` 参考图：384-5000 像素
- 文生图输出：768*768 - 1440*1440 总像素

### 超时处理

- 设置合理的超时时间（如 6 分钟）
- 使用重试机制

### 费用控制

- 分辨率越高费用越高
- 视频时长按秒计费
- 生成数量影响费用

## 官方文档

- [文生图 V2](https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference)
- [图生视频](https://help.aliyun.com/zh/model-studio/image-to-video-api)
- [视频生视频](https://help.aliyun.com/zh/model-studio/reference-to-video-api)
- [Qwen LLM](https://help.aliyun.com/zh/model-studio/qwen-api)

---

*最后更新: 2025-12-30*

