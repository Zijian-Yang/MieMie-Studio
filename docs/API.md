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

`GET /api/settings` 会返回火山引擎 Ark Key 的脱敏状态：

- `volcengine_api_key_masked`
- `is_volcengine_api_key_set`

`PUT /api/settings` 可写入 `volcengine_api_key`。这把 Key 仅供 `provider=volcengine` 的 Seedream 图片模型使用，不参与 DashScope 测试/生产 Key 路由。

所有 Key 字段写入前会去除首尾空白；空白字符串表示“不修改现有 Key”，不会清空已保存配置。

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
| POST | `/{id}/retry-oss` | 将任务内本地回退图片重新上传到 OSS |
| POST | `/project/{project_id}/retry-oss` | 将项目内所有本地回退图片重新上传到 OSS |
| GET | `/models/available` | 获取可用模型 |
| POST | `/preview-payload` | 预览 canonical 请求与厂商 payload |

`GET /api/studio/models/available`、`GET /api/settings` 与模型 registry/capabilities 会在已校准的阿里模型上暴露统一限流元数据：

```json
{
  "capabilities": {
    "api_mode": "sync",
    "submit_rate_limit": {"count": 2, "period_seconds": 60},
    "max_concurrent": null,
    "concurrency_scope": "unlimited",
    "rate_limit_note": "..."
  }
}
```

- `submit_rate_limit` 限制同步生成请求或异步任务提交请求的发出频率。
- `max_concurrent` 限制异步任务从提交成功到终态期间的处理中任务数量；`null` 表示当前平台实际调用接口的处理中任务无限制。
- `concurrency_scope=shared_pool` 时，多个模型共享同一个 `concurrency_pool_id` 的并发池。

#### Seedream / Volcengine

- `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5` 使用 `provider=volcengine`。
- 文生图：`task_kind=text_to_image`，不允许参考图，厂商 payload 使用 `sequential_image_generation=disabled`。
- 图像编辑：`task_kind=image_edit`，需要 1-14 张参考图，厂商 payload 使用 `sequential_image_generation=disabled`。
- 组图生成：`task_kind=sequential_generation`，允许 0-14 张参考图，厂商 payload 使用 `sequential_image_generation=auto`，并将 `n` 映射为 `sequential_image_generation_options.max_images`；`参考图数量 + n <= 15`。
- 通用参数：`size`、`watermark`、`prompt_extend`。`prompt_extend=true` 时下发 `optimize_prompt_options.mode=standard`。
- `size` 请求体格式必须是两种互斥方案之一：清晰度档位（5.0 lite 为 `2K`/`3K`/`4K`，4.5 为 `2K`/`4K`）或固定像素 `宽x高`（如 `2048x2048`）。固定像素总像素范围为 `2560x1440` 到 `4096x4096`，宽高比范围 `[1/16, 16]`。
- 模型 schema 中 `size.constraint.options` 仅暴露清晰度档位；固定像素尺寸由 `common_sizes` 暴露。图片工作室前端参考 Wan2.7 的尺寸设计，使用“清晰度档位 / 固定尺寸”二选一方案：清晰度模式只展示 `2K/3K/4K` 档位，固定尺寸模式才展示带比例的像素尺寸，popover 说明两种方案差异。
- `guidance_scale` 仅 Seedream 3.0 t2i 支持，`doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5` 不支持；平台不展示该控件，也不下发该字段。
- 5.0 lite 专属参数：`output_format=jpeg/png`、`web_search=true` 时下发 `tools=[{"type":"web_search"}]`。
- 固定下发 `response_format=url`、`stream=false`，结果继续走图片工作室后台生成、轮询和 OSS 持久化。

#### 图片工作室 OSS 回退

- 生成结果写入任务前会先落本地暂存，再上传当前用户 OSS；成功后删除本地暂存。
- 若 OSS 连续瞬时失败，任务图片会暂时使用 `/assets/oss_staging/...`，`storage_source=local_fallback`，并在 `warnings` 中返回告警。
- `GET /api/studio` 与 `GET /api/studio/{id}` 会触发到期本地回退图的后台补偿重传。
- 本地回退保留 7 天，过期后标记为 `local_expired` 并清理文件。
- `local_fallback` / `local_expired` 图片不能直接保存到图库；需先调用重传接口恢复为 OSS URL。

