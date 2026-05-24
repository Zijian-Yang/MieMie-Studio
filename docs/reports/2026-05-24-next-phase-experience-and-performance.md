# 2026-05-24 下一阶段体验与性能治理报告

## 基本信息

- 范围：仅 `miemie-pre`，不动旧实验服务。
- 目标：在不引入 PostgreSQL / SSE / RabbitMQ / K8s 的前提下，验证现有 Compose + Redis + Celery 路径的体验基线，并补齐轻量性能治理入口。
- 安全边界：本轮不写供应商 key，不做真实供应商并发压测，不记录 token、密码、API key 或真实生成 URL。

## pre 服务器门禁

只读检查结果：

- 服务器仓库 HEAD：`5eb378f6b2dc5a0a73c9679df2267f10384a4e1e`
- 当前运行版本：`/api/health.git_commit=7f736affd91a503dd007580af335b0254f3cceb4`
- `/api/health`：`200`，`redis.configured=true`，`redis.ok=true`
- `GET /`：`200`
- Compose 服务：
  - `miemie-pre-api-1`：Up / healthy
  - `miemie-pre-redis-1`：Up / healthy
  - `miemie-pre-worker-1`：Up
  - `miemie-pre-worker-video-1`：Up
- Celery `inspect ping`：2 nodes online，图片 worker 与 video worker 均返回 `pong`
- Celery `inspect registered`：包含 `studio.generate` 与 `video_studio.generate`

说明：服务器仓库 HEAD 已包含文档归档提交，运行容器仍是 `7f736aff...`。这是预期边界；本轮不重建、不重启。

## 体验 smoke

使用一次性测试用户和临时项目跑无 key 受控路径，结束后删除临时项目。

通过项：

- 项目列表、图片工作室列表、视频工作室列表均 `200`，响应耗时均低于 `5ms`。
- 图片工作室创建任务 `200`，首次生成 `14.0ms` 返回 `generating`。
- 图片工作室重复点击生成：两次均 `200/generating`，复用同一个 attempt，未重复提交。
- 无 key 图片任务最终进入 `failed`，错误可见，不静默卡住。
- 视频工作室创建任务 `10.1ms` 返回 `processing`，`submit_state=submitting`。
- 无 key 视频任务最终进入 `failed`，`submit_state=failed`，`task_ids_count=0`，`video_urls_count=0`，错误可见。
- 临时项目删除 `200`。

证据：

- `docs/reports/artifacts/2026-05-24-next-phase-experience/no-key-experience-smoke-20260524.json`

## 轻量性能治理

本轮新增后端运行态观测：

- 只采样高频运行路径：图片工作室列表/详情/生成、视频工作室列表/详情/状态/创建、图片/视频测评只读查询。
- 日志字段只包含 method、path、status、duration、user id、request id 和脱敏 query。
- query 中 `api_key`、`token`、`password`、`secret`、`authorization` 等字段统一写为 `[redacted]`。
- 不改变公开 API，不新增必需基础设施。

本轮新增 S4 k6 草案：

- `loadtest/k6/s4-mixed-query-generate.js`
- 默认只跑多人查询。
- 少量提交必须显式传入 `MIEMIE_SUBMIT_URL`、`MIEMIE_SUBMIT_BODY` 和 `MIEMIE_SUBMIT_EVERY`。
- 推荐先使用 preview 或无 key 受控失败路径，不做真实供应商并发压测。

## 代码治理

已完成第一刀行为保持型拆分：

- 新增 `frontend/src/services/apiClient.ts`，承载 axios 实例、token 注入、401 清理跳转和统一 `ApiError`。
- `frontend/src/services/api.ts` 保留原有导出面，继续作为业务 API 聚合入口。
- 该拆分不改变调用方 import 路径，不改变接口语义。

后续建议继续拆分：

- `api.ts` 下一刀：按 domain 提取 `studioApi` / `videoStudioApi`，仍从 `api.ts` re-export，先不改页面 import。
- `VideoStudioPage.tsx` 下一刀：优先提取任务展示/状态工具函数，再提取数据加载 hook；不重做 UI。

## 结论

- 当前 `miemie-pre` 运行态基础门禁通过。
- 无 key 体验路径证明：列表快、提交即时反馈、重复点击被去重、失败状态可见。
- 下一步仍不需要进入 PostgreSQL / SSE；应先基于 S4 混合查询数据判断 JSON 扫描、轮询或状态查询是否成为真实瓶颈。
