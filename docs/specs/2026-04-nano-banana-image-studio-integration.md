# Nano Banana 图片工作室接入 Spec

日期：2026-04-30

## 背景

Google Gemini 原生图片生成能力以 Nano Banana 2 / Pro 形式提供，返回 inline base64 图片而不是临时 URL。平台需要在图片工作室和图片测评中接入这两个模型，同时保持现有后台生成、轮询、OSS 持久化和开发者模式观测链路。

参考：

- `docs/Google模型api文档.md/nano-banana文档.md`
- `docs/STUDIO_MODEL_INTEGRATION_GUIDE.md`
- Google Gemini API `generateContent` 图片生成与图片理解文档

## 模型

| 平台 ID | Provider | Provider model | 能力 |
|---|---|---|---|
| `nano-banana-2` | `google` | `gemini-3.1-flash-image-preview` | `text_to_image`、`image_edit` |
| `nano-banana-pro` | `google` | `gemini-3-pro-image-preview` | `text_to_image`、`image_edit` |

v1 不接入 `sequential_generation`。多输出由平台 `group_count` 多次请求承载，单次请求 `n=1`。

## 参数与限制

- 共同参数：`aspect_ratio`、`image_size`、`google_search_mode`
- `nano-banana-2`：
  - `image_size`: `512`、`1K`、`2K`、`4K`
  - `aspect_ratio`: `1:1`、`1:4`、`1:8`、`2:3`、`3:2`、`3:4`、`4:1`、`4:3`、`4:5`、`5:4`、`8:1`、`9:16`、`16:9`、`21:9`
  - `thinking_level`: `minimal`、`high`
  - `google_search_mode`: `none`、`web`、`image`、`web_and_image`
- `nano-banana-pro`：
  - `image_size`: `1K`、`2K`、`4K`
  - `aspect_ratio`: `1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`4:5`、`5:4`、`9:16`、`16:9`、`21:9`
  - `google_search_mode`: `none`、`web`
- 文生图不允许参考图；图像编辑必须有 1-14 张参考图。
- 不展示或下发 `negative_prompt`、`seed`、`watermark`、`output_format`、`prompt_extend`。
- Google 图片默认带 SynthID；不支持透明背景。

## 后端契约

- 设置新增 `google_api_key`，`GET /api/settings` 返回 `google_api_key_masked` 与 `is_google_api_key_set`。
- `get_provider_api_key("google")` 返回独立 Google Key，不参与 DashScope 测试/生产 Key 路由。
- Adapter 调用：
  - `POST https://generativelanguage.googleapis.com/v1beta/models/{api_model_name}:generateContent`
  - Header: `x-goog-api-key: <google_api_key>`
  - body: `contents[].parts[]` + `generationConfig.responseModalities=["IMAGE"]`
  - 参考图下载后转为 `inline_data: { mime_type, data }`
- 结果解析：
  - 读取 `candidates[].content.parts[]` 中非 `thought` 的 `inlineData/inline_data`
  - 保留 `usageMetadata`、`groundingMetadata`、`finishReason`、文本 part、thought 数量、raw response 到 `provider_result_meta`
  - 从 `groundingMetadata.groundingChunks` 规范化生成 `grounding_source_links[]`，覆盖 web source、image source、root `uri/image_uri` 和 retrieved context 样本，便于图片工作室与图片测评展示合规来源链接
  - 不把 base64 写入任务 JSON

## 持久化

Google 返回 inline 图片字节，平台必须走图片字节持久化路径：

1. 先写入 `/assets/oss_staging/...` 本地暂存文件。
2. OSS 已启用时上传 OSS，成功后删除暂存文件并保存 OSS URL。
3. OSS 未启用或上传失败时保存本地回退 URL，`StudioTaskImage.storage_source=local_fallback`，沿用现有重试/过期状态。

## 前端契约

- 设置页新增独立 “Google Gemini API Key” 模块，模块保存按钮独立提交。
- 图片工作室按 schema 渲染 Nano Banana 参数：
  - 比例：`aspect_ratio`
  - 清晰度：`image_size`
  - Search：`google_search_mode`
  - Nano Banana 2 专属：`thinking_level`
- 开发者模式展示 canonical request、provider payload、request id、usage、grounding metadata、raw response；当有 grounding 来源时优先展示 `grounding_source_links[]` 链接。

## 图片测评

- Capabilities 暴露两个 Nano Banana 模型的 `text_to_image` / `image_edit`。
- 测评参数复用模型 schema。
- 单元详情保留 canonical request、provider payload、request id、usage、grounding metadata、`grounding_source_links[]`、raw response 和持久化后的结果 URL。

## 验收

- 后端目标测试通过：
  - `venv/bin/pytest backend/tests/test_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py backend/tests/test_image_benchmark.py -q`
- 前端：
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run lint`
- 有真实 Google Key 时补 smoke：Nano Banana 2 文生图、Nano Banana Pro 图像编辑、Nano Banana 2 grounding。