### 图片测评 `/api/image-benchmark`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/capabilities` | 获取可测评任务类型、模型与可配置参数 |
| GET | `/datasets?project_id={id}` | 列出项目数据集 |
| POST | `/datasets` | 创建数据集 |
| GET | `/datasets/{id}` | 获取数据集 |
| PUT | `/datasets/{id}` | 更新数据集 |
| DELETE | `/datasets/{id}` | 删除数据集 |
| POST | `/datasets/{id}/validate` | 校验图片槽位空缺 |
| GET | `/datasets/{id}/export` | 导出数据集 JSON |
| POST | `/datasets/import` | 导入数据集 JSON，可选转存输入图到当前 OSS |
| GET | `/suites?project_id={id}` | 列出测评任务 |
| POST | `/suites` | 创建测评任务 |
| GET | `/suites/{id}` | 获取测评任务 |
| PUT | `/suites/{id}` | 更新测评任务 |
| DELETE | `/suites/{id}` | 删除测评任务及其运行记录 |
| POST | `/suites/{id}/run` | 启动一次测评运行 |
| GET | `/runs/{id}` | 获取运行记录与单元结果 |
| POST | `/runs/{id}/export-md` | 导出 Markdown 测评报告（JSON，兼容旧前端） |
| POST | `/runs/{id}/export-html` | 导出 HTML 测评报告（JSON，兼容旧前端） |
| POST | `/runs/{id}/export-md-file` | 导出 Markdown 测评报告附件 |
| POST | `/runs/{id}/export-html-file` | 导出 HTML 测评报告附件 |
| POST | `/runs/{id}/retry-failures` | 重试状态为 `failed` 或 `unsupported` 的单元 |
| POST | `/preview-cell` | 预览单个 case × model 的 canonical 请求与厂商 payload |

运行接口会立即返回完整 `pending` cell 矩阵；后台执行中会增量写入 `running` / 终态 cell，`GET /runs/{id}` 可在 run 仍为 `running` 时看到已完成输出。`stats` 包含 `pending_count`、`running_count`、`completed_count`，前端通过轮询即时展示已完成结果。

#### 测评报告导出

`export-md-file` 与 `export-html-file` 是当前前端按钮使用的推荐接口，直接返回附件文件，避免超大 Markdown / HTML 通过 JSON 传输导致浏览器内存占用高或下载不触发。

请求体：

```json
{
  "inline_images": true
}
```

- `inline_images=true`：完整导出。后端会收集运行快照中的输入图 / 输出图，限流并发下载原图并转成 `data:<mime>;base64,...` 内嵌到单文件中；对超时、网络抖动、`429/5xx` 会自动重试，`403/404/410` 等明显失效 URL 会回退原 URL。
- `inline_images=false`：快速导出。跳过图片下载，报告中保留原 URL。

附件接口响应头：

| Header | 说明 |
|---|---|
| `Content-Disposition` | 附件文件名，格式为 `image_benchmark_{run_id}.md/html` |
| `X-Embedded-Image-Count` | 成功内嵌的图片数量 |
| `X-Fallback-Url-Count` | 下载失败后回退为原 URL 的图片数量 |

`export-md` / `export-html` 仍返回 JSON：

```json
{
  "filename": "image_benchmark_run-id.md",
  "content": "# 图片测评报告...",
  "embedded_image_count": 12,
  "fallback_url_count": 0
}
```

#### 数据集导入

`POST /api/image-benchmark/datasets/import`

```json
{
  "project_id": "project-id",
  "name": "可选的新数据集名称",
  "description": "可选说明",
  "migrate_images_to_oss": true,
  "data": {
    "type": "image_benchmark_dataset",
    "schema_version": "2.0",
    "task_kind": "interactive_edit",
    "max_image_slot_index": 2,
    "items": [
      {
        "id": "case-1",
        "name": "样例1",
        "prompt": "将图2中的人物换成图1中的人物",
        "bbox_list": [[], [[10, 20, 100, 140]]],
        "image_slots": [
          {"position": 1, "image": {"url": "https://...", "name": "图1"}},
          {"position": 2, "image": {"url": "https://...", "name": "图2"}}
        ]
      }
    ]
  }
}
```

