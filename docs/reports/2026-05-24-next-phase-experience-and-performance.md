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

2026-05-30 W2 阶梯压测 v1：

- 执行计划为 `50 -> 100 -> 200 VU` 只读阶梯，随后 `10 -> 20 -> 30 VU` preview 受控提交阶梯；每档均先本机 `http://127.0.0.1:18100`，再公网 `https://pre-studio.miemie.co`。
- 性能指标达到 W2 v1 保守目标：只读本机 200 VU P95 `18.53ms` / P99 `60.16ms`，公网 200 VU P95 `177.44ms` / P99 `1459.18ms`；preview 本机 30 VU P95 `30.48ms` / P99 `51.33ms`，公网 30 VU P95 `88.89ms` / P99 `1277.13ms`。
- 严格门禁结论为“不完全通过”：`preview-payload` 日志分类显示 `120` 次提交中 `119` 次 `200`、`1` 次 `500`。该 500 出现在 `local-preview-10` 首轮并发提交，traceback 指向 per-user `config.json` 首次初始化写入竞态：`config.tmp -> config.json` 的 `os.replace` 发生 `FileNotFoundError`。
- 压测后测试项目删除 `200`、logout `200`，本机与公网 `/api/health` 均为 `200` 且 `redis.ok=true`，`api`、`redis`、`worker`、`worker-video` 均保持运行。
- 结论：当前单机 Compose 对 W2 平台侧读流量和受控 preview 提交的 P95 性能有明显余量；下一步不应先上 PostgreSQL/SSE/RabbitMQ，而应先修复 per-user config 首次并发写入竞态，并复跑 preview 阶梯确认 5xx 清零。证据见 `docs/reports/artifacts/2026-05-29-w2-staircase-baseline/README.md`。

2026-05-30 W2 preview 阻塞修复与复跑：

- 已修复 per-user `config.json` 首次并发初始化竞态：配置写入临时文件从固定 `config.tmp` 改为 pid/thread/uuid 唯一临时文件，避免多个 worker 进程争用同一个 tmp。
- 本地回归：新增 `backend/tests/test_config_manager.py`，旧实现可复现 `FileNotFoundError`；修复后 `venv/bin/pytest backend/tests -q` 为 `234 passed`。
- 已部署到 `miemie-pre` 运行版本 `26e3824928a6d4deb86c830183e92310400e107e`，Compose config 通过，`api`、`worker`、`worker-video` 重建，Redis 未重建；本机与公网 `/api/health` 均为 `200` 且 `redis.ok=true`。
- 复跑 preview 阶梯 `10/20/30 VU` 本机与公网六档均通过：本机 30 VU P95 `29.89ms` / P99 `52.07ms`，公网 30 VU P95 `71.63ms` / P99 `1429.53ms`。
- 服务端日志分类显示 `POST /api/video-studio/preview-payload` 为 `200 120`，无 4xx/5xx；测试项目删除 `200`，logout `200`。证据见 `docs/reports/artifacts/2026-05-30-w2-preview-config-fix/README.md`。

2026-05-30 W2 状态观察阶梯：

- 本轮创建一次性用户、项目和 1 个无 key 视频任务，只读压测 `/api/projects`、`/api/video-studio?project_id=<id>`、`/api/video-studio/{task_id}` 与 `/api/video-studio/{task_id}/status`，不触发真实 DashScope 生成。
- 本机 `100 VU / 120s` 通过：`23872` 个 GET、失败率 `0`、P95 `17.37ms`、P99 `68.23ms`、check 失败 `0`。
- 公网 `100 VU / 120s` 按保守门禁停止：`19911` 个 GET、失败率 `0.020%`、P95 `138.40ms`、P99 `1603.56ms`，但 k6 记录 4 个 `request timeout`，导致状态码、`X-Request-ID`、`X-Deployment-Version` 三类 check 各失败 4 次。
- API 日志窗口内观察类 GET 状态码汇总为 `200 43785`，未观察到应用 4xx/5xx 放大；问题更像公网入口链路尾部抖动，而不是应用或 Redis/JSON 读路径瓶颈。证据见 `docs/reports/artifacts/2026-05-30-w2-status-observation/README.md`。

2026-05-30 W2 公网链路对照：

- 同一批状态观察 GET 以 `100 VU / 120s` 分别命中应用直连、Nginx 本机源站、Nginx 源站公网 IP 和 Cloudflare 公网域名。
- 应用直连、Nginx 本机源站、Nginx 源站公网 IP 三组均通过：P95 分别为 `22.67ms`、`28.93ms`、`23.63ms`，失败率均为 `0`，check 失败均为 `0`。
- Cloudflare 公网域名复测失败：`17414` 个 GET，失败率 `0.029%`，P95 `409.26ms`，P99 `2119.39ms`，出现 5 个 k6 `request timeout`，触发 15 个响应 check 失败。
- API 日志窗口内观察类 GET 状态码汇总为 `200 88423`；本轮将公网 timeout 收窄到 Cloudflare/公网代理链路，应用、Redis/JSON 读路径和 Nginx 源站不是主要瓶颈。证据见 `docs/reports/artifacts/2026-05-30-w2-link-comparison/README.md`。

2026-05-31 W2 DNS only 状态观察阶梯：

- `pre-studio.miemie.co` 已切到 DNS only，服务器侧解析为 `47.79.99.190`，响应头为 `server: nginx`，未经过 Cloudflare；源站证书链在服务器 curl/k6 环境仍有校验问题，本轮 k6 使用 `insecureSkipTLSVerify: true`，证书链作为独立运维项。
- DNS only 公网 `100 VU / 120s` 通过：`23536` 个 GET、失败率 `0`、P95 `45.92ms`、P99 `215.69ms`、check 失败 `0`。
- DNS only 公网 `300 VU / 120s` 无 4xx/5xx、无 timeout、无 header check 失败：`52000` 个 GET、失败率 `0`、P99 `666.39ms`；但 P95 `307.78ms` 略超 `300ms` 保守门槛，按规则停止，未进入 500 VU。
- API 日志窗口内观察类 GET 状态码汇总为 `200 75537`。证据见 `docs/reports/artifacts/2026-05-31-w2-dns-only-staircase/README.md`。

2026-05-31 W2 Cloudflare 入口复验：

- `pre-studio.miemie.co` 已恢复 Cloudflare 代理，公共 DNS 返回 Cloudflare IP，响应头为 `server: cloudflare`。
- Cloudflare 真实入口 `100 VU / 120s` 复验失败：`18247` 个 GET、失败率 `0.049%`、P95 `207.86ms`、P99 `2554.39ms`，出现 9 个 k6 `request timeout`，导致 27 个响应 check 失败，按规则停止，未进入 300/500。
- API 日志窗口内观察类 GET 状态码汇总为 `200 18253`，未观察到应用 4xx/5xx 放大。证据见 `docs/reports/artifacts/2026-05-31-w2-cloudflare-entry-retune/README.md`。
- 结论：源站能力和 Cloudflare 真实入口应继续分开看；Cloudflare 代理路径仍需按 `/api/*` 规则、HTTP/3/QUIC、WAF/Bot/Rate Limiting 和 Ray ID/源站日志维度继续调优。

2026-06-01 W2 Cloudflare HTTP/3 关闭复验：

- 用户已在 Cloudflare 关闭 `HTTP/3 (with QUIC)`；公网 health 预检仍为 `200`，响应头为 `server: cloudflare`、`cf-cache-status: DYNAMIC`，且不再出现 `alt-svc: h3`。
- Cloudflare 真实入口 `100 VU / 120s` 复验仍未通过：`19448` 个 GET、失败率 `0.0257%`、P95 `190.14ms`、P99 `1702.97ms`，出现 5 个 k6 `request timeout`，导致 15 个响应 check 失败。
- API 日志窗口内观察类 GET 状态码汇总为 `200 19451`；测试视频任务删除 `200`、项目删除 `200`、logout `200`，服务器 `/tmp` token env 已删除，压测后 `/api/health` 仍为 `200` 且容器保持运行。证据见 `docs/reports/artifacts/2026-06-01-w2-cloudflare-http3off/README.md`。
- 结论：关闭 HTTP/3/QUIC 对 Cloudflare 入口有改善，但 timeout 未清零；下一步应优先查 Cloudflare `/api/*` Security Events、WAF、Bot Fight / Super Bot Fight、Rate Limiting、缓存规则命中和 Ray ID，而不是先改应用架构。

2026-06-01 W2 Cloudflare Skip 规则复验：

- 用户按压测来源 IP `47.79.99.190` 与 `/api/*` 部署临时 Skip 规则，跳过 rate limiting、managed rules、Super Bot Fight Mode 与 Browser Integrity Check；公网 health 预检仍为 `200`。
- Cloudflare 真实入口 `100 VU / 120s` 复验仍未通过：`17902` 个 GET、失败率 `0.0838%`、P95 `195.03ms`、P99 `2179.31ms`，出现 15 个 k6 `request timeout`，导致 45 个响应 check 失败。
- API 日志窗口内观察类 GET 状态码汇总为 `200 17906`、`500 1`；1 个 500 traceback 指向 `backend/app/services/storage.py` 的 `_write_json_with_lock()` 固定 `<task_id>.tmp` 在并发 `list_tasks` 保存视频任务时发生 `FileNotFoundError`。证据见 `docs/reports/artifacts/2026-06-01-w2-cloudflare-skip-rule/README.md`。
- 结论：临时 Skip 规则不是 Cloudflare timeout 的解法；应暂停或删除该临时规则。下一步先修复 StorageService 通用 JSON 写入的固定 tmp 文件竞态，再复跑入口对照，避免应用 500 与 Cloudflare timeout 混在一起判断。

2026-06-01 StorageService 修复部署与 Cloudflare 复跑：

- 已修复 `StorageService._write_json_with_lock()` 固定 `<name>.tmp` 竞态：通用 JSON 写入临时文件改为 pid/thread/uuid 唯一路径；本地按 TDD 确认旧实现复现 `FileNotFoundError`，修复后 `venv/bin/pytest backend/tests -q` 为 `235 passed`。
- 已部署到 `miemie-pre` 运行版本 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`，Compose config 通过，`api`、`worker`、`worker-video` 重建，Redis 未重建；容器内 `pytest backend/tests/test_storage_service.py backend/tests/test_config_manager.py -q` 为 `2 passed`。
- Cloudflare 真实入口 `100 VU / 120s` 复跑仍未通过：`19256` 个 GET、失败率 `0.0364%`、P95 `170.64ms`、P99 `1978.19ms`，出现 7 个 k6 `request timeout`，导致 21 个响应 check 失败。
- API 日志窗口内观察类 GET 状态码汇总为 `200 19263`，未再出现应用 500；测试视频任务删除 `200`、项目删除 `200`、logout `200`，服务器 `/tmp` token env 已删除，压测后 `/api/health` 仍为 `200` 且容器保持运行。证据见 `docs/reports/artifacts/2026-06-01-w2-storage-fix-cloudflare-rerun/README.md`。
- 结论：应用侧 JSON 写入竞态已解除；Cloudflare/公网边缘链路 timeout 仍独立存在，下一步继续聚焦 Cloudflare 入口尾部 timeout。

2026-06-03 W2 Cloudflare Ray 诊断：

- Cloudflare 临时 Skip 规则已关闭，运行版本仍为 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`；本轮使用带 `cf-ray` / timings 采样的诊断脚本，只记录 `>=800ms` 慢请求和失败请求。
- Cloudflare `100 VU / 120s` 通过：`23060` 个 GET、失败率 `0`、P95 `36.75ms`、P99 `187.71ms`、check 失败 `0`；API 侧观察类 GET 汇总为 `200 23061`。
- 因 100 VU 通过，继续进入 Cloudflare `300 VU / 120s`；该档无 timeout、无 check 失败、API 侧观察类 GET 汇总为 `200 49577`，但 P95 `351.64ms` 超过 `300ms` 保守门槛，按规则停止，未进入 500 VU。
- 两档慢/失败样本 `sample_count=0`，说明本轮没有 `>=800ms` 慢请求或失败响应；300 VU P95 超标更像较多请求落在 `300-715ms` 区间，而不是少量尖刺。证据见 `docs/reports/artifacts/2026-06-03-w2-cloudflare-ray-diagnostics/README.md`。
- 结论：Cloudflare 入口当前 100 VU 门禁已恢复通过；300 VU 稳定性通过但 P95 超标。下一步应做同时间窗口的 300 VU 本机 / Nginx 源站 / Cloudflare 对照，定位 300 VU 尾部延迟来源。

2026-06-03 W2 300 VU 入口对照：

- 同一批一次性用户、项目和无 key 视频任务，分别跑应用直连、本机 Nginx、源站公网 IP forced 和 Cloudflare 真实入口 `300 VU / 120s` 状态观察读路径。
- 应用直连和本机 Nginx 均通过 W2 读路径门槛：app direct P95 `244.29ms` / P99 `489.41ms`，Nginx local P95 `271.69ms` / P99 `610.00ms`，失败率均为 `0`，check failed 均为 `0`。
- 源站公网 IP forced 路径失败率 `0`、check failed `0`，但 P95 `325.81ms` 略超 `300ms`；Cloudflare 真实入口 P95 `512.92ms`、P99 `914.13ms`，失败率 `0.0020%`，出现 1 个 `dial: i/o timeout`，导致 3 个响应 check 失败。
- API 日志窗口内状态码汇总为 `200 217076`，未观察到应用 4xx/5xx；测试任务、项目和 session 均清理成功，压测后 health 与 Compose 仍健康。证据见 `docs/reports/artifacts/2026-06-03-w2-300-entry-comparison/README.md`。
- 结论：应用直连与本机 Nginx 在 300 VU 下仍能过保守门槛；源站公网路径已有小幅尾延迟，Cloudflare 真实入口进一步放大。下一步应优先做 Cloudflare/公网边缘路径调优和压测来源位置对照，而不是先上 PostgreSQL / SSE / RabbitMQ。

2026-06-03 W2 本地客户端 Cloudflare 入口复测：

- 本机安装 `k6 v2.0.0 (darwin/arm64)` 后，从本地 Mac 对 `https://pre-studio.miemie.co` 执行客户端侧状态观察复测；计划按 `100 -> 200 -> 300 VU` 递进。
- 预检显示当前本机并非直连 Cloudflare：`dig` 返回 `198.18.2.211`，`route` 走 `utun1024`，判定为 Clash Verge TUN / fake-ip 路径。
- Clash TUN 路径下 `100 VU / 120s` 失败率 `0`、check failed `0`，但 P95 `925.75ms`、P99 `1671.47ms`，按门禁停止，未进入 200/300 VU。
- 慢样本 `813` 个，Cloudflare colo 分布为 `LAX 503`、`SJC 310`；服务器 API 同窗口观察类 GET 状态码为 `200 11169`，未观察到应用 4xx/5xx。证据见 `docs/reports/artifacts/2026-06-03-w2-client-cloudflare-baseline/README.md`。
- 结论：本轮只能代表“本地 Mac + Clash TUN 代理出口 -> Cloudflare”，不能代表普通用户直连。下一步需要在 Clash 为 `pre-studio.miemie.co` 配置 DIRECT 或临时关闭 TUN/fake-ip 后，复跑直连客户端侧样本。

2026-06-04 W2 本地客户端 Cloudflare DIRECT 规则复测：

