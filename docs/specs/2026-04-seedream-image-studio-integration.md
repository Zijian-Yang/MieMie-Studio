# Seedream 图片工作室接入

## 背景

- 本地参考文档：`docs/火山api文档/seedream文档.md`
- 平台接入指南：`docs/STUDIO_MODEL_INTEGRATION_GUIDE.md`
- 厂商接口：`POST https://ark.cn-beijing.volces.com/api/v3/images/generations`

厂商镜像文档只作为原始参考。本 spec 是平台侧实现口径。

图片工作室当前以 `task_kind + provider adapter + preview-payload + OSS 持久化` 为主轴。Seedream 作为独立 `provider=volcengine` 接入，不复用 DashScope 测试/生产 Key 池。

## 目标

- 接入 `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5`。
- 平台模型 ID 分别为 `doubao-seedream-5.0-lite`、`doubao-seedream-4.5`。
- 厂商模型名分别为 `doubao-seedream-5-0-260128`、`doubao-seedream-4-5-251128`。
- 设置页新增“火山引擎 Ark API Key”，保存独立 `volcengine_api_key`。
- 图片工作室支持文生图、图像编辑、组图生成。
- 图片测评开放 Seedream 的文生图和图像编辑能力；组图生成仅保留在图片工作室。

## 非目标

- 不新增自定义 Endpoint ID 设置。
- 不把火山 Key 混入 DashScope 测试/生产 Key 路由。
- 不接入 Seedream 流式返回；平台固定使用非流式 URL 返回。
- 不在图片测评中开放组图生成。

## 能力映射

### `text_to_image`

- 输入参考图数量必须为 0。
- 厂商 payload 下发 `sequential_image_generation=disabled`。
- `n` 固定为 1；需要多张结果时由平台 `group_count` 发起多组请求。

### `image_edit`

- 输入参考图数量必须为 1 到 14。
- 厂商 payload 下发 `image`，单图为字符串，多图为数组。
- 厂商 payload 下发 `sequential_image_generation=disabled`。
- `n` 固定为 1；需要多张结果时由平台 `group_count` 发起多组请求。

### `sequential_generation`

- 输入参考图数量可为 0 到 14。
- 厂商 payload 下发 `sequential_image_generation=auto`。
- `n` 映射为 `sequential_image_generation_options.max_images`。
- `参考图数量 + n <= 15`。

## 参数口径

- 通用参数：
  - `size`: 支持 `2K` / `4K` 或 `宽x高`；5.0 lite 额外支持 `3K`。
  - `watermark`: 原样下发。
  - `prompt_extend=true`: 下发 `optimize_prompt_options.mode=standard`。
- 5.0 lite 专属参数：
  - `output_format`: `jpeg` / `png`，默认 `jpeg`。
  - `web_search=true`: 下发 `tools=[{"type":"web_search"}]`。
- 固定传输参数：
  - `response_format=url`
  - `stream=false`

## 接口与数据

- `/api/studio/models/available` 暴露两个 Seedream 模型，`provider=volcengine`。
- `/api/studio/preview-payload` 必须展示 canonical request、provider payload 与参数提醒。
- 生成结果继续走图片工作室后台生成、轮询、OSS 暂存/持久化链路。
- 开发者模式继续记录 `provider_payload_snapshot`、`provider_result_meta.request_id`、`usage`、`tools`、单图错误和 `raw_response`。
- 设置接口：
  - `PUT /api/settings` 接收 `volcengine_api_key`。
  - `GET /api/settings` 返回 `volcengine_api_key_masked` 与 `is_volcengine_api_key_set`。

## 验收标准

- 两个 Seedream 模型可在图片工作室文生图、图像编辑、组图生成任务类型下选择。
- 5.0 lite 的 `output_format` / `web_search` 只在该模型展示和下发。
- 4.5 不接受 `output_format` / `web_search`。
- 文生图带参考图、图像编辑无参考图、组图 `参考图+n>15` 均返回明确错误。
- 图片测评 capability 包含 Seedream 文生图/图像编辑，不包含组图生成。
- 火山 Key 保存后设置页显示 masked 状态，且不影响 DashScope Key 路由。

## 验证

自动化：

```bash
venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q
cd frontend && npm run typecheck
cd frontend && npm run lint
git diff --check
```

手工 smoke：

1. 打开设置页，保存火山引擎 Ark API Key，确认 masked 状态。
2. 打开图片工作室，确认两个 Seedream 模型在对应任务类型下可选。
3. 展开开发者模式，核对 `response_format=url`、`stream=false`、`sequential_image_generation`、`output_format/tools`。
4. 有真实 Key 时提交 5.0 lite 文生图、4.5 图像编辑、5.0 lite 组图。
5. 核对图片进入 OSS 持久化结果，失败项保留厂商 request id 与 raw response。
