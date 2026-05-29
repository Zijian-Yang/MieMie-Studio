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

## 浏览器验证补充

真实浏览器通过本地 SSH 隧道访问 `http://127.0.0.1:18100/login` 时，曾发现生产 bundle 白屏：

- 页面 title 为 `MieMie Studio`，但 body 无有效文本。
- 控制台先后出现 `Cannot read properties of undefined (reading 'createContext')` 与 `Cannot access 'G' before initialization`。
- 根因定位为 Vite 手动分包过细：React 生态依赖与 Ant Design 子 chunk 存在反向 import，导致生产初始化顺序不稳定。

修复方向：

- React、React Router、Scheduler、Zustand 与 CommonJS helper 归入 `react-vendor`。
- Ant Design 主包统一归入 `antd-vendor`，不再按 `antd/es/{component}` 生成子 chunk。
- 新增 `npm run test:vite-chunks`，断言 AntD 主包保持单 chunk，保留 icons / rc / dayjs / dnd 等独立 vendor 分组。

本地验证：

- `npm run test:vite-chunks`
- `npm run build`
- 构建产物只剩 `antd-vendor-*.js`，未再生成 `antd-button`、`antd-form`、`antd-_util` 等子 chunk。

pre 部署复验：

- 已部署运行版本：`32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`
- `/api/health`：`200`，`redis.ok=true`
- `GET /`：`200`
- 首页 HTML 仅引用 `/_static/antd-vendor-Nuu71fug.js` 这一类 AntD chunk。
- 真实浏览器访问 `/login`：页面不再白屏，`#root` 有有效内容，登录页截图正常。
- 交互验证：点击“立即注册”后出现注册表单与“立即登录”入口。
- 浏览器控制台：error `0`，warn `0`。

2026-05-25 工作室浏览器门禁补充：

- 通过本地 SSH 隧道访问 `miemie-pre`，注册一次性测试用户并创建临时项目，进入图片工作室后任务列表和详情正常渲染，没有长时间全页转圈。
- 首次点击图片工作室时隧道被远端关闭，浏览器记录一次 `Failed to fetch dynamically imported module: /_static/StudioPage-kkK5922i.js`；随后本地 `curl` 也无法连接隧道。重建隧道后同一 chunk 返回 `200`、`content-length=89747`，刷新同一路由后页面恢复正常，判定为 SSH 隧道中断噪声。
- 普通模式下新建图片任务并点击“开始生成”，页面约 3.4 秒内显示“提交中...”；无 key 路径随后进入 `failed / API key 未配置`，任务卡片、详情和错误提示均可见。
- 服务器 API 日志显示本轮浏览器验证窗口内 `/api/studio/preview-payload` 命中数为 `0`，`POST /api/studio/{id}/generate` 返回 `200`，运行态观测耗时约 `235.27ms`。
- 本轮临时项目已通过服务器本机 API 删除。截图保存在本机临时路径 `/private/tmp/miemie-pre-studio-browser-gate-20260525.png` 和 `/private/tmp/miemie-pre-studio-browser-gate-full-20260525.png`，未写入仓库。

2026-05-29 公网反代门禁补充：

- `pre-studio.miemie.co` 修正 DNS 解析后，Cloudflare 公网入口恢复；`GET https://pre-studio.miemie.co/api/health` 返回 `200`，响应包含 `status=ok`、`run_mode=prod`、`serve_frontend=true`、`redis.ok=true`，运行版本仍为 `32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`。
- `GET /` 与 `GET /login` 均返回 `200`；首页 HTML 引用的主入口 `/_static/index-CiWzNZJv.js` 与样式 `/_static/index-CAz34CPn.css` 均返回 `200`。
- aaPanel / Nginx 自定义 `/_static/` 缓存规则已命中：静态资源响应带 `Cache-Control: public, max-age=604800, immutable`，主入口 JS 二次请求观察到 `cf-cache-status: HIT`。
- 真实浏览器访问 `https://pre-studio.miemie.co/login`，登录页可完整渲染，控制台 error/warn 为 `0`；点击“立即注册”后切换到注册表单，未创建用户、未提交敏感数据。
- 截图保存在本机临时路径 `/private/tmp/pre-studio-public-login-loading-20260529.png` 与 `/private/tmp/pre-studio-public-register-20260529.png`，未写入仓库。

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

2026-05-29 S4 公网反代后基线：

- 计划按“两段式 / 保守门禁 / 一次性测试账号项目”执行，先对比服务器本机 `http://127.0.0.1:18100` 与公网 `https://pre-studio.miemie.co` 的只读查询，再执行少量 `preview-payload` 受控提交。
- 四组保守基线均通过：本机只读 P95 `22.58ms` / P99 `47.93ms`，公网只读 P95 `29.99ms` / P99 `77.32ms`；本机 preview P95 `22.79ms` / P99 `30.41ms`，公网 preview P95 `38.33ms` / P99 `86.22ms`。
- 四组 `http_req_failed=0`、checks failed `0`，响应头 `X-Request-ID` 与 `X-Deployment-Version` 均通过检查。
- 本轮未触发真实 DashScope 供应商调用；少量提交仅使用 `/api/video-studio/preview-payload`。测试项目已删除，session 已登出；测试用户未删除，作为低风险残留账号记录。
- 证据见 `docs/reports/artifacts/2026-05-29-s4-public-baseline/README.md`。

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
- 公网域名 `pre-studio.miemie.co` 的 Cloudflare -> aaPanel/Nginx -> `127.0.0.1:18100` 反代门禁通过，可作为下一轮 S4 混合查询基线的真实入口。
- S4 保守基线通过：公网链路相比本机链路有可见但很小的额外延迟，本轮未观察到 5xx 或 header 缺失。
- 无 key 体验路径证明：列表快、提交即时反馈、重复点击被去重、失败状态可见。
- 下一步仍不需要进入 PostgreSQL / SSE；应先基于 S4 混合查询数据判断 JSON 扫描、轮询或状态查询是否成为真实瓶颈。