- 用户已在 Clash Verge 为 `pre-studio.miemie.co` 添加 domain DIRECT 规则；复测预检仍显示 `dig` 返回 `198.18.2.211`，`route` 走 `utun1024`，说明当前 TUN/fake-ip 仍在系统层接管该域名。
- Cloudflare 入口 `100 VU / 120s` 仍未通过：`10524` 个 GET、失败率 `0.019%`、P95 `969.79ms`、P99 `1401.50ms`，出现 2 个失败请求并导致 6 个响应 check 失败，按规则停止，未进入 200/300 VU。
- 慢样本 `1038` 个，Cloudflare colo 主要为 `DEN`；服务器 API 同窗口观察类 GET 状态码汇总为 `200 10523`，未观察到应用 4xx/5xx 放大。证据见 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-direct-rule/README.md`。
- 结论：当前 Clash DIRECT 规则没有形成干净直连样本，也没有改善客户端侧 P95；下一步若要继续验证本地直连 Cloudflare，需要临时关闭 Clash TUN/fake-ip 或使用另一条不经 Clash 的客户端网络。

2026-06-04 W2 本地客户端 Cloudflare 干净直连复测：

- 用户关闭 Clash TUN/fake-ip 后，保护性预检显示 DNS 为 Cloudflare 真实 IP `172.67.201.59` / `104.21.85.29`，route 走 `en0`，public health 为 `200`，本轮可作为干净的本地客户端直连 Cloudflare 样本。
- Cloudflare 入口 `100 VU / 120s` 失败率 `0`、check failed `0`，但 P95 `734.57ms`、P99 `1080.36ms`，按原始 W2 读路径 `300ms` 保守门槛停止，未进入 200/300 VU。
- 慢样本 `505` 个，Cloudflare colo 分布为 `LAX 367`、`SJC 138`；服务器 API 同窗口观察类 GET 状态码汇总为 `200 12685`，未观察到应用 4xx/5xx。证据见 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-clean-direct/README.md`。
- 用户补充该网站不关注大陆访问效果；因此本地大陆/跨境客户端直连 Cloudflare 的 P95 不作为目标市场硬门禁，只作为跨境访问风险记录。后续 W2 判断应优先补非大陆客户端/VPS vantage，或继续以服务器侧入口对照作为平台承载依据。

2026-06-04 W2 本地客户端 Cloudflare 美国代理样本：

- 用户确认可用本机 TUN 美国代理做阶段收尾参考；本轮路径为本地 Mac -> Clash 美国代理节点 -> Cloudflare -> 源站，预检显示 fake-ip `198.18.2.211`、route 走 `utun1024`，Cloudflare colo 为 `DEN`。
- 最新有效 Cloudflare 入口 `100 VU / 120s` 失败率 `0`、check failed `0`，但 P95 `960.63ms`、P99 `1315.98ms`，按原始 W2 读路径 `300ms` 保守门槛停止，未进入 200/300 VU。
- 慢样本 `1173` 个，Cloudflare colo 均为 `DEN`；服务器 API 同窗口观察类 GET 状态码汇总为 `200 11159`，未观察到应用 4xx/5xx。证据见 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-us-proxy/README.md`。
- 结论：美国代理样本稳定性通过但尾延迟高，且代理链路不是目标地区 VPS 原生网络；它不改变 W2 平台侧结论。若需要目标市场入口 SLO，应后续从美国或目标地区 VPS 直接跑 k6。

## 代码治理

已完成第一刀行为保持型拆分：

- 新增 `frontend/src/services/apiClient.ts`，承载 axios 实例、token 注入、401 清理跳转和统一 `ApiError`。
- `frontend/src/services/api.ts` 保留原有导出面，继续作为业务 API 聚合入口。
- 该拆分不改变调用方 import 路径，不改变接口语义。

2026-06-04 阶段 6A 服务层拆分：

- 新增 `frontend/src/services/studioApi.ts`，承载图片工作室类型与 `studioApi`；`api.ts` 继续 re-export，页面 import 路径不变。
- 新增 `frontend/src/services/videoStudioApi.ts`，承载视频工作室 capability / task 类型与 `videoStudioApi`；`api.ts` 保留 type-only re-export，并仅用 type-only import 支撑视频测评 capability 类型。
- `frontend/src/services/api.ts` 从约 `2851` 行降至约 `2260` 行；不改变后端接口、请求体、响应体、页面行为或 UI。

2026-06-04 阶段 6B 视频工作室页面拆分第一刀：

- 新增 `frontend/src/pages/VideoStudio/taskViewUtils.ts`，承载任务类型元数据、历史任务类型归一化、输入素材归一化、参数摘要、参数展示项和预览图选择等纯工具函数。
- `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 从约 `3972` 行降至约 `3846` 行；页面继续保留 JSX 标签渲染、状态编排和用户交互，不改变 UI 行为。
- 本刀只建立任务展示工具边界，不拆数据加载 hook、轮询通知或任务列表/详情组件。

2026-06-04 阶段 6B 视频工作室页面拆分第二刀：

- 新增 `frontend/src/pages/VideoStudio/useVideoStudioData.ts`，承载任务列表、图库/音频库/视频库数据、模型配置占位状态、初始加载、处理中任务轮询启动和完成通知去重。
- `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 从约 `3846` 行降至约 `3744` 行；页面继续保留创建/编辑表单、详情弹窗、任务操作和 UI 编排。
- 本刀不改变 API URL、请求体、响应体、轮询间隔、任务完成提示或用户可见交互。

2026-06-04 阶段 6B 视频工作室页面拆分第三刀：

- 新增 `frontend/src/pages/VideoStudio/TaskListPanel.tsx`，承载视频工作室顶部任务列表卡片、空状态、新建入口、批量删除入口、任务缩略图、状态标签和单任务查看/删除动作。
- `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 从约 `3744` 行降至约 `3644` 行；页面继续负责数据、表单、详情弹窗和任务操作回调。
- 本刀不改变任务列表布局、标签、进度展示、确认删除行为或卡片点击行为。

2026-06-04 阶段 6B 视频工作室页面拆分第四刀：

- 新增 `frontend/src/pages/VideoStudio/TaskDetailModal.tsx`，承载任务详情弹窗标题、编辑/重生成入口、输入素材展示、关键参数、任务状态、生成结果、标记按钮、保存到视频库、保存尾帧、提示词和开发者模式展示。
- `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 从约 `3644` 行降至约 `3345` 行；页面继续负责选中任务、数据状态、创建/编辑表单和任务操作回调。
- 本刀不改变详情弹窗宽度、按钮文案、标记逻辑、保存动作、开发者模式内容或用户可见交互。

2026-06-04 阶段 6B 视频工作室页面拆分第五刀：

- 新增 `frontend/src/pages/VideoStudio/useVideoStudioTaskActions.ts`，承载保存到视频库、提取尾帧、视频标记、单任务删除、全部删除和重新生成动作，以及 `extractingFrames` / `regenerating` 操作状态。
- `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 从约 `3345` 行降至约 `3277` 行；页面剩余 `videoStudioApi` 调用收窄到源视频准备、Mask 上传、创建任务和编辑保存等表单路径。
- 本刀不改变删除确认、保存提示、尾帧提取 loading、视频标记更新、重新生成轮询启动或用户可见交互。

2026-06-05 视频工作室 smoke 补强：

- `frontend/e2e/smoke.spec.ts` 新增 mock 成功任务，覆盖 `TaskListPanel` 和 `TaskDetailModal` 的主要渲染路径：任务卡片、任务类型、Provider、状态、进度、详情弹窗、输入素材、关键参数、生成结果、提示词、编辑/重生成、保存到视频库、保存尾帧和开发者模式入口。
- `npm run test:e2e` 从 4 个 smoke 扩展到 5 个 smoke，全部通过。
- 本 smoke 不触发真实供应商调用，不改变后端接口或页面行为。

2026-06-05 项目列表 smoke 补强：

- `frontend/e2e/smoke.spec.ts` 新增项目列表样本，mock `/api/projects` 返回一个带分镜和角色统计的项目，覆盖登录态进入 `/projects`、项目卡片、描述、分镜数、角色数和打开/删除入口。
- `npm run test:e2e` 从 5 个 smoke 扩展到 6 个 smoke，全部通过。
- 本 smoke 只验证现有列表渲染，不触发真实项目创建、删除或供应商调用。

2026-06-05 视频工作室创建流程 smoke 补强：

- `frontend/e2e/smoke.spec.ts` 新增最小文生视频能力 mock，覆盖 `/api/video-studio/capabilities`、`/api/video-studio/preview-payload` 与 `POST /api/video-studio`，验证新建任务弹窗、文生视频 tab、任务名称、提示词、创建成功消息和新任务卡片回显。
- `npm run test:e2e` 从 6 个 smoke 扩展到 7 个 smoke，全部通过。
- 本 smoke 返回本地 mock `pending` 任务，不触发真实供应商调用，不启动后台轮询。

2026-06-05 阶段 6B 视频工作室页面拆分第六刀：

- 删除 `frontend/src/pages/VideoStudio/VideoStudioPage.tsx` 内两个 `{false && ...}` 包裹的旧创建/编辑弹窗，以及只服务这些不可达弹窗的旧状态、旧 handler、Mask 处理和旧模型分支引用。
- `VideoStudioPage.tsx` 从约 `3277` 行降至 `152` 行；当前创建/编辑继续统一挂载 `CapabilityCreateModal`，详情继续走 `TaskDetailModal`，列表继续走 `TaskListPanel`。
- 本刀不改变用户可见创建/编辑入口、任务详情操作、轮询启动或 API 语义；价值是移除不可达代码，避免后续拆分误碰旧路径。

2026-06-06 阶段 6B 视频工作室创建/编辑弹窗拆分第一刀：

- 新增 `frontend/src/pages/VideoStudio/DeveloperPreviewPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出开发者模式提交状态、canonical 请求体、厂商请求体和 validation warning 展示。
- `CapabilityCreateModal.tsx` 从 `1730` 行降至 `1706` 行；新面板为纯展示组件，不持有 API 调用、表单状态或副作用。
- 本刀不改变 preview payload 的生成时机、开发者模式折叠面板文案、warning 显示、请求体格式或提交行为。

2026-06-06 阶段 6B 视频工作室创建/编辑弹窗拆分第二刀：

- 新增 `frontend/src/pages/VideoStudio/VideoFieldLabel.tsx`，收敛素材、Mask 和提示词区域共用的字段标题、必填星号和 hover 帮助入口。
- `CapabilityCreateModal.tsx` 从 `1706` 行降至 `1698` 行；新组件为纯展示组件，不持有表单状态、素材状态或副作用。
- 本刀不改变字段文案、必填星号、帮助弹层内容或任一素材选择行为。

2026-06-06 阶段 6B 视频工作室创建/编辑弹窗拆分第三刀：

- 新增 `frontend/src/pages/VideoStudio/ReferenceCollectionsPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出参考图片/视频选择、已选参考素材、参考音色、顺序调整、删除和指代词按钮挂载。
- `CapabilityCreateModal.tsx` 从 `1698` 行降至 `1499` 行；新组件为受控 UI 组件，状态、提交 payload、preview payload 和 API 调用仍由父组件持有。
- `frontend/e2e/smoke.spec.ts` 新增参考素材创建流程样本，mock `wan2.7-r2v` 能力、图库参考图、preview payload 与创建提交，断言 `reference_media` 请求体；`npm run test:e2e` 扩展到 8 个 smoke。
- 本刀不改变参考素材数量限制、已选素材展示、参考音色选择、指代词插入、提交校验或任一后端接口语义。

2026-06-06 阶段 6B 视频工作室创建/编辑弹窗拆分第四刀：

- 新增 `frontend/src/pages/VideoStudio/MaskEditorPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出局部编辑 Mask 展示、工具按钮、警告、编辑模式复用提示和 `SourceVideoMetadata` 纯类型。
- `CapabilityCreateModal.tsx` 从 `1499` 行降至 `1434` 行；新面板为受控 UI 组件，源视频准备、Mask 上传、提交校验和 API 调用仍由父组件持有。
- `frontend/e2e/smoke.spec.ts` 新增局部编辑源视频/Mask 面板样本，mock `video_edit_local` 能力、视频库源视频和 `prepare-source-video`，覆盖源视频选择后元数据与 Mask 面板出现；`npm run test:e2e` 扩展到 9 个 smoke。
- 本刀不改变 Mask 绘制工具、Mask 导出、上传接口、局部编辑校验或源视频准备接口语义。

2026-06-06 阶段 6B 视频工作室创建/编辑弹窗拆分第五刀：

- 新增 `frontend/src/pages/VideoStudio/InputAssetSelector.tsx`，从 `CapabilityCreateModal.tsx` 拆出首帧、尾帧、音频、首段视频、待编辑视频和源视频选择器。
- `CapabilityCreateModal.tsx` 从 `1434` 行降至 `1306` 行；新组件为受控 UI 组件，素材状态、源视频准备回调、preview payload 和提交逻辑仍由父组件持有。
- 本刀不改变素材选择控件、可选/必填标记、源视频准备触发时机、元数据展示或任一后端接口语义；继续由 9 个前端 smoke 覆盖文生、参考素材和局部编辑入口。

2026-06-06 阶段 7 数据库前架构检查点：

- 新增 `docs/adr/ADR-0003-pre-database-architecture-checkpoint.md`，沉淀阶段 5/6 后的数据库前初版检查点：先进入设计准备，避免一次性全量替换 JSON。
- ADR 明确进入 SQLite/PostgreSQL 实施前的触发条件：本机入口也出现明确 JSON I/O 瓶颈、业务确认跨主机多实例核心状态需求，或用户接受数据库备份/迁移/监控成本。
- ADR 同步列出数据库阶段准备包：数据域清单、迁移顺序、回滚策略、备份恢复、性能门禁和 SSE 关系。

2026-06-06 阶段 7 Compose PostgreSQL 升级路线确认：

- 用户确认数据库部署形态选择 Compose 内 PostgreSQL，不走 SQLite 中转；JSON 可作为主数据源保留一段过渡期，但最终核心业务状态全部迁入数据库。
- 新增 `docs/plans/2026-06-06-postgres-upgrade-optimization-plan.md`，覆盖 Compose PostgreSQL、运行开关、数据域迁移顺序、任务索引首迁、双写/回填/对账、读切换、回滚、备份恢复和性能门禁。
- `ADR-0003` 状态更新为 Accepted，并把第一实施刀收敛为 PostgreSQL Compose 基础设施与 health 观测；第一业务迁移域建议为视频工作室任务索引/任务状态。

2026-06-07 阶段 7 PostgreSQL 执行路线与 preflight：

- 新增 `docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md`，将数据库升级拆为 R0 preflight、R1 Compose PostgreSQL 基础设施、R2 database health/备份恢复、R3 Alembic/schema、R4-R6 视频工作室任务 shadow/dual-write/read-switch、R7-R8 服务器 rollout 与性能/真实 smoke 门禁。
- preflight artifact 已归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/`：本地 Docker/Compose/Python/pytest/Node/npm/k6 均可用，`docker compose config`、后端关键测试、前端 typecheck 和 vite chunk 检查通过；服务器 SSH、`miemie-pre` Compose、`/api/health`、Cloudflare health 均通过。
- 服务器当前运行提交仍为 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`，`api`、`redis`、`worker`、`worker-video` 均运行；已预拉取 `postgres:16-alpine` 并验证镜像可执行，后续 R1 不再需要等待镜像下载。
- 观察到服务器无 swap、可用内存约 `994MiB`，R1/R2 必须保守配置 PostgreSQL 并持续观察 `docker stats`；本地 Mac 对公网 health 的路由仍经 Clash TUN/fake-ip，继续只作为客户端路径变量记录，不作为服务器 rollout 阻塞。

2026-06-07 阶段 7 R1/R2 本地实现：

- Compose 已新增 `postgres:16-alpine` service、`postgres_data` volume 和小内存保守参数，`api`、`worker`、`worker-video` 仅接收数据库开关环境变量，不新增 `depends_on: postgres`；默认 `MIEMIE_DATABASE_ENABLED=false`，业务读写仍为 JSON。
- 后端新增 `backend/app/db/engine.py`，以懒连接方式提供 `database_health()`，`/api/health` 新增 `database` 字段；关闭数据库时返回 `{"configured": false, "ok": null}`，开启但缺失/错误 URL 时返回明确错误且不泄露密码。
- 新增 `scripts/postgres_backup.sh` 与 `scripts/postgres_restore_rehearsal.sh`，恢复演练使用临时库 `miemie_restore_check`，不覆盖生产库；`backend/backups/` 已加入 `.gitignore`。
- 本地验证：`docker compose config`、带 `MIEMIE_POSTGRES_PASSWORD` 的 Compose config、数据库 health 测试、后端全量 `238 passed`、前端 typecheck、vite chunk 检查和生产 build 均通过。因本机 Docker daemon 未运行，`docker compose up -d postgres` 与本机 `pg_isready` 未在本地验证，服务器 rollout 需补齐。

2026-06-07 阶段 7 R1/R2 staging rollout 进行中：

- 服务器已从 `00091f21f5ee207f78a1092e7e5e164ab4567c7f` fast-forward 到 `cb2d4ff0f5e00d2eb7fbb84a6b411408014107f0`，并在未跟踪 `compose.env` 中写入 PostgreSQL 强密码、保守参数和 `MIEMIE_DATABASE_ENABLED=false`，未打印秘密。
- 服务器 `docker compose config` 已通过，随后执行 `docker compose up -d --build postgres api worker worker-video`；构建过程中 SSH 被远端断开。
- 断开后，本机到服务器的 SSH banner 多次超时，源站 TCP/HTTP 检查受本机 Clash TUN/路由状态影响不稳定；因此 staging R1/R2 尚未闭环，artifact 记录为 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r1-r2-staging/` 的 `in_progress`。
- 恢复 SSH 后必须先检查 Compose 状态和 health，必要时优先恢复 JSON 默认路径，再补 `postgres`、`pg_isready`、`/api/health.database`、备份和恢复演练。

