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
- W2 阶梯压测 v1 显示平台侧 P95 余量充足；已修复并复跑 preview 阶梯，`preview-payload` 提交状态码 `200 120`，5xx 阻塞项解除。
- W2 状态观察本机 100 VU 通过；Cloudflare 公网路径连续出现过 k6 request timeout。切到 DNS only 后 timeout 消失，公网 100 VU 通过，300 VU 稳定性通过但 P95 `307.78ms` 略超保守门槛；恢复 Cloudflare 后 100 VU 一度再次出现 timeout；修复 StorageService 竞态并关闭临时 Skip 后，2026-06-03 Cloudflare 100 VU 已通过。300 VU 同窗口对照显示 app direct / 本机 Nginx 仍通过，源站公网 IP forced P95 `325.81ms` 略超，Cloudflare P95 `512.92ms` 且有 1 次连接超时。
- 无 key 体验路径证明：列表快、提交即时反馈、重复点击被去重、失败状态可见。
- 下一步仍不需要进入 PostgreSQL / SSE；应用 500 已清零，Cloudflare 100 VU 已恢复通过，300 VU 主要瓶颈已收窄到源站公网/Cloudflare 边缘链路。下一步聚焦 Cloudflare/TLS/压测来源位置对照和入口 SLO 分层。