- `migrate_images_to_oss=false`（默认）：只保留导入 JSON 中的图片 URL。
- `migrate_images_to_oss=true`：后端会下载每个输入图并上传到当前用户配置的 OSS，再把数据集中的 URL 替换为当前环境 OSS URL；重复 URL 会复用同一次上传结果。
- 响应中的 `migration_report` 包含 `enabled`、`attempted`、`succeeded`、`failed`、`skipped` 和 `errors`，用于判断是否有图片转存失败。
- `interactive_edit` 数据集会保留 `bbox_list`，其长度必须与输入图数量一致；每张图最多 2 个框，不需要框选的位置使用空数组 `[]`。导出后再导入不会丢失 bbox 数据。

### 视频测评 `/api/video-benchmark`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/capabilities` | 获取可测评首帧生视频模型与可配置参数 |
| GET | `/datasets?project_id={id}` | 列出项目视频数据集 |
| POST | `/datasets` | 创建视频数据集 |
| GET | `/datasets/{id}` | 获取视频数据集 |
| PUT | `/datasets/{id}` | 更新视频数据集 |
| DELETE | `/datasets/{id}` | 删除视频数据集 |
| GET | `/datasets/{id}/export` | 导出视频数据集 JSON |
| POST | `/datasets/import` | 导入视频数据集 JSON |
| GET | `/suites?project_id={id}` | 列出视频测评任务 |
| POST | `/suites` | 创建视频测评任务 |
| GET | `/suites/{id}` | 获取视频测评任务 |
| PUT | `/suites/{id}` | 更新视频测评任务 |
| DELETE | `/suites/{id}` | 删除视频测评任务及其运行记录 |
| POST | `/suites/{id}/run` | 启动一次视频测评运行 |
| GET | `/runs/{id}` | 获取运行记录与单元结果 |
| POST | `/runs/{id}/retry-failures` | 重试状态为 `failed` 或 `unsupported` 的单元 |
| POST | `/runs/{id}/export-md-file` | 导出 Markdown 视频测评报告附件 |
| POST | `/runs/{id}/export-html-file` | 导出 HTML 视频测评报告附件 |
| POST | `/preview-cell` | 预览单个 case × model 的 canonical 请求与厂商 payload |

v1 固定 `task_kind=image_to_video`。数据集 item 示例：

```json
{
  "name": "角色转身",
  "prompt": "让画面中的角色自然转身，镜头稳定",
  "negative_prompt": "模糊",
  "tags": ["角色"],
  "duration": 6,
  "first_frame": {"url": "https://...", "name": "首帧.png"},
  "audio": {"url": "https://...", "name": "驱动音频.mp3"}
}
```

视频数据集允许暂存缺少 `first_frame` 的样例，`create/get/update/import` 响应会返回 `warnings` 与 `blocking_issues`：

```json
{
  "item_id": "case-id",
  "item_name": "样例 1",
  "missing_fields": ["first_frame"],
  "message": "缺首帧图，无法开始首帧生视频测评"
}
```

缺首帧样例可以保存和导出，但 `preview-cell` 与 `suites/{id}/run` 会返回 400，并携带 `blocking_issues` 阻止真实提交。

单元有效参数合并顺序为：模型默认值 → suite `baseline_params` → suite `model_overrides[model_id]` → case `duration`。case 时长对某个模型不合法时，该单元会标记为 `unsupported`，不阻塞其他模型。

前端视频测评页不再提供 `Baseline Params JSON` 输入，创建、保存、运行和 preview 时会把 `baseline_params` 置为 `{}`，常规参数全部通过每个参与模型的独立参数表单写入 `model_overrides[model_id]`。API 字段仍保留用于旧数据读取和外部调用兼容。