2026-06-07 阶段 7 R3 本地 schema：

- 新增 Alembic 配置、`video_studio_tasks` SQLAlchemy metadata、首个 migration 和 schema 测试；表设计包含任务查询索引字段、JSONB provider/input/result 字段，以及 `raw_task_snapshot`，用于 shadow/backfill 阶段无损保存现有 Pydantic 任务结构。
- `video_studio_tasks` 索引覆盖 `(user_id, project_id, updated_at DESC)`、`(user_id, status, updated_at DESC)` 和 `submit_attempt_id`，前两者均过滤 `deleted_at IS NULL`。
- 本地验证：schema 测试 `3 passed`、数据库 health 测试 `3 passed`、R3 targeted 后端测试 `7 passed`、Alembic offline SQL 生成通过、`docker compose config` 通过、`git diff --check` 通过。
- live `alembic upgrade head` 尚未执行；原因是本地 Docker daemon 不可用，且 R1/R2 staging build 后 SSH/health 仍未恢复到可验证状态。后续必须先收口服务器 R1/R2，再在 Compose 网络内执行 migration。

2026-06-07 阶段 7 R4 本地 repository boundary：

- 新增 `backend/app/repositories/base.py` 与 `backend/app/repositories/video_studio_tasks.py`，为视频工作室任务建立 `save/get/list_for_project/list_all/delete/mark_deleted` 仓储协议。
- 新增 file repository adapter，默认继续包装现有 `StorageService` JSON 读写，排序和保存更新时间语义保持不变；当前路由和 worker 尚未接入 repository，因此运行态仍是 JSON/file-only。
- 新增 PostgreSQL 行映射和 repository skeleton：常用查询字段进入索引列，完整 Pydantic 任务保存在 `raw_task_snapshot`，PostgreSQL 删除路径采用 `deleted_at` 软删除。
- 新增 dual repository wrapper：先写 JSON primary，再写 PostgreSQL shadow；shadow 写失败在非 strict 模式不打断 JSON 主路径，为后续 R5 dual-write feature flag 做准备。
- 本地验证：repository 测试 `4 passed`，repository/schema/health 目标集 `10 passed`，后端全量 `245 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r4-local-repository/`。

