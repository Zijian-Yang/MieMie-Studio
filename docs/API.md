# API 设计规范

## 基础规范

### URL 格式

```
/api/{资源名}                    # 列表/创建
/api/{资源名}/{id}               # 获取/更新/删除
/api/{资源名}/{id}/{动作}        # 特殊操作
```

### HTTP 方法

| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 获取资源 | `GET /api/projects` |
| POST | 创建资源 | `POST /api/projects` |
| PUT | 更新资源 | `PUT /api/projects/{id}` |
| DELETE | 删除资源 | `DELETE /api/projects/{id}` |

### 请求/响应格式

```json
// 请求体
{
  "field1": "value1",
  "field2": 123
}

// 成功响应
{
  "item": {...},      // 单个资源
  "items": [...],     // 资源列表
  "message": "操作成功"  // 可选消息
}

// 错误响应
{
  "detail": "错误信息"
}
```

### 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功（无内容） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

## 认证

### Token 格式

```
Authorization: Bearer {token}
```

### 公开路径（无需认证）

- `/` - API 根路径
- `/docs` - Swagger 文档
- `/redoc` - ReDoc 文档
- `/openapi.json` - OpenAPI 规范
- `/api/health` - 健康检查
- `/api/auth/login` - 登录
- `/api/auth/register` - 注册
- `/assets/*` - 静态资源

## API 列表

### 认证 `/api/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/register` | 用户注册 |
| POST | `/login` | 用户登录 |
| POST | `/logout` | 用户登出 |
| GET | `/me` | 获取当前用户信息 |
| POST | `/change-password` | 修改密码 |

### 设置 `/api/settings`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取所有设置 |
| PUT | `/` | 更新设置 |
| POST | `/api-key` | 设置 API Key |
| DELETE | `/api-key` | 删除 API Key |
| POST | `/oss/test` | 测试 OSS 连接 |

### 项目 `/api/projects`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出所有项目 |
| POST | `/` | 创建项目 |
| GET | `/{id}` | 获取项目 |
| PUT | `/{id}` | 更新项目 |
| DELETE | `/{id}` | 删除项目 |
| GET | `/{id}/summary` | 获取项目摘要 |

### 分镜脚本 `/api/scripts`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{project_id}` | 获取项目脚本 |
| PUT | `/{project_id}` | 保存脚本 |
| POST | `/generate` | 生成/优化脚本（SSE 流式） |
| POST | `/extract-shots` | 提取分镜 |

### 角色 `/api/characters`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出角色（需 `project_id`） |
| POST | `/create` | 创建角色 |
| POST | `/extract` | 从脚本提取角色 |
| GET | `/{id}` | 获取角色 |
| PUT | `/{id}` | 更新角色 |
| DELETE | `/{id}` | 删除角色 |
| POST | `/{id}/generate` | 生成角色图片 |
| POST | `/{id}/select-images` | 选择角色图片 |

### 场景 `/api/scenes`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出场景 |
| POST | `/create` | 创建场景 |
| POST | `/extract` | 从脚本提取场景 |
| PUT | `/{id}` | 更新场景 |
| DELETE | `/{id}` | 删除场景 |
| POST | `/{id}/generate` | 生成场景图片 |
| POST | `/{id}/select-image` | 选择场景图片 |

### 道具 `/api/props`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出道具 |
| POST | `/create` | 创建道具 |
| POST | `/extract` | 从脚本提取道具 |
| PUT | `/{id}` | 更新道具 |
| DELETE | `/{id}` | 删除道具 |
| POST | `/{id}/generate` | 生成道具图片 |
| POST | `/{id}/select-image` | 选择道具图片 |

### 分镜首帧 `/api/frames`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出首帧 |
| POST | `/sync` | 同步分镜数据 |
| POST | `/generate` | 生成首帧图片 |
| PUT | `/{id}` | 更新首帧 |
| DELETE | `/{id}` | 删除首帧 |
| POST | `/set-from-gallery` | 从图库设置首帧 |
| POST | `/{id}/save-to-gallery` | 保存到图库 |

### 视频 `/api/videos`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出视频 |
| POST | `/generate` | 生成视频 |
| GET | `/status/{task_id}` | 查询生成状态 |
| DELETE | `/{id}` | 删除视频 |

### 图库 `/api/gallery`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出图片 |
| POST | `/` | 添加图片（URL） |
| POST | `/batch` | 批量添加 |
| POST | `/upload-files` | 上传文件 |
| PUT | `/{id}` | 更新图片信息 |
| DELETE | `/{id}` | 删除图片 |

### 图片工作室 `/api/studio`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出任务 |
| POST | `/` | 创建任务 |
| GET | `/{id}` | 获取任务 |
| PUT | `/{id}` | 更新任务 |
| DELETE | `/{id}` | 删除任务 |
| POST | `/{id}/generate` | 执行生成 |
| POST | `/{id}/save-to-gallery` | 保存到图库 |
| GET | `/models` | 获取可用模型 |

