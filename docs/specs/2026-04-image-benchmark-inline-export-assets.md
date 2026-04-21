# 图片测评导出内嵌图片资源

## 背景

- 当前图片测评的 `导出 Markdown` 与 `导出 HTML` 都直接写入 OSS URL。
- 一旦 OSS 签名地址过期，导出的报告就会出现图片失效，无法长期归档或离线转发。
- 现有 HTML 还是前端本地拼接，Markdown 由后端渲染，导出行为分散且不可统一治理。

## 目标

- 导出的 Markdown / HTML 在单文件内直接包含图片二进制内容。
- 用户拿到导出文件后，不依赖 OSS URL 仍能打开图片。
- Markdown 与 HTML 统一由后端生成，避免两套渲染逻辑漂移。
- 导出过程中优先尽可能下载原图，只有多次重试后仍失败或 URL 已失效时才回退原 URL。
- 页面在导出期间提供明确加载反馈，并允许用户选择快速导出。

## 非目标

- 不改公开分享页的在线渲染策略。
- 不把导出格式改成 zip 包或多文件目录结构。
- 不保证已经失效、当前无法下载的远程图片一定能恢复。

## 用户流 / 角色

- 用户在图片测评页面完成一次 run 后，点击 `导出 Markdown` 或 `导出 HTML`。
- 后端收集 run 快照中的输入图与输出图 URL，尝试下载并转成 `data:<mime>;base64,...`。
- 如果全部成功，导出的单文件可离线查看。
- 如果部分下载失败，导出仍然成功，但失败图片保留原 URL，前端给出明确提示。
- 用户也可选择“快速导出”，跳过图片下载，直接导出保留 URL 的报告。

## 状态与数据契约

- 输入数据：`ImageBenchmarkRun.dataset_snapshot.items[*].image_slots[*].image.url` 与 `cell_results[*].output_images[*].url`
- 派生数据：导出阶段构建 `原始 URL -> data URI / 原始 URL` 的映射表
- 持久化状态：不新增持久化字段；内嵌资源只存在于导出结果中
- 兼容策略：已是 `data:` URL 的图片直接复用，不重复下载

## API / Schema / 表单约束

- `POST /api/image-benchmark/runs/{run_id}/export-md`
  - 返回 `filename`、`content`、`embedded_image_count`、`fallback_url_count`
- `POST /api/image-benchmark/runs/{run_id}/export-html`
  - 返回 `filename`、`content`、`embedded_image_count`、`fallback_url_count`
- `POST /api/image-benchmark/runs/{run_id}/export-md-file`
  - 返回 `text/markdown` 附件
  - 通过 `Content-Disposition` 下发文件名
  - 通过 `X-Embedded-Image-Count / X-Fallback-Url-Count` 下发统计
- `POST /api/image-benchmark/runs/{run_id}/export-html-file`
  - 返回 `text/html` 附件
  - 通过 `Content-Disposition` 下发文件名
  - 通过 `X-Embedded-Image-Count / X-Fallback-Url-Count` 下发统计
- 两个接口都支持 `inline_images`：
  - `true`：完整导出，尝试内嵌图片
  - `false`：快速导出，保留原 URL
- 失败策略：
  - run 不存在：`404 运行记录不存在`
  - 单张图片下载失败：不终止整体导出，计入 `fallback_url_count`

## 实现边界

- 前端：
  - 两个导出按钮都调用附件下载接口
  - 导出中按钮显示 loading，避免用户误判为无响应
  - 根据 `embedded_image_count / fallback_url_count` 显示成功或降级提示
  - 提供“完整导出”和“快速导出”两种入口
  - 下载实现基于 `fetch + Blob + Content-Disposition`，不再依赖大 JSON 响应
- 后端：
  - 负责下载图片、推断 MIME、转成 data URI
  - 下载采用限流并发和多次重试，优先拿到原图
  - 负责统一渲染 Markdown / HTML
- 不允许前端自行抓取 OSS 再拼接导出，避免 CORS、签名时效和两套逻辑漂移

## 可观测性

- 后端对单张图片内嵌失败写 `warning` 日志，包含 URL 和错误摘要
- 后端对可重试下载失败写重试日志，包含 attempt 次数
- 前端在导出完成后显示“已内嵌多少张 / 多少张回退 URL”
- 前端在导出开始时显示“正在下载并内嵌图片”或“快速导出中”

## 验收标准

- 自动化验证：
  - pytest 覆盖 Markdown 导出返回 data URI
  - pytest 覆盖 HTML 导出返回 data URI
  - pytest 覆盖导出统计字段 `embedded_image_count / fallback_url_count`
  - pytest 覆盖导出下载失败后的自动重试
  - pytest 覆盖 `inline_images=false` 的快速导出
- 手工验证：
  - 导出后的 `.md` 与 `.html` 在断网或 OSS URL 失效后仍可显示已成功内嵌的图片
- 回归关注点：
  - 导出大文件体积上升属于预期
  - 部分图片下载失败时导出不应整体失败

## 文档更新

- `docs/CHANGELOG.md`
- 前后端导出接口类型定义与页面提示文案