2026-06-07 阶段 7 R5 本地 backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_video_studio_tasks.py`，扫描 `backend/data/users/<user_id>/video_studio/*.json`，通过 per-user repository factory upsert 到 PostgreSQL repository；坏 JSON 会进入摘要失败项，不中断其它任务。
- 新增 `backend/app/services/migration/reconcile_video_studio_tasks.py`，对比 JSON 与 PostgreSQL shadow 的计数、ID、`project_id`、`status`、`updated_at`、`submit_attempt_id`，并生成脱敏 JSON/Markdown 摘要。
- 新增 `scripts/postgres_backfill_video_studio_tasks.py` 与 `scripts/postgres_reconcile_video_studio_tasks.py`，使用 `MIEMIE_DATABASE_URL` 创建维护用 SQLAlchemy engine，再装配 `PostgresVideoStudioTaskRepository`；脚本默认输出到 R5 artifact 目录。
- 隐私边界：摘要不包含 prompt body、raw provider payload、token、password、API key 或私有 URL；单元测试显式覆盖这些内容不会进入 summary/Markdown。
- 本地验证：migration 测试 `3 passed`，migration/repository/schema/health 目标集 `13 passed`，脚本 `py_compile` 通过，`git diff --check` 通过，后端全量 `248 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r5-backfill-reconcile/`。

2026-06-07 阶段 7 R6 runtime dual-write feature flag：

- 新增 `backend/app/repositories/video_studio_task_runtime.py`，集中处理 `video_studio_tasks` 双写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` 包含 `video_studio_tasks` 或 `MIEMIE_DATABASE_WRITE_MODE=dual` 时才懒加载 PostgreSQL engine。
- `StorageService` 新增 `owner_user_id`，`get_user_storage(user_id)` 创建的用户专属存储会携带用户 ID，后台 worker 不依赖当前请求 context 也能写入正确 PostgreSQL user namespace。
- `save_video_studio_task()` 保持 JSON 主写，JSON 成功后 shadow save PostgreSQL；`delete_video_studio_task()` 保持 JSON 删除，随后 shadow mark deleted。非 strict 模式下 PostgreSQL shadow 失败只记录 warning，不打断 JSON 主路径。
- 运行态默认仍为 file-only；读路径未切 PostgreSQL，公开 API 响应形状未改。服务器启用双写必须等待 live migration、backfill、reconcile 干净后再设置 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=video_studio_tasks`。
- 本地验证：dual-write 测试 `3 passed`，dual-write/repository/migration/schema/health/storage 目标集 `17 passed`，`git diff --check` 通过，后端全量 `251 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-runtime-dual-write/`。

2026-06-07 阶段 7 R6 read switch + JSON fallback：

- `backend/app/repositories/video_studio_task_runtime.py` 新增读开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_READ_DOMAINS` 包含 `video_studio_tasks` 或 `MIEMIE_DATABASE_READ_MODE=postgres` 时才优先读 PostgreSQL。
- `StorageService.get_video_studio_task()`、`get_video_studio_tasks()`、`get_all_video_studio_tasks()` 改为通过读开关 helper；默认继续读取 JSON，开启后优先读 PostgreSQL repository。
- 当 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，单任务 PostgreSQL miss/异常会回退 JSON；项目列表和全量列表在 PostgreSQL 返回空或异常时回退 JSON。关闭 fallback 时 PostgreSQL 异常会向上抛出，便于严格门禁。
- 运行态默认仍为 file-only；公开 API 响应形状仍返回 `VideoStudioTask`，未启用 PostgreSQL primary 和 JSON archive。
- 本地验证：read-switch 测试 `4 passed`，read-switch/dual-write/repository/migration/schema/health/storage/video-studio-capabilities 目标集 `78 passed`，`git diff --check` 通过，后端全量 `255 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-read-switch/`。

2026-06-07 阶段 7 R6 PostgreSQL primary write + JSON archive mirror：

- `backend/app/repositories/video_studio_task_runtime.py` 新增主写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` 包含 `video_studio_tasks` 或 `MIEMIE_DATABASE_WRITE_MODE=postgres_primary` 时，视频任务保存/删除才以 PostgreSQL 为主。
- `StorageService.save_video_studio_task()` 在进入主写、双写或 JSON 分支前统一刷新 `updated_at`；主写成功后默认不写 JSON，只有 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时才维护 JSON archive mirror。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免数据库主写阶段产生“PG 失败但 JSON 成功”的分叉状态；删除路径同样先写 PostgreSQL，再按 archive 开关清理 JSON。
- Compose/API/worker/worker-video 环境变量已补齐 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` 与 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES`；运行态默认仍为 file-only，服务器 primary-write 仍需等 live migration/backfill/reconcile/dual-write/read-switch 证据干净后再启用。
- 本地验证：primary-write 测试 `4 passed`，primary-write/read-switch/dual-write/repository/migration/schema/health/storage/video-studio-capabilities 目标集 `82 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r6-postgres-primary-write/`。

2026-06-07 阶段 7 R7 staging precheck：

- 本轮只做服务器入口预检，未修改服务器文件、Compose env、数据库开关或容器。
- SSH 短命令出现 `Connection closed` / `Connection timed out during banner exchange`；公网 `/api/health` 20 秒无响应。
- 网络诊断显示本机 DNS/路由仍被 Clash TUN/fake-ip 接管：`pre-studio.miemie.co` 解析到 `198.18.2.211`，`47.79.99.190` 路由走 `utun1024`；同时 TCP 22/443 connect 成功，说明本次不能证明源站或应用已宕机。
- R7 live rollout 暂停在预检阶段；下一步先恢复 SSH banner 和公网 health 的稳定路径，再继续 PostgreSQL container health、backup/restore、live migration、backfill/reconcile 和分阶段开关。
- 证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r7-staging-precheck/`。

2026-06-07 阶段 7 R8 studio_tasks 本地 schema/repository：

- 在 staging 入口仍受本机 TUN/fake-ip 阻塞时，继续推进下一本地域：图片工作室 `studio_tasks`。
- 新增 `backend/app/db/schema/studio_tasks.py` 与 Alembic migration `20260607_0002_studio_tasks`，复用“索引列 + `raw_task_snapshot` JSONB”的过渡模式；migration head 更新为 `20260607_0002`。
- 新增 `StudioTaskRepository` 协议和 `backend/app/repositories/studio_tasks.py`，包含 file/PostgreSQL/dual repository；当前运行态仍默认 JSON/file-only，业务读写尚未接入。
- 索引遵循活动任务 partial index：`(user_id, project_id, updated_at desc)` 和 `(user_id, status, updated_at desc)` 均过滤 `deleted_at is null`，优先覆盖列表和状态扫描。
- 本地验证：新增 schema/repository 测试 `7 passed`，数据库相关目标集 `86 passed`，后端全量 `266 passed`，Alembic head、Compose config 和 `git diff --check` 均通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r8-studio-tasks-local-schema-repository/`。

2026-06-07 阶段 7 R9 studio_tasks backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_studio_tasks.py`，扫描 `backend/data/users/<user_id>/studio/*.json`，按用户装配 repository factory 并 upsert 到 PostgreSQL repository。
- 新增 `backend/app/services/migration/reconcile_studio_tasks.py`，对比 JSON 与 PostgreSQL shadow 的计数、ID、`project_id`、`status`、`updated_at`、`last_task_id`，并生成脱敏 JSON/Markdown 摘要。
- 新增 `scripts/postgres_backfill_studio_tasks.py` 与 `scripts/postgres_reconcile_studio_tasks.py`；脚本默认输出到 R9 artifact 目录。
- 隐私边界：摘要不包含 prompt body、raw provider payload、token、password、API key 或私有 URL；单元测试显式覆盖这些内容不会进入 summary/Markdown。
- 本地验证：migration 测试 `3 passed`，studio/video 数据库迁移目标集 `23 passed`，脚本 `py_compile` 通过，`git diff --check` 通过，后端全量 `269 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r9-studio-tasks-backfill-reconcile/`。

2026-06-07 阶段 7 R10 studio_tasks runtime dual-write：

- 新增 `backend/app/repositories/studio_task_runtime.py`，集中处理 `studio_tasks` 双写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` 包含 `studio_tasks` 或 `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write` 时才懒加载 PostgreSQL engine。
- `StorageService.save_studio_task()` 保持 JSON 主写，JSON 成功后 shadow save PostgreSQL；`delete_studio_task()` 保持 JSON 删除，随后 shadow mark deleted。
- 非 strict 模式下 PostgreSQL shadow 失败只记录 warning，不打断 JSON 主路径；strict 模式可用于后续对账门禁。
- 运行态默认仍为 file-only；读路径未切 PostgreSQL，公开 API 响应形状未改。服务器启用双写必须等待 live migration、backfill、reconcile 干净后再设置 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=studio_tasks`。
- 本地验证：dual-write 测试 `3 passed`，studio/video/storage/studio-capabilities 目标集 `79 passed`，`py_compile`、`git diff --check`、`docker compose config` 均通过，后端全量 `272 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r10-studio-tasks-runtime-dual-write/`。

2026-06-07 阶段 7 R11 studio_tasks read switch + JSON fallback：

- `backend/app/repositories/studio_task_runtime.py` 新增读开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_READ_DOMAINS` 包含 `studio_tasks` 或 `MIEMIE_DATABASE_READ_MODE=postgres` 时才优先读 PostgreSQL。
- `StorageService.get_studio_task()` 与 `get_studio_tasks_by_project()` 改为通过读开关 helper；默认继续读取 JSON，开启后优先读 PostgreSQL repository。
- 当 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，单任务 PostgreSQL miss/异常会回退 JSON；项目列表在 PostgreSQL 返回空或异常时回退 JSON。关闭 fallback 时 PostgreSQL 异常会向上抛出，便于严格门禁。
- 运行态默认仍为 file-only；公开 API 响应形状仍返回 `StudioTask`，未启用 PostgreSQL primary 和 JSON archive。
- 本地验证：read-switch 测试 `4 passed`，studio/video/storage/studio-capabilities 目标集 `83 passed`，`py_compile`、`git diff --check`、`docker compose config` 均通过，后端全量 `276 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r11-studio-tasks-read-switch/`。

2026-06-07 阶段 7 R12 studio_tasks PostgreSQL primary write + JSON archive mirror：

- `backend/app/repositories/studio_task_runtime.py` 新增主写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` 包含 `studio_tasks` 或 `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary` 时，图片任务保存/删除才以 PostgreSQL 为主。
- `StorageService.save_studio_task()` 和 `delete_studio_task()` 在 primary-write 成功后按 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES` 决定是否维护临时 JSON 归档镜像。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免主写阶段产生“PG 失败但 JSON 成功”的分叉状态。
- 运行态默认仍为 file-only；公开 API 响应形状仍返回 `StudioTask`，服务器未启用该开关。
- 本地验证：primary-write 测试 `4 passed`，studio/video/storage/studio-capabilities 目标集 `80 passed`，`py_compile`、`git diff --check`、`docker compose config` 均通过，后端全量 `280 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r12-studio-tasks-primary-write/`。

2026-06-07 阶段 7 R13 projects 本地 schema/repository：

- 新增 `backend/app/db/schema/projects.py` 与 Alembic migration `20260607_0003_projects`，复用“索引列 + `raw_project_snapshot` JSONB”的过渡模式；migration head 更新为 `20260607_0003`。
- 新增 `ProjectRepository` 协议和 `backend/app/repositories/projects.py`，包含 file/PostgreSQL/dual repository；当前运行态仍默认 JSON/file-only，业务读写尚未接入。
- `projects` 表索引覆盖 `(user_id, updated_at desc)` 和 `(user_id, name)`，均过滤 `deleted_at is null`；索引列同时记录脚本、角色、场景、道具、风格数量，便于后续项目列表脱离目录扫描。
- 本地验证：新增 schema/repository 测试 `7 passed`，数据库三域目标集 `52 passed`，Alembic offline SQL 生成到 `20260607_0003`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `287 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r13-projects-local-schema-repository/`。

2026-06-07 阶段 7 R14 projects backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_projects.py`，扫描 `backend/data/users/<user_id>/projects/*.json`，按用户装配 repository factory 并 upsert 到 PostgreSQL repository。
- 新增 `backend/app/services/migration/reconcile_projects.py`，对比 JSON 与 PostgreSQL shadow 的计数、ID、`updated_at` 和脚本/角色/场景/道具/风格数量，并生成脱敏 JSON/Markdown 摘要。
- 新增 `scripts/postgres_backfill_projects.py` 与 `scripts/postgres_reconcile_projects.py`；脚本默认输出到 R14 artifact 目录。
- 隐私边界：摘要不包含项目名、描述、剧本内容、model config 细节、prompt body、token、password、API key 或私有 URL；单元测试显式覆盖这些内容不会进入 summary/Markdown。
- 本地验证：migration 测试 `3 passed`，projects schema/repository/migration 目标集 `10 passed`，三域迁移/仓储目标集 `21 passed`，数据库迁移目标集 `41 passed`，脚本 `py_compile` 通过，`docker compose config` 和 `git diff --check` 通过，后端全量 `290 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r14-projects-backfill-reconcile/`。

2026-06-07 阶段 7 R15 projects runtime dual-write：

- 新增 `backend/app/repositories/project_runtime.py`，集中处理 `projects` 双写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS` 包含 `projects` 或 `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write` 时才懒加载 PostgreSQL engine。
- `StorageService.save_project()` 保持 JSON 主写，JSON 成功后 shadow save PostgreSQL；`delete_project()` 保持 JSON 删除，随后 shadow mark deleted。
- 非 strict 模式下 PostgreSQL shadow 失败只记录 warning，不打断 JSON 主路径；strict 模式可用于后续对账门禁。
- 运行态默认仍为 file-only；读路径未切 PostgreSQL，公开 API 响应形状未改。服务器启用双写必须等待 live migration、backfill、reconcile 干净后再设置 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=projects`。
- 本地验证：dual-write 测试 `3 passed`，projects/storage 目标集 `14 passed`，三域 dual/migration 目标集 `18 passed`，数据库目标集 `44 passed`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `293 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r15-projects-runtime-dual-write/`。

2026-06-07 阶段 7 R16 projects read switch + JSON fallback：

- `backend/app/repositories/project_runtime.py` 新增项目读开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_READ_DOMAINS` 包含 `projects` 或 `MIEMIE_DATABASE_READ_MODE=postgres` 时才优先读 PostgreSQL。
- `StorageService.get_project()` 与 `list_projects()` 改为通过读开关 helper；默认继续读取 JSON，开启后项目详情和列表优先读 PostgreSQL repository。
- 当 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，单项目 PostgreSQL miss/异常会回退 JSON；项目列表在 PostgreSQL 返回空或异常时回退 JSON。关闭 fallback 时 PostgreSQL 异常会向上抛出，便于严格门禁。
- 运行态默认仍为 file-only；公开 API 响应形状仍返回 `Project`，未启用 PostgreSQL primary 和 JSON archive。
- 本地验证：read-switch 测试 `4 passed`，projects/read-switch/storage 目标集 `26 passed`，数据库目标集 `48 passed`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `297 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r16-projects-read-switch/`。

2026-06-07 阶段 7 R17 projects PostgreSQL primary write + JSON archive mirror：

- `backend/app/repositories/project_runtime.py` 新增主写开关：默认关闭，只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS` 包含 `projects` 或 `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary` 时，项目保存/删除才以 PostgreSQL 为主。
- `StorageService.save_project()` 和 `delete_project()` 在 primary-write 成功后按 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES` 决定是否维护临时 JSON 归档镜像。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免主写阶段产生“PG 失败但 JSON 成功”的分叉状态。
- 运行态默认仍为 file-only；公开 API 响应形状仍返回 `Project`，服务器未启用该开关。
- 本地验证：primary-write 测试 `4 passed`，projects 目标集 `22 passed`，数据库目标集 `52 passed`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `301 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r17-projects-primary-write/`。

2026-06-07 阶段 7 R18 staging connectivity refresh：

- 本轮只做只读连通性刷新，未修改服务器文件、Compose env、数据库开关或容器状态。
- SSH 命令执行仍不可用，返回 `Connection closed by 47.79.99.190 port 22`；TCP 22 可达但不足以执行 rollout 自动化。
- 本机 DNS 仍把 `pre-studio.miemie.co` 解析到 fake-IP `198.18.2.211`，到 `47.79.99.190` 的路由仍走 `utun1024`。
- 公网 `/api/health` 在当前客户端路径下 20 秒超时，因此不能从本机确认服务器 Compose、`postgres` health、server-local health、live migration、backfill/reconcile 或备份恢复演练。
- 证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r18-staging-connectivity-refresh/`；服务器 rollout 需等 SSH/public health 恢复，或改从已确认直连路径/服务器控制台执行并回收 artifact。

2026-06-07 阶段 7 R19 media metadata 本地 schema/repository：

- 新增 `backend/app/db/schema/media_assets.py`，定义 `media_assets` 和 `text_items` 两张表；`media_assets` 覆盖图库图片、音频库和视频库 metadata，`text_items` 独立覆盖文本库内容和版本快照。
- 新增 Alembic migration `20260607_0004_media_metadata`，链路从 `20260607_0003` 升级到 `20260607_0004`；offline SQL 生成通过。
- 新增 `backend/app/repositories/media_assets.py` 与 repository protocol：提供 file adapter、PostgreSQL repository、row mapping 和 `raw_media_snapshot` / `raw_text_snapshot` JSONB 完整快照。
- 本轮不迁文件本体，不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：media metadata 测试 `9 passed`，schema/repository 目标集 `22 passed`，数据库/storage 目标集 `43 passed`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `310 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r19-media-metadata-local-schema-repository/`。

2026-06-07 阶段 7 R20 media metadata backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_media_metadata.py`，扫描图库、音频库、视频库和文本库 JSON，并按 domain upsert 到 `media_assets` 或 `text_items` repository。
- 新增 `backend/app/services/migration/reconcile_media_metadata.py`，输出 JSON/Markdown 对账摘要；摘要只比较安全字段，不包含文本内容、prompt、provider payload、token/key/password 或私有 URL。
- 新增 `scripts/postgres_backfill_media_metadata.py` 和 `scripts/postgres_reconcile_media_metadata.py` 两个维护脚本；默认 artifact 目录指向本轮 R20 证据目录。
- 本轮不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED import gate 先以 `ModuleNotFoundError` 失败；实现后 migration 测试 `3 passed`，media metadata 目标集 `13 passed`，数据库目标集 `36 passed`，`py_compile`、`docker compose config`、`git diff --check` 均通过，后端全量 `313 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r20-media-metadata-backfill-reconcile/`。

2026-06-07 阶段 7 R21 media metadata runtime dual-write：

- 新增 `backend/app/repositories/media_asset_runtime.py`，统一管理 `media_metadata` dual-write feature flag、cached PostgreSQL engine 和 shadow repository builder。
- `StorageService.save_gallery_image()`、`save_audio_item()`、`save_video_item()`、`save_text_item()` 以及对应 delete 方法接入 shadow 写；默认不开启，显式开启后 JSON 主写/删除成功再 shadow 写 PostgreSQL。
- Shadow 写失败默认只记录 warning，不打断 JSON 主路径；`MIEMIE_DATABASE_RECONCILE_STRICT=true` 时可让 shadow 失败向上抛出，用于严格迁移门禁。
- 本轮不接入 read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED import gate 先以 `ModuleNotFoundError` 失败；实现后 dual-write 测试 `3 passed`，media metadata 目标集 `16 passed`，数据库目标集 `39 passed`，`py_compile`、`docker compose config` 均通过，后端全量 `316 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r21-media-metadata-runtime-dual-write/`。

2026-06-07 阶段 7 R22 media metadata read-switch：

- `backend/app/repositories/media_asset_runtime.py` 新增 read feature flag、read repository builder 和 PostgreSQL 优先读 helper。
- `StorageService.get_gallery_image()` / `get_gallery_images_by_project()`、音频库、视频库和文本库 get/list 方法接入 read-switch；默认仍读 JSON。
- 当 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，PostgreSQL miss、空列表或读异常会回退 JSON；关闭 fallback 时 PostgreSQL 异常向上抛出，便于严格门禁。
- 本轮不接入 primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED builder gate 先因缺少 `build_media_asset_read_repository` 失败；实现后 read-switch 测试 `4 passed`，media metadata 目标集 `20 passed`，数据库目标集 `43 passed`，`py_compile`、`docker compose config` 均通过，后端全量 `320 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r22-media-metadata-read-switch/`。

2026-06-07 阶段 7 R23 media metadata PostgreSQL primary-write：

- `backend/app/repositories/media_asset_runtime.py` 新增 primary-write feature flag、primary repository builder 和 PostgreSQL 主写 helper。
- `StorageService` 图库、音频库、视频库和文本库 save/delete 方法接入 primary-write；显式开启后先写 PostgreSQL，默认不再写 JSON，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时才维护 JSON archive mirror。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免主写阶段产生“PG 失败但 JSON 成功”的分叉状态。
- 默认运行态仍为 JSON/file-only；本轮未修改服务器开关，未执行 live migration/backfill/reconcile。
- 本地验证：RED builder gate 先因缺少 `build_media_asset_primary_repository` 失败；实现后 primary-write 测试 `4 passed`，media metadata 目标集 `24 passed`，数据库目标集 `47 passed`，`py_compile`、`docker compose config` 均通过，后端全量 `324 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r23-media-metadata-primary-write/`。

2026-06-07 阶段 7 R24 project entities 本地 schema/repository：

- 新增 `backend/app/db/schema/project_entities.py`，用统一 `project_entities` 表覆盖 `character`、`scene`、`prop`、`frame`、`video` 和 `style` 六类项目编辑实体。
- 新增 Alembic migration `20260607_0005_project_entities`，链路从 `20260607_0004` 升级到 `20260607_0005`；offline SQL 生成通过。
- 新增 `backend/app/repositories/project_entities.py`，提供 file/PostgreSQL/dual repository boundary、共享索引列映射和完整 `raw_entity_snapshot` JSONB 快照。
- 本轮不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED collection gate 先因缺少 `project_entities` schema/repository 模块失败；实现后 project entity 测试 `7 passed`，schema/repository 目标集 `16 passed`，`py_compile`、`docker compose config` 均通过，后端全量 `331 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r24-project-entities-local-schema-repository/`。

2026-06-07 阶段 7 R25 project entities backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_project_entities.py`，扫描角色、场景、道具、首帧、视频和风格 JSON，并按 `entity_kind` upsert 到 project entity repository。
- 新增 `backend/app/services/migration/reconcile_project_entities.py`，输出 JSON/Markdown 对账摘要；摘要只比较安全索引字段，不包含名称、描述、prompt、text style body、provider task id、token/key/password 或私有 URL。
- 新增 `scripts/postgres_backfill_project_entities.py` 和 `scripts/postgres_reconcile_project_entities.py` 两个维护脚本；默认 artifact 目录指向本轮 R25 证据目录。
- 本轮不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED import gate 先以 `ModuleNotFoundError` 失败；实现后 migration 测试 `3 passed`，project entity 目标集 `10 passed`，跨域 migration 目标集 `22 passed`，`py_compile` 通过，后端全量 `334 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r25-project-entities-backfill-reconcile/`。

2026-06-07 阶段 7 R26 project entities runtime dual-write：

- 新增 `backend/app/repositories/project_entity_runtime.py`，统一管理 `project_entities` dual-write feature flag、cached PostgreSQL engine 和 shadow repository builder。
- `StorageService.save_character()`、`save_scene()`、`save_prop()`、`save_frame()`、`save_video()`、`save_style()` 以及对应 delete 方法接入 shadow 写；默认不开启，显式开启后 JSON 主写/删除成功再 shadow 写 PostgreSQL。
- Shadow 写失败默认只记录 warning，不打断 JSON 主路径；`MIEMIE_DATABASE_RECONCILE_STRICT=true` 时可让 shadow 失败向上抛出，用于严格迁移门禁。
- 本轮不接入 read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED gate 先因缺少 `project_entity_runtime` 失败；实现后 dual-write 测试 `4 passed`，project entity/storage 目标集 `15 passed`，跨域 dual-write 目标集 `23 passed`，`py_compile` 通过，后端全量 `338 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r26-project-entities-runtime-dual-write/`。

2026-06-07 阶段 7 R27 project entities read-switch：

- `backend/app/repositories/project_entity_runtime.py` 新增 read feature flag、read repository builder、JSON fallback helper、按项目/类型过滤 helper。
- `StorageService` 角色、场景、道具、首帧、视频和风格 get/list 方法接入 read-switch；同时覆盖 frame/video by-shot 和 video by-task 读取。
- 当 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，PostgreSQL miss、空列表或读异常会回退 JSON；关闭 fallback 时 PostgreSQL 异常向上抛出，便于严格门禁。
- 本轮不接入 primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED gate 先因缺少 `build_project_entity_read_repository` 失败；实现后 read-switch 测试 `4 passed`，project entity/storage 目标集 `19 passed`，跨域 read-switch 目标集 `24 passed`，`py_compile` 通过，后端全量 `342 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r27-project-entities-read-switch/`。

2026-06-07 阶段 7 R28 project entities PostgreSQL primary-write：

- `backend/app/repositories/project_entity_runtime.py` 新增 primary-write feature flag、primary repository builder、主写 save/delete helper 和 JSON archive mirror 开关。
- `StorageService` 角色、场景、道具、首帧、视频和风格 save/delete 方法接入 primary-write；显式开启后先写 PostgreSQL，默认不再写 JSON，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时才维护 JSON archive mirror。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免切换期产生 PostgreSQL 失败但 JSON 成功的分叉状态。
- 默认运行态仍为 JSON/file-only；服务器 primary-write 仍需等 live migration/backfill/reconcile/dual-write/read-switch 证据干净后再启用。
- 本地验证：RED gate 先因缺少 `build_project_entity_primary_repository` 失败；实现后 primary-write 测试 `4 passed`，project entity/storage 目标集 `23 passed`，跨域数据库回归 `29 passed`，`py_compile` 通过，后端全量 `346 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r28-project-entities-primary-write/`。

2026-06-07 阶段 7 R29 staging 连通性刷新：

- 服务器 rollout 前置检查显示当前 operator path 仍不能安全执行 live migration/backfill/reconcile。
- `dig pre-studio.miemie.co A` 返回 `198.18.2.211`，仍是 fake-IP；到源站 IP `47.79.99.190` 的 route 走 `utun1024`。
- TCP 22 可达，但 `ssh -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'` 被远端关闭；公网 `/api/health` 20 秒超时且无响应体。
- 本轮未修改服务器状态；继续本地 benchmark/user/config 域迁移，待 SSH command execution 和 public health 同时稳定后再恢复 staging rollout。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r29-staging-connectivity-refresh/`。

2026-06-07 阶段 7 R30 benchmark records 本地 schema/repository：

- 新增 `backend/app/db/schema/benchmark_records.py`，覆盖图片/视频测评的 dataset、suite 和 run 三类记录。
- 新增 Alembic migration `20260607_0006_benchmark_records`，并注册到共享 metadata。
- 新增 `backend/app/repositories/benchmark_records.py`，提供 file/PostgreSQL repository boundary 和 Pydantic model 到安全索引列 + JSONB snapshot 的映射。
- 本轮不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED gate 先因缺少 `benchmark_records` schema/repository 模块失败；实现后 schema/repository 测试 `5 passed`，数据库 schema/repository 目标集 `42 passed`，`py_compile` 通过，后端全量 `351 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r30-benchmark-records-local-schema-repository/`。

2026-06-07 阶段 7 R31 benchmark records backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_benchmark_records.py`，扫描 per-user 图片/视频测评 dataset、suite 和 run JSON 并 upsert 到 PostgreSQL repository。
- 新增 `backend/app/services/migration/reconcile_benchmark_records.py`，按安全字段对比 JSON 和 PostgreSQL，输出脱敏 JSON/Markdown 摘要。
- 新增 `scripts/postgres_backfill_benchmark_records.py` 和 `scripts/postgres_reconcile_benchmark_records.py` 作为维护入口。
- 摘要不输出 prompt、provider payload、canonical request、request id、task id、key/token/password、私有 URL、名称或描述。
- 本轮不接入 runtime dual-write/read-switch/primary-write；默认运行态仍为 JSON/file-only。
- 本地验证：RED gate 先因缺少 `backfill_benchmark_records` 模块失败；实现后 migration 测试 `3 passed`，benchmark 目标集 `8 passed`，跨域 migration 回归 `23 passed`，`py_compile` 通过，后端全量 `354 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r31-benchmark-records-backfill-reconcile/`。

2026-06-07 阶段 7 R32 benchmark records runtime dual-write：

- 新增 `backend/app/repositories/benchmark_record_runtime.py`，统一承载 `benchmark_records` 写侧开关、运行态 PostgreSQL repository 构造和 shadow 失败策略。
- `StorageService` 图片/视频测评 dataset、suite、run 的保存/删除路径接入 shadow write；JSON 写入/删除仍先执行，显式启用 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=benchmark_records` 或 `MIEMIE_DATABASE_WRITE_MODE=dual|dual_write` 后才写 PostgreSQL。
- `MIEMIE_DATABASE_RECONCILE_STRICT=false` 时 shadow 失败只记录 warning，不打断 JSON 主路径；`true` 时在 JSON 成功后冒泡 shadow 异常，供灰度/对账窗口使用。
- 运行态仍默认 JSON/file-only；benchmark read-switch + JSON fallback 和 primary-write 尚未启用。
- 本地验证：RED gate 先因缺少 `benchmark_record_runtime` 模块失败；实现后 dual-write 测试 `4 passed`，benchmark/storage 目标集 `13 passed`，`py_compile` 通过，后端全量 `358 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r32-benchmark-records-runtime-dual-write/`。

2026-06-07 阶段 7 R33 benchmark records read-switch：

- `benchmark_record_runtime.py` 新增 read-switch 和 JSON fallback 开关，复用 `PostgresBenchmarkRecordRepository` 作为读仓库。
- `StorageService` 图片/视频测评 dataset、suite、run 的单条读取、项目列表读取和 suite run 列表读取均可在显式开关下优先读 PostgreSQL。
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，PostgreSQL miss、空列表或异常回退 JSON；关闭 fallback 时 PostgreSQL 读异常会冒泡，便于灰度门禁发现数据/连接问题。
- 运行态仍默认 JSON/file-only；benchmark PostgreSQL primary-write + JSON archive mirror 尚未启用。
- 本地验证：RED gate 先因缺少 `build_benchmark_record_read_repository` 失败；实现后 read-switch 测试 `4 passed`，benchmark/storage 目标集 `17 passed`，`py_compile` 通过，后端全量 `362 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r33-benchmark-records-read-switch/`。

2026-06-07 阶段 7 R34 benchmark records PostgreSQL primary-write：

- `benchmark_record_runtime.py` 新增 primary-write 开关、primary repository builder、保存和软删除主写 helper。
- `StorageService` 图片/视频测评 dataset、suite、run 的保存/删除路径支持显式 PostgreSQL 主写；默认不维护 JSON，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时才保留临时 JSON archive mirror。
- PostgreSQL 主写失败会直接冒泡，且不会写 JSON，避免切换窗口产生 PostgreSQL 失败但 JSON 成功的分叉状态。
- benchmark records 本地域已完成 schema/repository、backfill/reconcile、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；运行态默认仍为 JSON/file-only，服务器 live rollout 尚未闭环。
- 本地验证：RED gate 先因缺少 `build_benchmark_record_primary_repository` 失败；实现后 primary-write 测试 `4 passed`，benchmark/storage 目标集 `21 passed`，`py_compile` 通过，后端全量 `366 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r34-benchmark-records-primary-write/`。

2026-06-07 阶段 7 R35 user/config 本地 schema/repository：

- 新增 `users` 与 `user_configs` PostgreSQL schema，并加入 Alembic revision `20260607_0007`。
- 新增用户/配置 row mapping 与 `PostgresUserRepository`、`PostgresUserConfigRepository` 边界；`users.password_hash` 映射现有 bcrypt hash 字段，`user_configs` 只暴露 `api_region`、`has_dashscope_key`、`has_oss_config` 等安全索引。
- 本阶段不切换 `UserService`、session 或 `ConfigManager` 运行态；登录、Redis/file session fallback 和 per-user `config.json` 仍按现有路径运行。
- 本地验证：RED gate 先因缺少 `app.db.schema.user_config` 与 `app.repositories.user_config` 失败；实现后 focused `8 passed`，user/config + benchmark schema/repository 目标集 `13 passed`，`py_compile` 通过，后端全量 `374 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r35-user-config-local-schema-repository/`。

2026-06-07 阶段 7 R36 user/config backfill/reconcile：

- 新增 `backfill_user_config.py` / `reconcile_user_config.py`，扫描 `users.json` 和 per-user `config.json`，并通过 R35 repository upsert/compare PostgreSQL。
- 新增 `scripts/postgres_backfill_user_config.py` 与 `scripts/postgres_reconcile_user_config.py` 作为维护入口。
- 对账报告只输出计数、缺失记录和字段名；不输出 password hash 值、raw key/token、完整配置快照或私有用户数据。`sessions.json` 暂不迁移，active session 继续 Redis + file fallback。
- 运行态仍默认 JSON/Redis/file-only；尚未接入 user/config dual-write、read-switch 或 primary-write。
- 本地验证：RED gate 先因缺少 `backfill_user_config` 模块失败；实现后 focused `5 passed`，user/config 目标集 `13 passed`，`py_compile` 通过，后端全量 `379 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r36-user-config-backfill-reconcile/`。

2026-06-07 阶段 7 R37 user/config runtime dual-write：

- 新增 `user_config_runtime.py`，提供 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=user_config` 写侧 feature flag、runtime engine builder 和 shadow save helper。
- `UserService.register()`、`login()` 中的 password hash/last_login 更新、`change_password()` 在 JSON 主写成功后可 shadow 写 `users`。
- `ConfigManager.save()` 在当前用户上下文存在时可 shadow 写 `user_configs`；默认全局配置或无用户上下文不写 PostgreSQL。
- shadow 失败默认不打断 JSON 主路径；`MIEMIE_DATABASE_RECONCILE_STRICT=true` 可在灰度/对账窗口冒泡。session 仍不迁移。
- 本地验证：RED gate 先因缺少 `user_config_runtime` 模块失败；实现后 focused `6 passed`，user/config 目标集 `19 passed`，`py_compile` 通过，后端全量 `385 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r37-user-config-runtime-dual-write/`。

2026-06-07 阶段 7 R38 user/config read-switch：

- `user_config_runtime.py` 新增 read-switch 和 JSON fallback helper。
- `UserService.get_user_by_id()` 和 token 用户恢复可在显式开关下优先读 PostgreSQL；miss/error 可按 `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 回退 JSON。
- `ConfigManager.load()` 在当前用户上下文存在时可显式优先读 PostgreSQL；无用户上下文仍走 JSON。
- 登录密码校验主路径本阶段保持 JSON，避免认证链路一次跨太大；session 仍不迁移。
- 本地验证：RED gate 先因缺少 read repository builder 失败；实现后 focused `7 passed`，user/config 目标集 `26 passed`，`py_compile` 通过，后端全量 `392 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r38-user-config-read-switch/`。

2026-06-07 阶段 7 R39 user/config PostgreSQL primary-write：

- `user_config_runtime.py` 新增 primary-write 和 JSON archive mirror helper。
- `UserService.register()`、`login()` 的 last_login/hash 更新、`change_password()` 和 `ConfigManager.save()` 可在显式开关下以 PostgreSQL 为主。
- primary-write 模式下 user/config read helper 自动视为 PostgreSQL 优先，避免写 PostgreSQL 但读 JSON。
- 默认不写 JSON；`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 可在切换窗口保留临时 JSON 镜像。主写失败会直接冒泡，且不会写 JSON。
- session 仍保持 Redis + file fallback，不在本地域 primary-write 中迁移。
- 本地验证：RED gate 先因缺少 primary repository builder 失败；实现后 focused `7 passed`，user/config 目标集 `33 passed`，`py_compile` 通过，后端全量 `399 passed`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r39-user-config-primary-write/`。

2026-06-07 阶段 7 R40 staging 连通性复查：

- user/config 本地门禁完成后，只读复查服务器 rollout 路径。
- SSH 命令执行失败：TCP 22 可达，但 SSH banner exchange 超时。
- 公网 `https://pre-studio.miemie.co/api/health` 20 秒无响应。
- DNS 仍返回 `198.18.2.211`，到 `47.79.99.190` 的 route 使用 gateway `198.18.0.1` 和 interface `utun1024`。
- 结论：当前 operator network path 仍不能安全执行服务器 live rollout，本轮未修改服务器状态。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r40-staging-connectivity-after-user-config/`。

2026-06-07 阶段 7 R41 本地 live database rehearsal：

- 新增 `scripts/postgres_live_rehearsal.sh`，将本地临时 Compose PostgreSQL、`alembic upgrade head`、全域 backfill/reconcile、备份和恢复演练串成一个可复跑门禁。
- 脚本使用 `/tmp/<run_id>/compose.env` 保存临时强密码，并只把脱敏 env、status、commands 和错误摘要写入 artifact；不会把 raw key、token、PostgreSQL password、session 或私有用户数据写入仓库。
- 本机实跑结果为 `state=blocked`、`stage=docker-precheck`，原因是 Docker daemon 不可用：`Cannot connect to the Docker daemon at unix:///Users/zane/.docker/run/docker.sock`。
- 本轮未修改业务数据或服务器状态。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r41-local-live-database-rehearsal/`。

2026-06-16 阶段 7 R42 staging PostgreSQL live resume：

- 用户指出最终应在服务器测试后，恢复服务器侧 live gates。
- SSH 一度恢复，服务器本机 `/api/health` 为 `200`，Cloudflare public health 从服务器侧访问为 `200`，Compose 中 API/Redis/worker/worker-video 均运行。
- `/opt/miemie-pre` 从 `cb2d4ff0f5e00d2eb7fbb84a6b411408014107f0` fast-forward 到 `e73124527eeb858c4d12aa8990f19c6574bfb9d4`。
- `postgres` 服务已通过 Compose 启动，`pg_isready` 返回 `accepting connections`；启动后现有 API health 仍为 `200`，运行态 `x-deployment-version` 仍是 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`。
- 随后开始 build 最新 `api` 镜像，准备通过 one-off 容器执行 Alembic/backfill/reconcile；build 过程中 SSH 会话返回 `Timeout, server 47.79.99.190 not responding`，后续 SSH 检查继续在 banner exchange 阶段超时。
- 本轮尚未执行 Alembic、backfill、reconcile、API/worker 重启或任何数据库业务读写开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r42-staging-postgres-live-resume/`。

2026-06-16 阶段 7 R43 staging live migration/backfill/reconcile：

- SSH 恢复后，只读确认服务器 repo 为 `e731245`，`postgres` healthy，现有 API health 仍为 `200`。
- 由于当前线上镜像仍是 2026-06-01 旧镜像且缺少 Alembic，改用服务器 `/tmp/miemie-db-maint-venv-20260616` 临时维护 venv 执行迁移脚本，不替换线上运行镜像。
- Alembic 已升级到 `20260607_0007`。
- 全域 backfill/reconcile 均返回 `ok=true`；脱敏计数：`video_studio_tasks=6`、`studio_tasks=12`、`projects=9`、`users=46`、`user_configs=40`，其余 metadata/entity/benchmark 域当前 live JSON 计数为 0。
- PostgreSQL backup 生成 `.sql` 备份；restore rehearsal 使用 `miemie_restore_check` 成功恢复并校验。
- 迁移后服务器本机 health 和服务器侧 Cloudflare public health 均为 `200`；应用运行态仍是 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`，业务数据库开关仍关闭。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r43-staging-live-migration-backfill-reconcile/`。
- 23:27 CST closeout 只读复查：`api/postgres/redis/worker/worker-video` 均仍运行，服务器本机与 Cloudflare `/api/health` 继续为 `200`。

2026-06-16 阶段 7 R44 staging dual-write canary 预备中断：

- 目标是先滚动到包含数据库 feature flag 的新运行态，保持 `MIEMIE_DATABASE_ENABLED=false`，再启用 `video_studio_tasks` dual-write canary。
- 服务器 `compose.env` 已备份为 `compose.env.bak-r44-dual-write-canary-20260616`，`MIEMIE_RUNTIME_GIT_COMMIT` 更新到 `e73124527eeb858c4d12aa8990f19c6574bfb9d4`，`MIEMIE_DATABASE_ENABLED` 明确保持 `false`。
- 使用 `docker-compose.pre.override.yml` 构建 `miemie-studio:pre-local`，但 build SSH 会话在完成前超时；本轮没有执行 `docker compose up`，没有重启 API/worker，也没有启用数据库业务开关。
- 随后本机 DNS/route 复现 fake-IP/TUN 症状：`pre-studio.miemie.co` 解析为 `198.18.2.63`，到 `47.79.99.190` 的 route 走 `utun1024`/`198.18.0.1`；TCP 22 可连但 SSH banner 超时。
- 当前不能把 R44 视为 dual-write canary；恢复 SSH 后必须先只读审计镜像是否构建完成、容器是否仍旧、health 是否正常，再决定继续构建或滚动新镜像。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r44-staging-dual-write-canary-interrupted/`。

2026-06-17 阶段 7 R45 staging canary 自动化：

- 新增 `scripts/postgres_staging_video_task_canary.sh`，用于恢复 SSH 后继续 R44。
- 脚本分为 `MODE=audit`、`MODE=roll-runtime`、`MODE=dual-write-canary`。默认 `audit` 只读；`roll-runtime` 只构建/滚动新运行态且保持 `MIEMIE_DATABASE_ENABLED=false`；`dual-write-canary` 才开启 `video_studio_tasks` 单域双写。
- 双写验证不调用真实供应商：容器内维护 smoke 通过 `StorageService.save_video_studio_task()` 写入 canary task，并直接检查 PostgreSQL shadow row；API smoke 使用 `/api/video-studio/preview-payload`。
- 本地验证：`bash -n scripts/postgres_staging_video_task_canary.sh` 通过；本机缺少服务器 `compose.env` 时 `MODE=audit` 按预期写入 blocked status，未尝试 Docker/Compose 操作。
- 当前本机路径仍显示 `198.18.*`/`utun1024`，SSH 仍在 banner exchange 超时；服务器实跑待直连 SSH 恢复。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r45-staging-canary-automation-script/`。

2026-06-17 阶段 7 R46 staging canary verifier：

- 新增 `scripts/verify_postgres_staging_canary_script.py`，作为 R45 shell 脚本的 app-free 本地 verifier。
- verifier 覆盖 shell 语法、缺少 `compose.env` 时的 blocked precheck、不触碰 Docker/Compose、默认只读 `audit`、`roll-runtime` 数据库业务开关关闭、`dual-write-canary` 单域双写和 no-provider smoke 契约。
- 本地验证：`python3 scripts/verify_postgres_staging_canary_script.py` 通过；`bash -n scripts/postgres_staging_video_task_canary.sh` 通过。
- 早先尝试把相同检查放入 `backend/tests/test_run_script.py` 时，后端全局 `conftest.py` 加载 app/OSS/PyCryptodome 栈并在本机原生模块加载阶段被 macOS system policy 拦住；该环境问题不属于 canary 脚本本身，因此本轮改为独立 verifier。
- R46 未执行服务器命令、未重启容器、未启用数据库业务开关；证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r46-staging-canary-verifier/`。

2026-06-17 阶段 7 R47/R48 本地实库演练恢复：

- 本机 Docker daemon 在沙盒外可用后，重跑 `scripts/postgres_live_rehearsal.sh`。
- R47 复现并定位根因：`scripts/postgres_backup.sh` 产出 `.sql`，但 rehearsal 脚本查找 `*.dump`，导致备份实际成功但演练误判失败。
- 修复 `scripts/postgres_live_rehearsal.sh` 备份发现逻辑为 `*.sql`。
- R48 通过：临时 Compose PostgreSQL 启动，Alembic upgrade head 通过，`video_studio_tasks`、`studio_tasks`、`projects`、`media_metadata`、`project_entities`、`benchmark_records`、`user_config` 全域 backfill/reconcile 均 `ok=true`，`.sql` 备份创建成功，restore rehearsal 在 `miemie_restore_check` 中通过并清理，演练容器/volume 已 `down -v` 清理。
- 为避免提交本地用户 UUID，原始 backfill/reconcile 明细不入库；提交脱敏摘要到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r47-local-live-database-rehearsal-failed/` 与 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r48-local-live-database-rehearsal/`。

2026-06-17 阶段 7 R49 staging read-switch/rollback 自动化：

- 扩展 `scripts/postgres_staging_video_task_canary.sh`，新增显式 `MODE=read-switch-canary` 与 `MODE=rollback-read-switch`。
- `read-switch-canary` 会启用 `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`，保持 JSON 主写和 PostgreSQL shadow write，并用 JSON/PG 分叉状态 canary 证明 `StorageService.get_video_studio_task()` 与项目列表读取 PostgreSQL。
- `rollback-read-switch` 会清空 `MIEMIE_DATABASE_READ_DOMAINS`，保持 JSON 主写和 PostgreSQL shadow write，并用同样的分叉状态 canary 证明读路径回到 JSON。
- 两段 canary 均继续使用 `/api/video-studio/preview-payload` 做 no-provider API smoke；不会触发真实供应商生成。
- `scripts/verify_postgres_staging_canary_script.py` 已加强：除 shell 语法、缺 env blocked precheck 和安全契约外，还会编译脚本内所有 `<<'PY'` 维护 Python 代码块。
- 本地验证：`bash -n scripts/postgres_staging_video_task_canary.sh`、`python3 scripts/verify_postgres_staging_canary_script.py`、`python3 -m py_compile scripts/verify_postgres_staging_canary_script.py` 均通过。R49 未执行服务器命令、未重启容器、未启用业务开关；证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r49-staging-read-switch-rollback-automation/`。

2026-06-17 阶段 7 R50 staging primary-write/rollback 自动化：

- 扩展 `scripts/postgres_staging_video_task_canary.sh`，新增显式 `MODE=primary-write-canary` 与 `MODE=rollback-primary-write`。
- `primary-write-canary` 会启用 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=video_studio_tasks` 和 `MIEMIE_DATABASE_READ_DOMAINS=video_studio_tasks`，关闭 JSON archive writes，并验证 `StorageService.save_video_studio_task()` 后 PostgreSQL 主写存在、读后可见、没有生成 JSON 文件。
- `rollback-primary-write` 会清空 primary/read domains，恢复 JSON 主写 + PostgreSQL shadow write，并用分叉状态证明读路径回到 JSON、shadow row 存在且 delete 可同步标记 PostgreSQL 删除。
- 两段 canary 均继续使用 `/api/video-studio/preview-payload` 做 no-provider API smoke；不会触发真实供应商生成。
- 本地验证：`bash -n scripts/postgres_staging_video_task_canary.sh`、`python3 scripts/verify_postgres_staging_canary_script.py`、`python3 -m py_compile scripts/verify_postgres_staging_canary_script.py` 均通过；`backend/.venv/bin/pytest backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py -q` 通过 11 项 runtime 语义测试。R50 未执行服务器命令、未重启容器、未启用业务开关；证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r50-staging-primary-write-rollback-automation/`。

2026-06-17 阶段 7 R51 staging sequence runner 与连通性复查：

- 复查服务器路径时，`nc -vz 47.79.99.190 22` TCP 成功，但 `ssh -o BatchMode=yes -o ConnectTimeout=12 ...` 仍在 banner exchange 超时；`pre-studio.miemie.co` DNS 仍返回 `198.18.2.63`，到源站 IP 的 route 仍走 `utun1024`，public health 20 秒无响应。本轮没有进入远端命令执行，也没有修改服务器。
- 新增 `scripts/postgres_staging_video_task_sequence.sh`，把 `audit -> roll-runtime -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write` 串成服务器序列 runner。默认 `CONFIRM_STAGING_SEQUENCE=dry-run` 只写计划；显式 `CONFIRM_STAGING_SEQUENCE=run` 才执行，并在任一阶段非 0 时停止。
- 新增 `scripts/verify_postgres_staging_canary_sequence.py`，验证 runner shell 语法、dry-run 不触碰 Docker/子 canary、默认序列和显式执行开关。
- 本地验证：`bash -n scripts/postgres_staging_video_task_sequence.sh`、`python3 scripts/verify_postgres_staging_canary_sequence.py`、`python3 scripts/verify_postgres_staging_canary_script.py` 均通过；本地 dry-run 写入预期 sequence。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r51-staging-sequence-runner-and-connectivity/`。

2026-06-17 阶段 7 R52 connectivity preflight：

- 新增 `scripts/pre_studio_connectivity_preflight.sh`，在执行 R51 sequence 前检查代理环境脱敏摘要、DNS fake-IP、到源站 IP 的 route/TUN、TCP 22、SSH banner 和公网 `/api/health` header/body。
- 新增 `scripts/verify_pre_studio_connectivity_preflight.py`，验证 preflight shell 语法、dry-run 不执行网络命令、代理环境脱敏和关键安全契约。
- 沙盒内真实预检会遇到 DNS/permission 限制，因此本轮用提升权限实跑一次；结果为 blocked：DNS `198.18.0.80`，route gateway `198.18.0.1` / interface `utun1024`，TCP 22 可达，SSH banner 被 `47.79.99.190` 关闭，public health 返回 HTTP/2 framing layer error。
- 本地验证：`bash -n scripts/pre_studio_connectivity_preflight.sh`、`python3 scripts/verify_pre_studio_connectivity_preflight.py`、`python3 scripts/verify_postgres_staging_canary_sequence.py` 均通过。R52 未执行服务器命令、未重启容器、未启用业务开关；证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r52-connectivity-preflight/`。

2026-06-17 阶段 7 R53 remote PostgreSQL sequence wrapper：

- 新增 `scripts/pre_studio_remote_postgres_sequence.sh`，把 R52 本地 preflight 与 R51 服务器 sequence 串成一个入口。默认只写 dry-run 计划；显式 `CONFIRM_REMOTE_SEQUENCE=run` 后先跑本地 preflight，通过后才 SSH 到 `/opt/miemie-pre`。
- 远端命令只使用 `git fetch origin pre` 与 `git merge --ff-only origin/pre` 同步，不使用 `git reset --hard`；随后执行 `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`，并可把远端 artifact 拉回本地归档。
- 新增 `scripts/verify_pre_studio_remote_postgres_sequence.py`，验证 dry-run 不执行网络命令、远端命令包含 `ff-only` 同步和 R51 sequence、且不含破坏性 git/docker 命令。
- 本轮用 `CONFIRM_REMOTE_SEQUENCE=run` 实跑 wrapper，结果停在本地 preflight：DNS 仍为 `198.18.0.80`，route 仍走 `utun1024`，TCP 22 可达，但 SSH banner 超时，public health 20 秒无响应。wrapper 未进入远程 sequence。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r53-remote-postgres-sequence/`。

2026-06-17 部署体验 R54 deploy doctor：

- 新增 `scripts/deploy_doctor.sh` 与 `scripts/verify_deploy_doctor.py`，为 Mac、本机脚本生产路径和单服务器 Compose 路径提供只读部署前自检。
- `./run.sh doctor` 已接入主脚本命令和维护菜单；默认不安装依赖、不修改配置、不启动服务，检查 Python/Node/npm/curl/screen/lsof、关键部署文件、敏感 `backend/data` 文件误跟踪、`compose.env` 缺失/占位值、Docker/Compose 版本和端口占用。
- `DOCTOR_PROFILE=compose` 可把缺失 `compose.env` 提升为 blocked；`MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true` 才会额外检查 Docker daemon，避免普通 Mac 环境被 daemon 状态误拦。
- 本机实跑 `./run.sh doctor` 结果为 `passed_with_warnings`：19 passed、2 warn（`compose.env` 缺失、Docker daemon 检查默认跳过）、0 blocked/failed。证据归档到 `docs/reports/artifacts/2026-06-17-deploy-doctor/`。

2026-06-17 阶段 7 R55 connectivity rediagnosis：

- R54 后继续执行本地 doctor 和 `scripts/pre_studio_connectivity_preflight.sh`；doctor 仍为 `passed_with_warnings`，只有本地缺 `compose.env` 和 Docker daemon 默认跳过两个 warning。
- 真实 preflight 仍 blocked：DNS 返回 `198.18.0.100`，route 走 gateway `198.18.0.1` / interface `utun1024`，TCP 22 可达但 SSH banner 超时，公网 `/api/health` 20 秒无响应。
- 额外尝试 `route -n get -ifscope en0 47.79.99.190` 可见物理网关 `192.168.50.1`，但 `ssh -o BindInterface=en0 ... echo ok` 与 `curl --interface en0 --resolve ... /api/health` 仍超时；因此未执行远端 sequence、未修改服务器、未启用数据库业务开关。
- `scripts/pre_studio_connectivity_preflight.sh` 已补 `remediation.md` 输出，自动把 fake-IP DNS、TUN route、SSH banner 和 public health timeout 的恢复动作写入 artifact；本地 verifier 已覆盖该契约。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r55-connectivity-preflight-rediagnosis/`。

2026-06-17 阶段 7 R56 DIRECT 规则复测：

- 用户在 Clash 中添加 `pre-studio.miemie.co` 和源站 IP 的 DIRECT 规则后，复跑 `./run.sh doctor` 与 `scripts/pre_studio_connectivity_preflight.sh`。
- doctor 仍为 `passed_with_warnings`，只有本地缺 `compose.env` 和 Docker daemon 默认跳过两个 warning。
- connectivity preflight 仍 blocked：DNS 仍为 `198.18.0.100`，route 仍走 gateway `198.18.0.1` / interface `utun1024`，TCP 22 可达但 SSH banner 超时，公网 health 20 秒无响应。
- 结论：DIRECT 规则尚未在 macOS 命令行 DNS/route 路径生效；远端 PostgreSQL sequence 未执行。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r56-direct-rule-still-blocked/`。

2026-06-17 阶段 7 R57 network-scope preflight：

- `scripts/pre_studio_connectivity_preflight.sh` 新增 `MIEMIE_PREFLIGHT_SCOPE=network`，只跑 DNS 与源站 route 两个门禁，确认本机 Clash/fake-IP/TUN 是否已经清干净；该 scope 不触发 TCP 22、SSH banner 或 public health，避免每次等待超时。
- verifier 新增 fake-bin 契约，证明 network scope 只调用 `dig` 与 `route`，不会误触发 `nc`、`ssh`、`curl`。
- 真实 network scope 实跑 0.16 秒返回 blocked：DNS 仍为 `198.18.0.100`，route 仍走 gateway `198.18.0.1` / interface `utun1024`；远端 PostgreSQL sequence 未执行。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r57-network-scope-preflight/`。

2026-06-17 阶段 7 R58 服务器自运行 sequence 入口：

- 用户继续补 DIRECT 规则后，实跑完整 `scripts/pre_studio_connectivity_preflight.sh` 仍 blocked：DNS 为 `198.18.0.100`，route 仍走 gateway `198.18.0.1` / interface `utun1024`，TCP 22 可达但 SSH banner 超时，公网 health 20 秒超时。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-connectivity-after-direct-rule/`。
- 新增 `scripts/pre_studio_server_postgres_sequence.sh`，作为服务器终端后备入口：在 `/opt/miemie-pre` 内默认 dry-run，显式 `CONFIRM_SERVER_SEQUENCE=run` 后校验 branch/files、`git merge --ff-only origin/pre`，再执行 R51 `CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh`。
- 新增 `scripts/verify_pre_studio_server_postgres_sequence.py`，验证 shell 语法、dry-run 不执行 git fetch/merge 或 Docker/网络命令、确认变量和安全契约。dry-run 证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-server-self-sequence-wrapper/`。

2026-06-17 阶段 7 R59 sessions PostgreSQL 本地基础：

- 新增 `sessions` PostgreSQL schema 与 Alembic revision `20260607_0008`，字段包括 `token_hash`、`user_id`、`raw_session_snapshot`、`created_at`、`last_seen_at`、`expires_at` 和 `deleted_at`，并建立 active user/expires partial indexes。
- 新增 `PostgresSessionRepository`，数据库只保存 SHA-256 `token_hash`；raw session token 不入库、不进入 backfill/reconcile artifact。
- 新增 `backend/app/services/migration/backfill_sessions.py`、`reconcile_sessions.py`、`scripts/postgres_backfill_sessions.py` 和 `scripts/postgres_reconcile_sessions.py`，支持 current/legacy `sessions.json` 形状，输出仅包含计数、字段名、错误类型和 token hash。
- `scripts/postgres_live_rehearsal.sh` 的 domain 序列已加入 `sessions`，顺序在 user/config 后，避免外键缺失。
- 运行态保持不变：auth session 仍是 Redis 优先 + file fallback；本轮未引入 session read/write switch，也未修改服务器业务开关。
- 本地验证：session focused `9 passed`，session + user/config target `22 passed`，schema/repository/migration target `82 passed`，auth/session target `52 passed`，后端全量 `408 passed`，`py_compile`、shell syntax 和 Alembic offline SQL 均通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r59-sessions-local-schema-repository/`。
- 用户再次补本地 DIRECT 规则后复跑完整 preflight 仍 blocked：DNS `198.18.0.124`，route `utun1024`，TCP 22 可达但 SSH banner 超时，公网 health 20 秒超时；服务器 sequence 未执行，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r59-connectivity-after-direct-rule/`。

2026-06-17 阶段 7 R60 sessions runtime dual-write：

- 新增 `backend/app/repositories/session_runtime.py`，沿用现有数据库 feature flag 模式：默认关闭，显式 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=sessions` 或全局 `MIEMIE_DATABASE_WRITE_MODE=dual/dual_write` 后才启用。
- `UserService` 登录保存 session 后会 shadow-save 到 PostgreSQL；登出会 shadow-delete 单个 session；改密清理会 shadow-delete 用户所有 sessions。
- Shadow 失败默认 warning-only，不打断 Redis/file 主路径；`MIEMIE_DATABASE_RECONCILE_STRICT=true` 时在主路径写入完成后冒泡，便于灰度/对账窗口发现问题。
- 运行态默认仍为 Redis + file fallback；本轮不做 session read-switch 或 primary-write，不修改服务器业务开关，日志不记录 raw token。
- 本地验证：R60 focused `5 passed`，auth/session target `63 passed`，schema/repository/migration target `87 passed`，后端全量 `413 passed`，`py_compile` 通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r60-sessions-runtime-dual-write/`。

2026-06-17 阶段 7 R61 sessions read-switch：

- 新增 `sessions` 读侧 feature flag：显式 `MIEMIE_DATABASE_READ_DOMAINS=sessions` 或全局 `MIEMIE_DATABASE_READ_MODE=postgres` 后，`UserService.get_user_by_token()` 可优先读取 PostgreSQL session。
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，PostgreSQL miss/error 会回退现有 Redis/file session 路径；未开启 fallback 时沿用数据库读失败即失败的灰度策略。
- 运行态默认仍不变：Redis/file 仍是默认 auth session 路径；本轮不做 sessions primary-write，不启用服务器业务开关，不记录 raw token。
- 本地验证：RED 先确认缺少 `build_session_read_repository`；实现后 R61 focused `4 passed`，sessions runtime combined `18 passed`，auth/session target `67 passed`，schema/repository/migration target `91 passed`，`py_compile` 通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r61-sessions-read-switch/`。

2026-06-17 阶段 7 R62 connectivity direct-rule recheck：

- 用户新增 Clash 直连规则后，重跑 network-scope preflight；沙盒内首次因 `dig`/`route` socket 权限被拒，提升权限后得到真实结果。
- 结果仍为 blocked：DNS 返回 `198.18.0.124`，到源站 `47.79.99.190` 的 route 仍走 `198.18.0.1` / `utun1024`。
- 手动分层检查显示 TCP 22 可达，但 `ssh root@47.79.99.190 'echo ok'` 仍在 banner exchange 阶段超时；verbose SSH 已建立 TCP 并发送本地 version string，但服务端 banner 未返回。
- 本轮未执行 remote PostgreSQL sequence、未修改服务器状态、未重启容器、未启用数据库业务开关。证据归档到 `docs/reports/artifacts/2026-06-17-postgres-connectivity-direct-rule/`。

2026-06-17 阶段 7 R63 sessions primary-write：

- 新增 `sessions` 主写 feature flag：显式 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=sessions` 或全局 PostgreSQL write mode 后，登录保存 session 会先写 PostgreSQL。
- Redis 继续作为热 session cache；默认不再写 `sessions.json`，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时才维护临时 JSON 归档镜像。
- 主写失败会直接冒泡，且不写 Redis/file fallback，避免切换窗口出现分叉 session 状态；主写模式自动视为 PostgreSQL 读优先，避免写 PG 但读 JSON。
- 登出和改密清理接入 PostgreSQL 主删；默认运行态仍不变，服务器业务开关未启用。
- 本地验证：RED 先确认缺少 `build_session_primary_repository`；实现后 focused `7 passed`，sessions runtime combined `25 passed`，auth/session target `74 passed`，schema/repository/migration target `98 passed`，后端全量 `424 passed`，`py_compile` 通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r63-sessions-primary-write/`。

2026-06-17 阶段 7 R64 staging live data gate：

- 新增 `scripts/postgres_staging_live_data_gate.sh`，默认 dry-run；显式 `CONFIRM_LIVE_DATA_GATE=run` 后在服务器执行 Alembic `upgrade head`、全域 backfill/reconcile、PostgreSQL 备份和 restore rehearsal。
- 该 gate 只为维护进程注入数据库环境，不切换应用业务读写开关；维护 env 和 PostgreSQL dump 均保留在 `/tmp`，不写入提交 artifact。
- `scripts/postgres_staging_video_task_sequence.sh` 默认序列已插入 `live-data-gate`，完整顺序为 `audit -> roll-runtime -> live-data-gate -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write`。
- 本地验证：RED 先确认 sequence 缺少 `live-data-gate`、新 gate 脚本缺失；实现后 `python3 scripts/verify_postgres_staging_live_data_gate.py`、`python3 scripts/verify_postgres_staging_canary_sequence.py`、`python3 -m py_compile scripts/verify_postgres_staging_live_data_gate.py scripts/verify_postgres_staging_canary_sequence.py` 均通过，并生成 dry-run artifact。
- 用户新增直连规则后复测：`nc -vz 47.79.99.190 22` 可达，但 route 仍为 `utun1024` / gateway `198.18.0.1`，`ssh root@47.79.99.190 'echo ok'` 仍在 banner exchange 超时。本轮未执行服务器 sequence、未重启容器、未启用数据库业务开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-live-data-gate/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r64-staging-sequence-with-live-data-gate/`。

2026-06-17 阶段 7 R65 connectivity remediation / server fallback contract：

- 复测用户新增规则后的 network-scope preflight，结果仍 blocked：DNS `198.18.0.124`，route 为 `destination 32.0.0.0`、`mask 224.0.0.0`、`gateway 198.18.0.1`、`interface utun1024`。
- `scripts/pre_studio_connectivity_preflight.sh` 已加强 remediation：当宽泛 TUN catch-all 路由获胜时，会输出 `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve`，并提示放在宽泛代理规则和 Rule Providers 前。
- `scripts/pre_studio_server_postgres_sequence.sh` 已加强 fallback 契约：dry-run plan 与 run precheck 都会确认 sequence 包含 `live-data-gate` 且 `scripts/postgres_staging_live_data_gate.sh` 存在，避免服务器自运行入口漏掉 R64 live data gate。
- 本地验证：`python3 scripts/verify_pre_studio_connectivity_preflight.py` 与 `python3 scripts/verify_pre_studio_server_postgres_sequence.py` 均通过。服务器 sequence 仍未执行、未重启容器、未启用数据库业务开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r65-connectivity-ip-cidr-remediation/` 和 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r65-server-sequence-live-data-gate-contract/`。

2026-06-17 阶段 7 R66 remote wrapper/server fallback 对齐：

- `scripts/pre_studio_remote_postgres_sequence.sh` 默认远端 runner 从 staging sequence 改为 `scripts/pre_studio_server_postgres_sequence.sh`。
- 本机路径恢复后，remote wrapper 会先跑本机 connectivity preflight；通过后在远端执行 `git fetch origin pre` + `git merge --ff-only origin/pre`；同步后调用 `CONFIRM_SERVER_SEQUENCE=run SERVER_SYNC=none scripts/pre_studio_server_postgres_sequence.sh`。
- 这样本机远程路径和服务器终端路径复用同一套 server fallback 契约，包括 R65 的 `live-data-gate` 检查。
- 本地验证：RED 先确认 remote command 未调用 `CONFIRM_SERVER_SEQUENCE=run`；实现后 `python3 scripts/verify_pre_studio_remote_postgres_sequence.py` 与 `bash -n scripts/pre_studio_remote_postgres_sequence.sh` 通过，并生成 dry-run artifact。服务器 sequence 仍未执行、未重启容器、未启用数据库业务开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r66-remote-wrapper-server-fallback/`。

2026-06-17 阶段 7 R67 PostgreSQL domain coverage audit：

- 新增 `scripts/postgres_domain_coverage.py` 和 `scripts/verify_postgres_domain_coverage.py`，把当前 PostgreSQL 分域迁移覆盖面固化为可重复生成的 JSON/Markdown 报告。
- 报告确认 8 个 domain 已具备本地 schema/repository/backfill/reconcile/runtime gates：`video_studio_tasks`、`studio_tasks`、`projects`、`media_metadata`、`project_entities`、`benchmark_records`、`user_config`、`sessions`。
- 剩余明确 JSON-only 业务状态域为 `audio_studio`，覆盖 `audio_studio/*.json` 音频任务与 `voices/*.json` 音色档案；下一本地迁移域建议为 `audio_studio`。`scripts/shots` 继续由 `projects.raw_project_snapshot` 覆盖，不作为下一刀独立表。
- 本地验证：RED 先确认缺少 coverage 脚本；实现后 `python3 scripts/verify_postgres_domain_coverage.py` 通过，并生成 R67 artifact。服务器 sequence 仍未执行、未重启容器、未启用数据库业务开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r67-postgres-domain-coverage/`。

2026-06-17 阶段 7 R68 audio_studio 本地 schema/repository：

- 新增 `backend/app/db/schema/audio_studio.py` 和 Alembic migration `20260617_0009_audio_studio`，创建 `audio_studio_tasks` 与 `voice_profiles` 两张表。
- 新增 `AudioStudioRepository` 协议和 `backend/app/repositories/audio_studio.py`，包含 file adapter、PostgreSQL repository、dual wrapper，以及音频任务/音色档案的 row mapping。
- 表设计沿用“索引列 + JSONB 原始快照”的过渡模式：项目列表、状态扫描、voice_id 查询走索引列，完整 `AudioStudioTask` / `VoiceProfile` 保留在 `raw_task_snapshot` / `raw_profile_snapshot`。
- 本地验证：RED 先确认 schema/repository 模块缺失；实现后 `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_schema.py backend/tests/test_audio_studio_repository.py -q` 为 `9 passed`，coverage verifier/py_compile/Alembic offline SQL 均通过。运行态仍默认 JSON/file-only，服务器 sequence 未执行、业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r68-audio-studio-local-schema-repository/`。

2026-06-17 阶段 7 R69 audio_studio backfill/reconcile：

- 新增 `backend/app/services/migration/backfill_audio_studio.py` 与 `backend/app/services/migration/reconcile_audio_studio.py`，同时覆盖音频任务和音色档案两类 JSON 表面。
- 新增 `scripts/postgres_backfill_audio_studio.py` 与 `scripts/postgres_reconcile_audio_studio.py`；`postgres_live_rehearsal.sh` 和 `postgres_staging_live_data_gate.sh` 已把 `audio_studio` 加入默认全域演练列表。
- 对账摘要只比较保守字段：任务/档案 ID、project、状态、任务类型、result voice id、source、target model 和更新时间；不输出任务文本、prompt、音频 URL、名称、provider payload、token/key/password 或私有用户数据。
- 本地验证：RED 先确认 backfill/reconcile 模块缺失；实现后 `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_migration.py -q` 为 `2 passed`，audio studio 目标集 `11 passed`，coverage verifier 与 py_compile 通过。运行态仍默认 JSON/file-only，服务器 sequence 未执行、业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r69-audio-studio-backfill-reconcile/`。

2026-06-17 阶段 7 R70 audio_studio runtime dual-write：

- 新增 `backend/app/repositories/audio_studio_runtime.py`，沿用现有数据库 feature flag 模式：默认关闭，显式 `MIEMIE_DATABASE_DUAL_WRITE_DOMAINS=audio_studio` 或全局 dual-write 后才启用。
- `StorageService.save_audio_studio_task()`、`delete_audio_studio_task()`、`save_voice_profile()` 和 `delete_voice_profile()` 已接入 shadow save/delete；JSON 主路径先成功，随后才写 PostgreSQL。
- Shadow 失败默认 warning-only，不破坏 JSON 主路径；`MIEMIE_DATABASE_RECONCILE_STRICT=true` 时可在对账/灰度窗口冒泡。
- 本地验证：RED 先确认 runtime 模块缺失；实现后 `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_dual_write.py -q` 为 `4 passed`，audio studio 目标集 `15 passed`，coverage verifier 通过。运行态仍默认 JSON/file-only，服务器 sequence 未执行、业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r70-audio-studio-runtime-dual-write/`。

2026-06-18 阶段 7 R71 audio_studio read-switch：

- `backend/app/repositories/audio_studio_runtime.py` 新增读侧 feature flag、read repository builder 和 JSON fallback helper。
- `StorageService.get_audio_studio_task()`、`get_audio_studio_tasks()`、`get_voice_profile()`、`get_voice_profiles()` 和 `get_voice_profile_by_voice_id()` 已接入 PostgreSQL 优先读；默认仍 JSON/file-only。
- 显式开启 `MIEMIE_DATABASE_READ_DOMAINS=audio_studio` 或全局 PostgreSQL read mode 后，音频任务、音色档案、项目列表和 `voice_id` 查询可读 PostgreSQL；`MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时 miss/空列表/异常回退 JSON。
- 本地验证：RED 先确认 `build_audio_studio_read_repository` 缺失；实现后 `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_read_switch.py -q` 为 `4 passed`，coverage artifact 已生成。运行态仍默认 JSON/file-only，服务器 sequence 未执行、业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r71-audio-studio-read-switch/`。

2026-06-18 阶段 7 R72 audio_studio primary-write：

- `backend/app/repositories/audio_studio_runtime.py` 新增 primary-write feature flag、primary repository builder、主写保存/删除 helper 和 JSON archive mirror 开关。
- `StorageService.save_audio_studio_task()`、`delete_audio_studio_task()`、`save_voice_profile()` 和 `delete_voice_profile()` 已接入 PostgreSQL 主写；默认仍 JSON/file-only。
- 显式开启 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=audio_studio` 或全局 PostgreSQL 主写模式后，音频任务与音色档案保存/删除以 PostgreSQL 为主；默认不写 JSON，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时保留临时 JSON archive mirror。主写失败会冒泡且不落 JSON。
- 本地验证：RED 先确认 `build_audio_studio_primary_repository` 缺失；实现后 `backend/.venv/bin/python -m pytest backend/tests/test_audio_studio_primary_write.py -q` 为 `4 passed`，coverage artifact 已生成。运行态仍默认 JSON/file-only，服务器 sequence 未执行、业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r72-audio-studio-primary-write/`。

2026-06-18 阶段 7 R73 coverage after audio：

- 更新 `scripts/postgres_domain_coverage.py` 与 verifier，将 `audio_studio` 从 pending domain 移入 migrated domains。
- 当前 9 个 tracked 核心业务状态域均为 covered，pending domain 为 0；`scripts/shots` 继续由 `projects.raw_project_snapshot` 覆盖。
- 下一推荐步骤从本地域迁移切回 `staging_live_data_canary`：先执行服务器 live-data gate，再继续 app-level 双写、读切换、主写与回滚 canary。
- 本地验证：先修改 verifier 得到 RED，随后更新 coverage 生成器，`python3 scripts/verify_postgres_domain_coverage.py` 通过。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r73-postgres-domain-coverage-after-audio/`。

2026-06-18 阶段 7 R74 staging preflight：

- R73 后恢复服务器灰度前置检查，先执行 `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh`。
- 结果仍 blocked：DNS 返回 `198.18.1.154` fake-IP，源站 `47.79.99.190` route 仍为 `gateway 198.18.0.1 / interface utun1024`。
- 本轮是 network-only check，按脚本契约未进入 TCP/SSH/public-health，也未执行任何服务器命令、容器重启或业务数据库开关。
- 证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r74-network-preflight-before-staging/`。

2026-06-18 阶段 7 R75 final cutover readiness：

- 新增 `scripts/postgres_final_cutover_readiness.py` 与 `scripts/verify_postgres_final_cutover_readiness.py`，把最终脱离 JSON 前的门禁整理成可重复 artifact。
- 审计结果：domain coverage、live-data gate 域列表、staging sequence 顺序和服务器 fallback 契约均通过。
- 明确缺口：app-level canary 仍只覆盖 `video_studio_tasks`；最终切库前还需要全域 provider-free canary/smoke 覆盖 `studio_tasks`、`projects`、media metadata、project entities、benchmark records、user/config、sessions 和 `audio_studio`。
- 本地验证：RED 先确认 readiness 脚本缺失；实现后 `python3 scripts/verify_postgres_final_cutover_readiness.py` 通过，artifact 状态为 `needs_all_domain_app_canary`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r75-final-cutover-readiness/`。

2026-06-18 阶段 7 R76 all-domain provider-free canary：

- 新增 `scripts/postgres_staging_all_domain_canary.sh` 与 `scripts/verify_postgres_staging_all_domain_canary.py`。
- 默认 staging sequence 已从 video-only canary 切换为全域阶段：`audit -> roll-runtime -> live-data-gate -> all-domain-dual-write-canary -> all-domain-read-switch-canary -> all-domain-rollback-read-switch -> all-domain-primary-write-canary -> all-domain-rollback-primary-write`。
- 全域 canary 在 API 容器内使用 `StorageService`、`UserService` 和 `ConfigManager` 做维护写读删，不调用 DashScope/OSS/provider 生成接口；覆盖 9 个 tracked 核心业务状态域。
- 本地验证：`python3 scripts/verify_postgres_staging_all_domain_canary.py`、`python3 scripts/verify_postgres_staging_canary_sequence.py`、`python3 scripts/verify_postgres_final_cutover_readiness.py` 均通过；readiness artifact 状态为 `ready_for_final_cutover_sequence`。这只表示脚本契约就绪，服务器业务开关仍未执行。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r76-staging-all-domain-canary/`。

2026-06-18 阶段 7 R77 server sequence preflight：

- R76 后恢复服务器 sequence 前置检查，执行 `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh`。
- 结果仍 blocked：DNS 返回 `198.18.0.94` fake-IP，源站 `47.79.99.190` route 仍为 `gateway 198.18.0.1 / interface utun1024`。
- 本轮是 network-only check，按脚本契约未进入 TCP/SSH/public-health，也未执行任何远端命令、容器重启或业务数据库开关。
- 证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r77-network-preflight-before-server-sequence/`。

2026-06-18 阶段 7 R78 server fallback all-domain contract：

- 强化 `scripts/pre_studio_server_postgres_sequence.sh`：dry-run plan 与 run precheck 都会校验 staging sequence 包含 `live-data-gate` 和五个 all-domain canary 阶段。
- 服务器 fallback 现在还会检查 `scripts/postgres_staging_all_domain_canary.sh` 存在，并运行 `scripts/postgres_final_cutover_readiness.py`，要求状态为 `ready_for_final_cutover_sequence`。
- 本地验证：先更新 verifier 得到 RED，随后实现脚本契约，`python3 scripts/verify_pre_studio_server_postgres_sequence.py` 通过；本轮仅 dry-run contract，服务器业务开关未启用。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r78-server-fallback-all-domain-contract/`。

2026-06-18 阶段 7 R79 direct-rule preflight retry：

- 在本机 Clash 增加 direct 规则后复跑 `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh`。
- 结果仍 blocked：DNS 仍返回 `198.18.0.94` fake-IP，源站 `47.79.99.190` route 仍为 `gateway 198.18.0.1 / interface utun1024`。
- 本轮是 network-only check，未进入 TCP/SSH/public-health，也未执行任何远端命令、容器重启或业务数据库开关。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r79-network-preflight-before-server-sequence/`。

2026-06-18 阶段 7 R80 final JSON exit audit：

- 复跑 network-scope preflight，结果仍 blocked：DNS 仍为 `198.18.0.94`，源站 route 仍走 `utun1024`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r80-network-preflight-before-server-sequence/`。
- 新增 `scripts/postgres_final_json_exit_audit.py` 与 `scripts/verify_postgres_final_json_exit_audit.py`，把“完全脱离 JSON”拆成服务器 sequence 证据和最终运行态策略两个硬门禁。
- R80 audit 当前状态为 `needs_server_sequence_evidence`；最终 PostgreSQL-only 运行态要求 `MIEMIE_DATABASE_WRITE_MODE=postgres`、`MIEMIE_DATABASE_READ_MODE=postgres`、清空域 allowlist、关闭 `MIEMIE_DATABASE_JSON_FALLBACK_READ` 和 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES`，并开启 `MIEMIE_DATABASE_RECONCILE_STRICT=true`。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r80-final-json-exit-audit/`。

2026-06-18 阶段 7 R81 post JSON exit validation：

- 新增 `scripts/postgres_post_json_exit_validation.sh` 与 `scripts/verify_postgres_post_json_exit_validation.py`，作为 final JSON exit audit 通过后的后置执行门禁。
- 该脚本默认 dry-run；显式 `CONFIRM_POST_JSON_EXIT_VALIDATION=run` 后会先确认 final JSON exit audit 为 `ready_for_post_json_exit_validation`，再滚动 `api/worker/worker-video` 到最终策略、检查本机与公网 `/api/health`、执行 9 个 tracked 核心域 reconcile、采集 Compose ps 与 `docker stats --no-stream`，并跑 k6 S1 读负载门禁。
- 当前 artifact 状态为 `dry_run`，未执行服务器。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r81-post-json-exit-validation/`。

2026-06-18 阶段 7 R82 apply final JSON exit policy：

- 新增 `scripts/postgres_apply_final_json_exit_policy.sh` 与 `scripts/verify_postgres_apply_final_json_exit_policy.py`。
- 该脚本默认 dry-run；显式 `CONFIRM_APPLY_FINAL_JSON_EXIT_POLICY=run` 后会备份 `compose.env`，写入最终 PostgreSQL-only 运行态策略，并复跑 final JSON exit audit，要求状态为 `ready_for_post_json_exit_validation`。
- 当前 artifact 状态为 `dry_run`，本地没有服务器 `compose.env`，因此只生成计划，未修改服务器配置。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r82-apply-final-json-exit-policy/`。

2026-06-18 阶段 7 R83 rollback final JSON exit policy：

- 新增 `scripts/postgres_rollback_final_json_exit_policy.sh` 与 `scripts/verify_postgres_rollback_final_json_exit_policy.py`。
- 该脚本默认 dry-run；显式 `CONFIRM_ROLLBACK_FINAL_JSON_EXIT_POLICY=run ROLLBACK_ENV_BACKUP_FILE=<backup-file>` 后会保存回滚前 env、恢复 R82 备份、滚动 `api/worker/worker-video`，并检查本机与公网 `/api/health`。
- 当前 artifact 状态为 `dry_run`，未修改服务器配置。证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r83-rollback-final-json-exit-policy/`。

2026-06-18 阶段 7 R84 server final exit sequence：

- 新增 `scripts/pre_studio_server_postgres_final_exit_sequence.sh` 与 `scripts/verify_pre_studio_server_postgres_final_exit_sequence.py`，把服务器 sequence、最终策略应用、post JSON exit validation 和失败回滚串成一个服务器侧总入口。
- 该脚本默认 dry-run；显式 `CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run` 后会先跑服务器 sequence，再应用最终 PostgreSQL-only 运行态，随后执行 post JSON exit validation；若最终策略应用或后置验证失败，默认尝试 R83 rollback。
- 本地验证：server final exit sequence verifier 与 shell syntax 通过，并生成 R84 dry-run artifact。SSH 探针显示到 `47.79.99.190:22` 连接建立后在 key exchange 前关闭，同时 `route -n get 47.79.99.190` 仍走 `utun1024`，说明域名 DIRECT 规则没有覆盖 IP SSH；服务器 sequence 仍未执行、最终 JSON exit 未执行。

2026-06-18 阶段 7 R85 remote final exit sequence：

- 新增 `scripts/pre_studio_remote_postgres_final_exit_sequence.sh` 与 `scripts/verify_pre_studio_remote_postgres_final_exit_sequence.py`，把本机 connectivity preflight、远端 ff-only 同步和 R84 服务器最终 exit 总入口串成一个本机远程执行入口。
- 该脚本默认 dry-run；显式 `CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE=run` 后会先跑本机 connectivity preflight，通过后 SSH 到 `/opt/miemie-pre`，执行 `git merge --ff-only origin/pre`，再以 `CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run SERVER_SYNC=none` 调用服务器总入口。
- 本地验证：先观察 verifier 因缺少脚本失败，随后实现脚本并通过 verifier 与 shell syntax；R85 dry-run artifact 已生成。服务器 sequence 仍未执行、最终 JSON exit 未执行。

后续建议继续拆分：

- `api.ts` 下一刀：继续按 domain 提取 benchmark / media library 等 API，仍从 `api.ts` re-export。
- `CapabilityCreateModal.tsx` 下一刀：拆能力参数区域等子组件或 hook；不重做 UI。
- Smoke 后续：随创建/编辑表单拆分继续补编辑提交等更重路径。

## 结论

- 当前 `miemie-pre` 运行态基础门禁通过。
- 公网域名 `pre-studio.miemie.co` 的 Cloudflare -> aaPanel/Nginx -> `127.0.0.1:18100` 反代门禁通过，可作为下一轮 S4 混合查询基线的真实入口。
- S4 保守基线通过：公网链路相比本机链路有可见但很小的额外延迟，本轮未观察到 5xx 或 header 缺失。
- W2 阶梯压测 v1 显示平台侧 P95 余量充足；已修复并复跑 preview 阶梯，`preview-payload` 提交状态码 `200 120`，5xx 阻塞项解除。
- W2 状态观察本机 100 VU 通过；Cloudflare 公网路径连续出现过 k6 request timeout。切到 DNS only 后 timeout 消失，公网 100 VU 通过，300 VU 稳定性通过但 P95 `307.78ms` 略超保守门槛；恢复 Cloudflare 后 100 VU 一度再次出现 timeout；修复 StorageService 竞态并关闭临时 Skip 后，2026-06-03 Cloudflare 100 VU 已通过。300 VU 同窗口对照显示 app direct / 本机 Nginx 仍通过，源站公网 IP forced P95 `325.81ms` 略超，Cloudflare P95 `512.92ms` 且有 1 次连接超时。本地客户端侧经 Clash TUN/fake-ip 代理出口访问 Cloudflare 时，100 VU P95 `925.75ms`；添加 domain DIRECT 规则后系统层仍走 fake-ip/TUN，100 VU P95 `969.79ms`；关闭 TUN/fake-ip 后干净直连 Cloudflare 100 VU 无失败、无 header 缺失，但 P95 仍为 `734.57ms`；本机 TUN 美国代理样本 100 VU 无失败、无 header 缺失，但 P95 `960.63ms`。由于网站不关注大陆访问效果，本地跨境/代理客户端 P95 只作为风险记录，不作为目标市场硬门禁。
- 无 key 体验路径证明：列表快、提交即时反馈、重复点击被去重、失败状态可见。
- 下一步优先级：新 Mac 或新服务器先跑 `./run.sh doctor`，Compose 路径补 `DOCTOR_PROFILE=compose ./run.sh doctor`；数据库灰度恢复有两条路：若继续从本机执行，先用 `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh` 快速确认 DNS 与 route 干净，再让完整 preflight 退出 `0`，最后运行 `CONFIRM_REMOTE_FINAL_EXIT_SEQUENCE=run scripts/pre_studio_remote_postgres_final_exit_sequence.sh`；若本机 Clash/TUN 仍阻塞，则直接在服务器 `/opt/miemie-pre` 中运行 `CONFIRM_SERVER_FINAL_EXIT_SEQUENCE=run scripts/pre_studio_server_postgres_final_exit_sequence.sh`。该总入口会串行执行服务器 sequence、最终策略应用、post JSON exit validation 和失败回滚路径。R45/R46/R49/R50/R51/R52/R53 已把本机远程路径固化成脚本和 verifier，R54 补齐部署环境自检，R55/R65 补齐 blocked 时的 remediation 输出，R56/R58/R65/R74/R77/R79/R80 证明当前 Clash DIRECT/IP-CIDR 规则尚未作用到命令行路径，R57 增加快速 network scope，R58 增加服务器终端自运行后备入口，R64/R65 补齐 app-level canary 前的服务器 live data gate 与 fallback 契约，R66 将本机 remote wrapper 对齐到同一 server fallback，R68-R72 已完成 `audio_studio` 本地迁移闭环，R73 已确认 9 个 tracked 核心业务状态域 pending 为 0，R75 已确认最终切库前还缺全域 provider-free app canary，R76 已补齐全域 canary 契约并把 readiness 推进到 `ready_for_final_cutover_sequence`，R78 已补强服务器 fallback 执行前全域契约校验，R80 已补齐 final JSON exit audit，R81 已补齐 post JSON exit validation runner，R82 已补齐最终策略应用 runner，R83 已补齐最终策略回滚 runner，R84 已补齐服务器侧最终 exit 总入口，R85 已补齐本机远程最终 exit 总入口；R48 已补齐本地全域实库演练通过证据。应用 500 已清零，Cloudflare 100 VU 已恢复通过，300 VU 主要瓶颈已收窄到源站公网/Cloudflare 边缘链路。本地跨境直连与美国代理样本均已补齐为风险记录。W2 平台侧阶段可收口；阶段 7 已完成服务器 live migration/backfill/reconcile，但尚未完成新版 Alembic/session/audio 域 live data gate、全域 app canary 实跑、业务开关灰度和最终切库；下一步仍需服务器终端 fallback 或清理本机 TUN/fake-IP 后执行 final exit sequence。