### 视频工作室 `/api/video-studio`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出任务 |
| POST | `/` | 创建任务 |
| GET | `/{id}` | 获取任务 |
| PUT | `/{id}` | 更新任务 |
| DELETE | `/{id}` | 删除任务 |
| GET | `/{id}/status` | 查询状态 |
| POST | `/{id}/regenerate` | 重新生成 |
| POST | `/{id}/save-to-library` | 保存到视频库 |
| POST | `/prepare-source-video` | 校验源视频并提取首帧预览 |
| POST | `/upload-mask` | 上传并规范化局部编辑 Mask |

### 音频库 `/api/audio`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出音频 |
| POST | `/upload` | 上传音频 |
| POST | `/add-from-urls` | 从 URL 添加 |
| PUT | `/{id}` | 更新音频信息 |
| DELETE | `/{id}` | 删除音频 |

### 视频库 `/api/video-library`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出视频 |
| POST | `/upload` | 上传视频 |
| POST | `/add-from-urls` | 从 URL 添加 |
| PUT | `/{id}` | 更新视频信息 |
| DELETE | `/{id}` | 删除视频 |

## 异步任务模式

### 创建任务

```http
POST /api/video-studio
Content-Type: application/json

{
  "project_id": "xxx",
  "task_type": "image_to_video",
  "first_frame_url": "https://...",
  "prompt": "描述"
}
```

`task_type` 当前支持：
- `image_to_video`
- `reference_to_video`
- `text_to_video`
- `keyframe_to_video`
- `video_repainting`
- `video_edit`

响应：

```json
{
  "task": {
    "id": "task-xxx",
    "status": "processing",
    "task_ids": ["api-task-1", "api-task-2"]
  }
}
```

### 查询状态（轮询）

```http
GET /api/video-studio/{id}/status
```

响应：

```json
{
  "task": {
    "id": "task-xxx",
    "status": "succeeded",  // pending | processing | succeeded | failed
    "video_urls": ["https://..."],
    "error_message": null
  }
}
```

## 流式响应（SSE）

用于 LLM 生成等长时间操作：

```http
POST /api/scripts/generate
Content-Type: application/json
Accept: text/event-stream

{
  "project_id": "xxx",
  "prompt": "..."
}
```

响应格式：

```
event: chunk
data: {"type": "content", "content": "生成的文本片段"}

event: chunk
data: {"type": "thinking", "content": "思考过程"}

event: done
data: {"type": "complete"}

event: error
data: {"type": "error", "message": "错误信息"}
```

## 视频工作室补充接口

### 准备源视频首帧

```http
POST /api/video-studio/prepare-source-video
Content-Type: application/json

{
  "project_id": "xxx",
  "video_url": "https://..."
}
```

响应：

```json
{
  "preview_image_data_url": "data:image/jpeg;base64,...",
  "preview_image_url": "https://oss-example/preview.jpg",
  "metadata": {
    "width": 1280,
    "height": 720,
    "fps": 25.0,
    "duration": 4.2,
    "frame_count": 105,
    "file_size": 1234567,
    "format": "mp4"
  },
  "warnings": []
}
```

### 上传局部编辑 Mask

```http
POST /api/video-studio/upload-mask
Content-Type: multipart/form-data
```

表单字段：
- `project_id`
- `source_video_url`
- `mask_file`

响应：

```json
{
  "mask_image_url": "https://oss-example/video-mask.png"
}
```

### 视频重绘示例

```http
POST /api/video-studio
Content-Type: application/json

{
  "project_id": "xxx",
  "name": "视频重绘示例",
  "task_type": "video_repainting",
  "model": "wanx2.1-vace-plus",
  "source_video_url": "https://...",
  "reference_image_url": "https://...",
  "prompt": "将人物改成蒸汽朋克风格，保留原动作和镜头节奏",
  "control_condition": "depth",
  "strength": 0.8,
  "prompt_extend": false,
  "watermark": false
}
```

### 局部编辑示例

```http
POST /api/video-studio
Content-Type: application/json

{
  "project_id": "xxx",
  "name": "局部编辑示例",
  "task_type": "video_edit",
  "model": "wanx2.1-vace-plus",
  "source_video_url": "https://...",
  "mask_image_url": "https://...",
  "mask_frame_id": 1,
  "prompt": "将白色 Mask 区域中的咖啡杯改成透明玻璃杯",
  "mask_type": "tracking",
  "expand_ratio": 0.05,
  "expand_mode": "hull",
  "size": "1280*720",
  "prompt_extend": false,
  "watermark": false
}
```

说明：
- `video_repainting` 和 `video_edit` 均固定使用 `wanx2.1-vace-plus`
- `video_edit` 当前仅支持首帧 `mask_image_url` 工作流，`mask_frame_id` 固定为 `1`
- 局部编辑上传的 Mask 会在服务端被规范化为严格黑白二值 PNG，再上传到 OSS
- 输入视频限制：MP4、`>=16 FPS`、`<=50MB`；超过 5 秒或超过 720P 会给出 warning，但不阻断提交

---

*最后更新: 2026-03-30*