`GET /capabilities` 会为每个首帧生视频模型额外暴露测评层参数 `group_count`（生成数量），默认 1。有限并发模型的最大值来自 `capabilities.max_concurrent`，同步无限并发模型不额外设置上限。它会写入 `effective_params` 与 `canonical_request.normalized_params`，用于控制一个 case × model 单元提交多少个厂商任务；构造 `provider_payload` 时会移除，不作为厂商参数透传。运行结果会把多条结果保存在同一个 cell 的 `output_videos[]`，并累计所有 `task_ids` / `request_ids`。

`POST /suites/{id}/run` 会立即返回完整 `pending` cell 矩阵；后台执行中会增量写入 `running` / 终态 cell。`group_count > 1` 时，单条视频完成 OSS 持久化后会先追加到 `output_videos[]`，因此 `GET /runs/{id}` 可在 run 仍为 `running` 时看到部分可播放视频。`stats` 包含 `pending_count`、`running_count`、`completed_count`。

报告导出不内嵌视频字节。Markdown 保留视频 URL，HTML 使用 `<video controls preload="metadata">` 播放输出视频。

#### 运行记录中的追踪字段

每个 `cell_results[]` 会保留：

```json
{
  "case_id": "case-1",
  "model_id": "wan2.7-image",
  "status": "completed",
  "task_ids": ["task-a", "task-b"],
  "request_ids": ["submit-request", "poll-request"],
  "canonical_request": {},
  "provider_payload": {},
  "provider_result_meta": {}
}
```

- 自动重试发生时，最终 cell 会去重累计每次尝试产生的所有 `task_ids` 与 `request_ids`。
- `unsupported` 用于前置校验失败，例如 wan2.7 输入图暂时无法下载或解码；该状态可通过 `retry-failures` 再次提交。

### 视频工作室 `/api/video-studio`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出任务 |
| GET | `/capabilities` | 获取视频能力 schema（任务能力、模型、参数、帮助说明） |
| POST | `/` | 创建任务 |
| GET | `/{id}` | 获取任务 |
| PUT | `/{id}` | 更新任务 |
| DELETE | `/{id}` | 删除任务 |
| GET | `/{id}/status` | 查询状态 |
| POST | `/{id}/regenerate` | 重新生成 |
| POST | `/{id}/save-to-library` | 保存到视频库 |
| POST | `/prepare-source-video` | 校验源视频并提取首帧预览 |
| POST | `/upload-mask` | 上传并规范化局部编辑 Mask |

### 视频工作室能力 Schema 说明

`GET /api/video-studio/capabilities` 返回的视频能力 schema 用于驱动前端任务表单。

视频模型的 `capabilities` 同样包含 `api_mode`、`submit_rate_limit`、`max_concurrent`、`concurrency_scope`、`concurrency_pool_id` 与 `rate_limit_note`。视频工作室创建/更新任务时会拒绝超过有限 `max_concurrent` 的 `group_count`；状态查询和轮询不计入任务下发频率限制。

关键结构：

```json
{
  "task_kinds": [
    {
      "id": "video_edit_local",
      "label": "局部编辑",
      "model_ids": ["wanx2.1-vace-plus"],
      "default_model_id": "wanx2.1-vace-plus"
    }
  ],
  "models": {
    "wanx2.1-vace-plus": {
      "provider": "wan",
      "supported_task_kinds": ["video_edit_local", "video_repainting"],
      "task_profiles": {
        "video_edit_local": {
          "input_roles": ["source_video", "reference_image", "mask_image"],
          "parameters": [...],
          "ui_hints": {
            "asset_help": {...},
            "prompt_help": {...}
          }
        }
      }
    }
  }
}
```

帮助字段约定：
- `parameter.description`
  - 短说明
- `parameter.help`
  - 结构化详细帮助
- `ui_hints.asset_help`
  - 素材位帮助
- `ui_hints.prompt_help`
  - Prompt 输入框帮助

`help` 结构：

```json
{
  "summary": "概览",
  "meaning": "参数含义",
  "limits": ["限制1", "限制2"],
  "how_to_choose": ["选择建议1", "选择建议2"],
  "examples": ["示例"],
  "notes": ["补充说明"]
}
```

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

*最后更新: 2026-04-13*
