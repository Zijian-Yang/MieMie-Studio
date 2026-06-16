# 2026-05-23 未完成工作实施计划

## 背景

当前项目处于 `pre` 高性能/生产运行时实验分支。本地代码验证已经通过，主要未完成项集中在服务器验证闭环、线上体验验证、前端/路由大文件治理，以及后续扩容路线尚未重新按“小而美、易维护、支持数百在线”的目标收敛。

用户明确约束：

- 平台预期同时在线用户约数百人，不追求特别高可用或复杂架构。
- 目标是支持约一两百人同时进行较大量图片/视频生成与查询。
- 网站速度要持续保持快，用户之间尽量互不影响。
- 维护要简单轻松，避免重型、运维压力大、难排障的技术栈。
- 后续技术栈和架构选择需要再讨论再决定；2026-05-23 晚间用户随后明确要求按原扩容路线先推进 Redis + Celery，PostgreSQL / SSE 后置。

## 2026-05-23 执行口径更新

用户后续指令已经覆盖本计划最初“暂不引入 Redis / Celery”的保守口径：本轮按原扩容路线执行，但仍保持小步可回滚。

当前执行结果：

- 阶段 1 `pre` 服务器验证闭环：已补齐 S1、S3、低频 DashScope smoke、资源快照和报告。
- 阶段 2 Redis：已最小实装 Redis session、slowapi Redis storage、health Redis 状态，并在服务器验证通过。
- 阶段 3 Worker：已最小实装 Celery + Redis broker、统一 dispatcher、图片工作室生成链路入队，并在服务器验证 API 快速返回和 worker 消费。
- 阶段 3.5 Redis + Worker 稳定性验收补强：Redis restart / unavailable 路径通过；worker restart 后恢复 ping / registered。任务提交后重启 worker 留下 `generating` 超时任务的问题已用 stale 兜底修复，并已补跑 1 个真实 DashScope 图片队列 smoke。
- 阶段 4 PostgreSQL / SSE：仍按用户计划后置，仅保留 spec / 设计准备，不迁核心数据、不替换轮询。
- 阶段 5 代码治理：尚未开始拆 `frontend/src/services/api.ts` 和 `VideoStudioPage.tsx`，作为下一批未完成工作。

## 2026-05-24 下一阶段执行口径

Redis + Celery 图片 Worker、视频 `worker-video` v1、pre 服务器真实 DashScope 图片/视频 smoke 均已闭环。下一阶段以“线上/准线上体验验证 + 小而美性能治理 + 代码维护性治理”为主，不进入 PostgreSQL / SSE，不扩大基础设施。

当前新起点：

- `miemie-pre` 服务器门禁通过：`/api/health redis.ok=true`、`GET /` 200、图片 worker 与 video worker 均可 `ping`，注册任务包含 `studio.generate` 和 `video_studio.generate`。
- 无 key 体验 smoke 通过：图片工作室列表/创建/重复生成去重、视频工作室创建/失败路径、错误可见性与临时项目清理均通过。
- 轻量性能治理已开始：新增高频运行路径脱敏耗时日志，新增 S4 “多人查询 + 少量提交” k6 草案。
- 代码治理已开始第一刀：`frontend/src/services/apiClient.ts` 承载 transport，`frontend/src/services/api.ts` 保持原业务 API 聚合入口。

新增证据：

- `docs/reports/2026-05-24-next-phase-experience-and-performance.md`
- `docs/reports/artifacts/2026-05-24-next-phase-experience/no-key-experience-smoke-20260524.json`
- `loadtest/k6/s4-mixed-query-generate.js`

## 总原则

1. 先补完已经承诺但未闭环的验证与文档，不急着引入新基础设施。
2. 每一步都先量化现状，再决定是否需要改架构。
3. 优先使用当前已有栈：FastAPI、React、Ant Design、Zustand、Compose、JSON 存储、现有测试和 k6 资产。
4. 能通过限流、公平调度、前端轮询节制、缓存、页面拆分解决的问题，先不升级为重型架构问题。
5. 任何会改变部署复杂度的技术选择，都单独开 spec / ADR 并和用户确认后再实施。

## 阶段 0：确认当前工作树与文档基线

状态：已完成一次盘点，见 `docs/reports/2026-05-23-project-progress-review.md`。

后续动作：

- 保持本轮新增计划与报告可追溯。
- 后续每个阶段完成后，更新对应 report、`docs/README.md` 和必要的 `docs/ISSUES.md`。

验收：

- `git status` 中只包含本轮计划/报告/文档入口变更，或后续明确归属的实施变更。

## 阶段 1：补齐 `pre` 服务器验证闭环

目标：把 2026-05-18 卡住的服务器验证补完，先知道现有 Compose 单机路径真实表现。

动作：

1. 重新 SSH 到服务器，确认 sshd、Docker、Compose、旧服务和 `miemie-pre` 服务状态。
2. 确认 `/opt/miemie-pre` 中的 `pre` 服务仍健康，必要时只重启 `miemie-pre`，不动旧实验服务。
3. 检查 `/tmp/miemie-pre-auth.token` 和验证用户是否仍可用；失效则重新创建一次性验证用户。
4. 创建或确认一个平台侧状态观察任务。
5. 补跑 S1 纯读 k6。
6. 补跑 S3 状态观察 k6。
7. 补跑 1 个低频真实 DashScope smoke，只验证提交、状态观察、平台落状态，不做供应商并发压测。
8. 采集压测后 `docker stats`、容器日志摘要、磁盘/内存快照。
9. 更新 `docs/reports/2026-05-18-pre-server-validation.md`，归档 summary JSON 和脱敏 smoke 摘要。

状态：已完成。

验收：

- `/api/health` 和 `GET /` 继续通过。
- S1/S3 HTTP 失败率低于 1%。
- S1 P95 维持在既有阈值内。
- S3 请求量符合轮询间隔预期，没有明显轮询放大。
- smoke 任务能成功落到平台状态，或失败时记录明确的供应商/配置原因。
- 报告中不包含 API key、密码、token、真实私有 URL。

证据：

- `docs/reports/2026-05-18-pre-server-validation.md`
- `docs/reports/artifacts/2026-05-18-pre-server/`

## 阶段 2：Step 02 Redis 最小接入

目标：按原扩容路线先接 Redis，但只用于 session、限流和后续短缓存基础设施，保留文件 session 兜底。

已完成动作：

1. Compose 新增 `redis:7-alpine`，使用独立 `redis_data` volume。
2. 新增 `RedisSessionStore`，登录写 Redis + 文件，读取 Redis 优先、文件兜底并可回填。
3. 登出删除 Redis + 文件 session。
4. 改密码后清理该用户所有 Redis / 文件 session。
5. slowapi 通过 `MIEMIE_RATE_LIMIT_STORAGE_URI` 使用 Redis DB 1。
6. `/api/health` 暴露 Redis configured / ok 状态。
7. 服务器 `miemie-pre` 验证 Redis session、rate-limit key、登出、改密失效全部通过。

状态：已完成最小可用版本。

后续待评估：

- Redis 不可用时当前策略是文件 session 兜底、限流回退受 slowapi storage 初始化影响；是否要做更细的运行时降级告警，留到下一轮稳定性治理。
- 短缓存尚未接具体业务接口，需等热点接口证据明确。

证据：

- `backend/app/services/session_store.py`
- `backend/app/services/rate_limit.py`
- `docs/specs/2026-04-step-02-redis-session-cache-rate-limit.md`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/auth-redis-session-smoke-20260523.txt`
- `docs/reports/artifacts/2026-05-24-redis-worker-stability/redis-worker-core-20260524.json`

## 阶段 3：Step 03 Worker 队列最小接入

目标：先引入 Celery + Redis broker，让图片工作室生成不占用 API 请求路径；视频工作室、音频和测评后置。

已完成动作：

1. 新增 `backend/app/celery_app.py` 与 `backend/app/worker_tasks.py`。
2. 新增 `backend/app/services/task_dispatcher.py`，router 不直接依赖 Celery API。
3. 图片工作室 `/generate` 切到统一 dispatcher。
4. Compose 新增 `worker` 服务，使用 Redis DB 2 作为 broker、DB 3 作为 result backend。
5. 服务器验证 worker `ping`、`registered`，注册任务包含 `studio.generate`。
6. 服务器验证图片工作室 API 约 157.5ms 返回 `generating`，worker 接走任务并受控写回失败状态。

状态：已完成图片工作室最小可用版本。

2026-05-24 稳定性补强结论：

- Redis 正常路径、`restart redis`、短暂停 Redis 与恢复后 session 兜底均通过，未出现未捕获 `500`。
- Worker 受控 `restart worker` 后可恢复 `celery inspect ping`，`registered` 包含 `studio.generate`，API health 不受影响。
- 无供应商 key 的图片工作室失败路径可快速返回 `generating` 并最终进入 `failed`。
- 同一任务连续触发两次 generate 均返回现有 `generating` 状态，没有观察到重复终态污染。
- 原阻塞：任务提交后立即重启 worker，该任务 150 秒后仍为 `generating`。该问题已通过 stale 兜底修复，并在 pre 服务器验证通过。

2026-05-24 Worker stale 修复进展：

- 图片工作室生成请求新增 `generation_attempt` 元数据，包含 attempt id、dispatcher、Celery task id、dispatch/start/heartbeat/finish 时间和 stale 超时。
- Worker 开始执行和最终写回前校验 attempt id，旧 attempt 不再覆盖新 attempt。
- `GET /api/studio/{task_id}`、任务列表和再次 generate 前会检测 stale `generating`；默认 30 分钟后标记 `failed`，不自动重投递。
- 已补后端回归覆盖 attempt 写入、重复提交不重复 dispatch、stale GET 失败、stale 后重新生成、旧 attempt 不覆盖新 attempt、worker 异常失败写回。
- 已部署到 pre 服务器 `977457bb4aa8e1b89d7f9fcb1efac5bf32820006`，临时设置 `MIEMIE_STUDIO_GENERATION_STALE_SECONDS=90` 并重建 `api` / `worker`。
- pre 验证通过：同一任务连续两次 generate 复用同一个 attempt；提交后立即 `restart worker`，任务在约 93 秒后由 stale 兜底标记为 `failed`，`failure_reason=stale_generating`。
- 真实 DashScope 图片队列 smoke 已补跑通过：恢复 `MIEMIE_STUDIO_GENERATION_STALE_SECONDS=1800` 后，`wan2.6-t2i` 任务约 `167ms` 返回 `generating`，最终 `completed`，平台记录 1 个图片结果和 1 个 request id。
- 测试用户临时 key 已删除，补充检查确认服务器用户配置中没有 DashScope / production / test key。

2026-05-24 视频工作室 Worker 迁移 v1 本地进展：

- 视频工作室创建/重新生成链路已从直接 `asyncio.create_task` 改为统一 dispatcher，默认仍支持本地 `asyncio`，Compose 下通过 `MIEMIE_VIDEO_STUDIO_DISPATCHER=celery` 入队。
- Celery 新增 `video_studio.generate`，Compose 新增独立 `worker-video` 服务消费 `video_studio` 队列，图片 worker 继续只消费 `studio` 队列。
- `VideoStudioTask` 新增 `submit_state`、`submit_started_at`、`submit_attempt_id`，并在 `provider_result_meta.worker_attempt` 记录 dispatcher、Celery task id、heartbeat、submit stale 和 worker stale 窗口。
- 已实现 submit timeout 兜底：`processing + task_ids=[]` 超时后标记 `failed`，写入 `submit_error.error_code=SubmitTimeout`，不自动重投供应商任务。
- 已实现 worker stale 恢复：`processing + task_ids!=[]` 且 worker heartbeat stale 时，只重新入队状态协调，不重复 submit。
- 已补后端回归覆盖创建入队、启动恢复、submit timeout、worker stale recovery、旧 attempt 不覆盖、删除后旧 worker 不复活、provider error 元数据保留和旧 JSON 兼容读取。
- 本地验证通过：`backend/tests/test_video_studio_capabilities.py -q`、`./run.sh test`、前端 typecheck/lint/build、`docker compose config`。
- 已部署到 pre 服务器 `7f736affd91a503dd007580af335b0254f3cceb4`；`compose.env` 的 `MIEMIE_RUNTIME_GIT_COMMIT` 已对齐，`api/worker/worker-video` 已重建，Redis 未重建。
- pre 基础验收通过：`/api/health redis.ok=true`、`GET /` 200、Celery `ping` 2 nodes online，`registered` 包含 `studio.generate` 和 `video_studio.generate`。
- pre 无 key 失败路径通过：视频任务创建约 `157.8ms` 返回 `processing`，dispatcher 为 `celery`，最终进入 `failed`，未永久卡住。
- pre `worker-video restart` 基础恢复通过：restart 后 `worker-video` 恢复 online，`ping` 2 nodes online；server override 已补 `worker-video: image: miemie-studio:pre-local`，避免新增服务使用默认 `local` 镜像名。
- pre 真实 DashScope 视频 smoke 已补跑通过：1 个 `wan2.7-t2v` 文生视频任务最终 `succeeded`，供应商 task id / request id / video URL 各 1 个；SSH 外层连接中断后从服务器任务文件恢复核验，测试用户 key 与 `/tmp` 临时 key 均已清理，artifact 脱敏。

后续待完成：

- 评估 worker 非 root 运行与容器权限硬化。

证据：

- `backend/app/services/task_dispatcher.py`
- `backend/app/worker_tasks.py`
- `docs/specs/2026-04-step-03-async-job-orchestrator.md`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/worker-dispatch-smoke-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/celery-registered-post-worker-image-20260523.txt`
- `docs/reports/artifacts/2026-05-24-redis-worker-stability/redis-worker-core-20260524.json`
- `docs/reports/artifacts/2026-05-24-worker-stale-fix-server/worker-stale-fix-20260524.json`
- `docs/reports/artifacts/2026-05-24-worker-stale-fix-server/dashscope-image-smoke-20260524.json`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/README.md`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/runtime-gates-20260524.txt`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/no-key-failure-20260524.json`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/worker-video-restart-20260524.txt`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/worker-video-image-aligned-20260524.txt`
- `docs/reports/artifacts/2026-05-24-video-worker-migration/real-video-smoke-20260524.json`

## 阶段 4：线上图片工作室修复验证

目标：确认“本地已修复”的图片工作室卡顿和生成按钮无响应问题，在线上或准线上环境真实改善。

动作：

1. 用测试账号复现图片工作室页面切换、打开任务详情、点击生成、关闭/重开任务详情。
2. 检查开发者模式未展开时是否停止自动请求 heavy preview。
3. 检查生成按钮点击后是否立即进入提交中 / generating 状态。
4. 检查重复点击是否被前后端去重。
5. 抽查 Cloudflare / 源站日志里是否还出现 `/api/studio/preview-payload`、`/api/studio/{id}/generate` 的 520/522/524。
6. 若验证通过，更新 `docs/ISSUES.md` 状态为已验证；若仍有问题，补最小复现和接口耗时证据。

验收：

- 页面切换没有长时间全页转圈。
- 生成请求有即时反馈。
- heavy preview 不再在普通浏览中频繁触发。
- 线上验证结论落盘。

状态：

- API 层体验 smoke 已通过：列表接口快速返回，图片生成重复点击复用 attempt，无 key 失败可见。
- 浏览器真实 UI 操作开始补齐时发现生产前端白屏：`react-vendor` / `vendor` 与 AntD 子 chunk 之间存在初始化循环，登录页 body 为空并出现 `createContext` / `Cannot access before initialization` 控制台错误。
- 已收敛 Vite 手动分包策略：React 生态依赖保持在 `react-vendor`，Ant Design 主包统一进入 `antd-vendor`，不再按组件生成 `antd-button`、`antd-form`、`antd-_util` 等子 chunk。
- 已新增 `npm run test:vite-chunks` 回归脚本，防止后续重新引入 AntD 子 chunk 循环。
- 已部署到 `miemie-pre` 运行版本 `32ff189a57ca13cafcc73f7dd6e956ca1d8ce1e9`；真实浏览器验证登录页不再白屏，登录/注册切换可交互，控制台无 error/warn，页面只预加载单一 `antd-vendor`。
- 2026-05-25 已补齐工作室真实浏览器门禁：测试用户创建临时项目后进入图片工作室，任务列表/详情可渲染，无长时间全页转圈；普通模式下创建图片任务并点击生成，页面约 3.4 秒内出现“提交中...”，随后无 key 路径进入 `failed / API key 未配置`，错误可见。
- 2026-05-25 已用服务器日志复核：本轮浏览器验证窗口内 `/api/studio/preview-payload` 命中数为 `0`，`/api/studio/{id}/generate` 返回 `200` 且运行态观测耗时约 `235.27ms`；临时项目已清理。
- 验证噪声：SSH 隧道在首次 lazy chunk 加载时被远端关闭，导致一次 `Failed to fetch dynamically imported module`；重建隧道后 `/_static/StudioPage-kkK5922i.js` 可 `200` 获取，刷新同一路由后工作室正常渲染，记录为隧道稳定性问题，不作为前端发布缺陷。
- 2026-05-29 已补齐公网反代门禁：`pre-studio.miemie.co` 经 Cloudflare / aaPanel Nginx 反代到 `127.0.0.1:18100`，`/api/health`、`/`、`/login` 与主静态资源均返回 `200`；`/_static/index-CiWzNZJv.js` 二次请求出现 `cf-cache-status: HIT`，真实浏览器登录页与注册切换可交互，控制台无 error/warn。

## 阶段 5：保持小而美的性能治理

目标：在不引入新重型组件的前提下，让现有单机/Compose 路径更稳，支撑数百在线和一两百活跃生成/查询用户的体验目标。

动作：

1. 整理当前关键路径：
   - 登录与鉴权
   - 项目/任务列表读取
   - 图片工作室生成与状态查询
   - 视频工作室生成与状态查询
   - 图片/视频测评运行与状态查询
2. 给这些路径补轻量观测字段或日志摘要，只记录耗时、状态、用户隔离标识、请求 ID，不记录敏感内容。
3. 检查前端轮询：
   - 空闲页面不轮询
   - 弹窗关闭后清理轮询
   - 状态终态后停止轮询
   - 失败时退避
4. 检查生成任务公平性：
   - 防止单用户连续提交过多任务影响其他用户
   - 供应商限流和平台任务状态要清楚提示
   - 先用已有模型限流能力，不新增队列系统
5. 检查文件读写热点：
   - 找出高频列表接口是否反复全目录扫描
   - 对只读 registry / capability 结果优先做进程内短缓存或前端缓存
   - 不在本阶段迁数据库
6. 补一轮针对“多人查询 + 少量生成”的 k6 场景草案，为后续架构讨论提供数字。

验收：

- 不增加新的必需基础设施。
- 多用户状态查询不会明显互相拖慢。
- 供应商任务受限时，页面反馈清楚，不表现为按钮无响应。
- 形成一份“是否需要新技术栈”的证据清单，而不是凭感觉升级架构。

状态：

- 已新增运行态脱敏耗时日志，覆盖图片/视频工作室与测评查询高频路径。
- 已新增 `loadtest/k6/s4-mixed-query-generate.js`，可用于下一轮只读查询或 preview/无 key 受控提交混合压测。
- 公网反代入口 `https://pre-studio.miemie.co` 已通过基础门禁，下一轮 S4 建议同时采集公网入口与服务器本机 `127.0.0.1:18100` 的对照数据。
- 2026-05-29 已完成 S4 两段式保守基线：本机/公网只读查询和本机/公网 preview 受控提交四组均失败率 `0`、P95 `<800ms`；公网 preview P95 `38.33ms`、P99 `86.22ms`。证据归档于 `docs/reports/artifacts/2026-05-29-s4-public-baseline/`。
- 2026-05-30 已执行 W2 阶梯压测 v1：只读 `50/100/200 VU` 和 preview `10/20/30 VU` 的本机/公网 P95 均达到门槛；公网读 200 VU P95 `177.44ms`，公网 preview 30 VU P95 `88.89ms`。但日志分类发现 `preview-payload` 共 `120` 次提交中有 `1` 次 `500`，traceback 指向 per-user `config.json` 首次并发初始化写入竞态，因此严格结论为 W2 v1 **不完全通过**。证据归档于 `docs/reports/artifacts/2026-05-29-w2-staircase-baseline/`。
- 2026-05-30 已修复 per-user config 首次并发初始化竞态并复跑 preview 阶梯：本机/公网 `10/20/30 VU` 均通过，服务端 `preview-payload` 状态码为 `200 120`、无 5xx；公网 preview 30 VU P95 `71.63ms`。证据归档于 `docs/reports/artifacts/2026-05-30-w2-preview-config-fix/`。
- 2026-05-30 已补跑 W2 状态观察阶梯：本机 `100 VU / 120s` 通过，`23872` 个 GET 失败率 `0`、P95 `17.37ms`；公网 `100 VU / 120s` P95 `138.40ms`、失败率 `0.020%`，但出现 4 个 k6 `request timeout`，导致 12 个响应 check 失败并按保守门禁停止。API 侧观察类 GET 状态码汇总为 `200 43785`，未观察到应用 4xx/5xx。证据归档于 `docs/reports/artifacts/2026-05-30-w2-status-observation/`。
- 2026-05-30 已补跑 W2 公网链路对照：应用直连、Nginx 本机源站、Nginx 源站公网 IP 三组 `100 VU / 120s` 均通过；Cloudflare 公网域名复测 P95 `409.26ms`，出现 5 个 k6 `request timeout`，API 侧观察类 GET 汇总为 `200 88423`。瓶颈已收窄到 Cloudflare/公网代理链路。证据归档于 `docs/reports/artifacts/2026-05-30-w2-link-comparison/`。
- 2026-05-31 已在 Cloudflare DNS only 后复跑公网状态观察阶梯：DNS 解析为 `47.79.99.190`，响应头 `server: nginx`；公网 `100 VU / 120s` 通过，P95 `45.92ms`；公网 `300 VU / 120s` 无失败、无 timeout、无 header check 失败，但 P95 `307.78ms` 略超 `300ms` 门槛，按规则停止。证据归档于 `docs/reports/artifacts/2026-05-31-w2-dns-only-staircase/`。
- 2026-05-31 已恢复 Cloudflare 代理并复验真实入口：Cloudflare `100 VU / 120s` P95 `207.86ms`，但出现 9 个 k6 `request timeout`，导致 27 个响应 check 失败并按规则停止；API 侧观察类 GET 汇总为 `200 18253`。证据归档于 `docs/reports/artifacts/2026-05-31-w2-cloudflare-entry-retune/`。
- 2026-06-01 已在关闭 Cloudflare `HTTP/3 (with QUIC)` 后复验真实入口：Cloudflare `100 VU / 120s` P95 `190.14ms`，timeout 从 9 个降到 5 个，check failures 从 27 降到 15，但仍未清零；API 侧观察类 GET 汇总为 `200 19451`，压测后 health 和 Compose 仍健康。证据归档于 `docs/reports/artifacts/2026-06-01-w2-cloudflare-http3off/`。
- 2026-06-01 已在 Cloudflare 为压测来源 IP 与 `/api/*` 部署临时 Skip 规则后复验真实入口：Cloudflare `100 VU / 120s` P95 `195.03ms`，出现 15 个 timeout，check failures 为 45；同时发现 `GET /api/video-studio?project_id=<id>` 1 个 500，traceback 指向 `StorageService._write_json_with_lock()` 固定 `<task_id>.tmp` 并发写入竞态。证据归档于 `docs/reports/artifacts/2026-06-01-w2-cloudflare-skip-rule/`。
- 2026-06-01 已本地修复 `StorageService._write_json_with_lock()` 固定 tmp 文件竞态：临时文件改为 pid/thread/uuid 唯一路径；新增 `backend/tests/test_storage_service.py` 并按 TDD 确认旧实现复现 `FileNotFoundError`、修复后通过；`venv/bin/pytest backend/tests -q` 为 `235 passed`。
- 2026-06-01 已部署 StorageService 修复到 pre：运行版本 `00091f21f5ee207f78a1092e7e5e164ab4567c7f`，容器内并发回归 `2 passed`，Cloudflare `100 VU / 120s` 复跑后 API 侧观察类 GET 汇总为 `200 19263`、无 500；Cloudflare 仍有 7 个 timeout，check failures 为 21。证据归档于 `docs/reports/artifacts/2026-06-01-w2-storage-fix-cloudflare-rerun/`。
- 2026-06-03 已在关闭 Cloudflare 临时 Skip 规则后做 Ray 诊断：Cloudflare `100 VU / 120s` 通过，P95 `36.75ms`、失败率 `0`、check failures `0`、API 侧 `200 23061`；随后 Cloudflare `300 VU / 120s` 无 timeout、无 check failure、API 侧 `200 49577`，但 P95 `351.64ms` 超过 `300ms` 门槛，按规则停止。证据归档于 `docs/reports/artifacts/2026-06-03-w2-cloudflare-ray-diagnostics/`。
- 2026-06-03 已完成 300 VU 入口对照：应用直连 P95 `244.29ms`、本机 Nginx P95 `271.69ms`，两组均通过；源站公网 IP forced P95 `325.81ms` 略超但无失败；Cloudflare 真实入口 P95 `512.92ms`，有 1 个 `dial: i/o timeout`，API 侧窗口仍全 `200`。证据归档于 `docs/reports/artifacts/2026-06-03-w2-300-entry-comparison/`。
- 2026-06-03 已补本地客户端侧 Cloudflare 复测，但预检确认本机走 Clash Verge TUN / fake-ip：`dig` 返回 `198.18.2.211`，route 走 `utun1024`。该代理出口路径下 `100 VU / 120s` 失败率 `0`、check failures `0`，但 P95 `925.75ms`，按规则停止；API 侧窗口仍全 `200`。证据归档于 `docs/reports/artifacts/2026-06-03-w2-client-cloudflare-baseline/`。
- 2026-06-04 已在 Clash Verge 为 `pre-studio.miemie.co` 添加 domain DIRECT 规则后复测本地客户端侧 Cloudflare 入口；预检仍显示 `dig` 返回 `198.18.2.211`，route 走 `utun1024`，说明当前 TUN/fake-ip 仍在接管域名。`100 VU / 120s` 失败率 `0.019%`、P95 `969.79ms`、P99 `1401.50ms`，按规则停止；API 侧窗口为 `200 10523`，未观察到应用 4xx/5xx 放大。证据归档于 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-direct-rule/`。
- 2026-06-04 已在关闭 Clash TUN/fake-ip 后复测干净本地直连 Cloudflare 入口；预检显示 DNS 为 Cloudflare 真实 IP `172.67.201.59` / `104.21.85.29`，route 走 `en0`。`100 VU / 120s` 失败率 `0`、check failures `0`，但 P95 `734.57ms`、P99 `1080.36ms`，按原始 `300ms` 门槛停止；API 侧窗口为 `200 12685`。用户确认该网站不关注大陆访问效果，因此该本地跨境客户端 P95 只作为风险记录，不作为目标市场硬门禁。证据归档于 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-clean-direct/`。
- 2026-06-04 已补本机 TUN 美国代理入口样本：路径为本地 Mac -> Clash 美国代理节点 -> Cloudflare -> 源站，Cloudflare colo 为 `DEN`。最新有效 `100 VU / 120s` 失败率 `0`、check failures `0`，但 P95 `960.63ms`、P99 `1315.98ms`；API 侧窗口为 `200 11159`。该代理样本稳定性通过但尾延迟高，不作为目标市场硬门禁。证据归档于 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-us-proxy/`。

下一步补跑前置：

- W2 preview 5xx 阻塞项已解除。
- Cloudflare 代理路径 timeout 已通过 DNS only 对照确认；DNS only 下公网 100 VU 已通过，300 VU 稳定性通过但 P95 略超；关闭 HTTP/3/QUIC 后 Cloudflare timeout 有改善但未清零；临时 Skip 规则未能清零 timeout。
- StorageService 固定 tmp 文件竞态已部署并确认应用 500 清零。
- Cloudflare 100 VU 已在 2026-06-03 恢复通过；300 VU 同窗口对照显示 app direct / 本机 Nginx 可以过门槛，源站公网路径略超，Cloudflare 真实入口明显超。本地 Clash TUN 代理出口、domain DIRECT 但仍走 TUN、关闭 TUN 后干净直连、以及本机 TUN 美国代理样本均已补齐；这些客户端样本稳定性没有暴露应用 4xx/5xx，但 P95 高，不作为目标市场硬门禁。
- 下一轮不先改应用架构；W2 平台侧阶段可收口。后续如需更准的目标市场入口 SLO，再从美国或目标地区 VPS 原生网络跑 k6；否则进入阶段 6 代码治理。

## 阶段 6：代码治理，降低维护压力

目标：先把后续最容易出问题的大文件拆小，降低维护成本。只做行为保持型重构。

优先顺序：

1. 拆 `frontend/src/services/api.ts`
   - 先分 transport、shared types、domain API。
   - 不改接口语义。
   - 每拆一小步跑 typecheck/lint。

   状态：已完成第一刀 transport 拆分，新增 `frontend/src/services/apiClient.ts`；阶段 6A 已拆出 `frontend/src/services/studioApi.ts` 与 `frontend/src/services/videoStudioApi.ts`，`api.ts` 继续 re-export，页面 import 路径保持不变。后续继续按 domain API 分组或进入页面拆分。

2. 拆 `frontend/src/pages/VideoStudio/VideoStudioPage.tsx`
   - 提取数据加载、任务列表、任务详情、能力表单、媒体预处理。
   - 主页面保留编排逻辑。
   - 不重做 UI，不换状态管理。

   状态：阶段 6B 已完成十一刀。第一刀新增 `frontend/src/pages/VideoStudio/taskViewUtils.ts`，提取任务类型解析、输入素材归一化、参数摘要和预览图选择等纯工具函数；第二刀新增 `frontend/src/pages/VideoStudio/useVideoStudioData.ts`，承载任务列表、素材库、模型配置占位状态、初始加载和后台任务轮询启动逻辑；第三刀新增 `frontend/src/pages/VideoStudio/TaskListPanel.tsx`，承载任务列表卡片、空状态、创建入口、批量删除入口和单任务查看/删除动作；第四刀新增 `frontend/src/pages/VideoStudio/TaskDetailModal.tsx`，承载任务详情弹窗、输入素材展示、生成结果、标记按钮、保存到视频库、保存尾帧和开发者模式展示；第五刀新增 `frontend/src/pages/VideoStudio/useVideoStudioTaskActions.ts`，承载保存到视频库、提取尾帧、视频标记、单任务删除、全部删除和重新生成动作；第六刀删除 `VideoStudioPage.tsx` 中两个 `{false && ...}` 包裹的旧创建/编辑弹窗及其专属旧状态/handler；第七刀新增 `frontend/src/pages/VideoStudio/DeveloperPreviewPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出开发者模式提交状态、canonical 请求体、厂商请求体和 warning 展示；第八刀新增 `frontend/src/pages/VideoStudio/VideoFieldLabel.tsx`，收敛素材、Mask 和提示词区域共用的字段标题、必填星号和 hover 帮助；第九刀新增 `frontend/src/pages/VideoStudio/ReferenceCollectionsPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出参考图片/视频选择、已选参考素材、参考音色、顺序调整、删除和指代词按钮挂载；第十刀新增 `frontend/src/pages/VideoStudio/MaskEditorPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出局部编辑 Mask 展示、工具按钮、警告和编辑模式复用提示；第十一刀新增 `frontend/src/pages/VideoStudio/InputAssetSelector.tsx`，从 `CapabilityCreateModal.tsx` 拆出首帧、尾帧、音频、首段视频、待编辑视频和源视频选择器。`VideoStudioPage.tsx` 现仅保留任务列表、创建/编辑弹窗挂载、详情弹窗和少量编排逻辑，当前创建/编辑能力统一走 `CapabilityCreateModal`。后续继续治理时，优先拆 `CapabilityCreateModal.tsx` 的能力参数区域。

3. 补前端 smoke tests
   - 登录页 smoke。
   - 项目列表 smoke。
   - 至少一个工作室创建流程 smoke。

   状态：已补项目列表 smoke、视频工作室任务列表/详情弹窗 smoke、视频工作室文生视频创建流程 smoke、参考素材创建流程 smoke，以及局部编辑源视频/Mask 面板 smoke。`frontend/e2e/smoke.spec.ts` 现有项目列表样本覆盖登录态进入 `/projects`、已有项目卡片、描述、分镜/角色统计和打开/删除入口；视频工作室 mock 成功任务覆盖任务卡片、状态/Provider/进度、打开详情、输入素材、关键参数、生成结果、提示词、编辑/重生成、保存到视频库、保存尾帧和开发者模式入口；创建流程样本 mock `/api/video-studio/capabilities`、`/api/video-studio/preview-payload` 与 `POST /api/video-studio`，覆盖新建任务弹窗、文生视频能力、参考素材能力、局部编辑能力、提示词填写、参考图选择、源视频准备、Mask 面板出现、提交成功和新任务卡片/请求体回显。后续 smoke 可随页面拆分继续补编辑提交等更重路径。

4. 视风险再拆 `StudioPage` / `FramesPage`
   - 等前两项稳定后再做。

验收：

- 行为保持。
- `npm run typecheck`、`npm run lint`、相关脚本测试通过。
- 拆分后的文件边界写入对应 docs 或 report。

## 阶段 7：架构选型讨论检查点

本阶段只准备讨论材料，不直接实施新技术栈。

状态：已新增 `docs/adr/ADR-0003-pre-database-architecture-checkpoint.md` 作为数据库阶段前检查点，并在用户确认后接受 Compose 内 PostgreSQL 作为最终核心业务状态库。已新增 `docs/plans/2026-06-06-postgres-upgrade-optimization-plan.md`，明确 JSON 过渡、双写对账、分域读切换和最终数据库主数据源路线；第一实施域建议为视频工作室任务索引/任务状态。2026-06-07 已新增 `docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md` 作为 goal 模式执行路线，并完成 preflight artifact `docs/reports/artifacts/2026-06-07-postgres-upgrade-preflight/`：本地工具链、后端关键测试、前端 typecheck/chunk 检查、服务器 SSH/Compose/health、Cloudflare health 均通过，服务器已预拉取 `postgres:16-alpine`。R1/R2 本地实现已完成：Compose PostgreSQL、database health、备份/恢复脚本和 health 测试已落地，业务读写仍默认 JSON。`video_studio_tasks`、`studio_tasks`、`projects`、media metadata、`project_entities` 和 benchmark records 均已完成 schema/repository、backfill/reconcile、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；`project_entities` 覆盖角色、场景、道具、首帧、视频和风格，benchmark records 覆盖图片/视频测评 dataset、suite 和 run。R35-R39 已完成 user/config schema/repository、backfill/reconcile、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；session 继续 Redis + file fallback。R48 已完成本地临时 Compose PostgreSQL 实库演练，覆盖 Alembic、全域 backfill/reconcile、备份和恢复；R43 已完成服务器 live migration/backfill/reconcile 和备份/恢复演练；R44 中断在新镜像 build/SSH banner 恢复阶段，未重启容器也未启用业务开关；R45/R46/R49/R50/R51/R52/R53 已补可重复服务器 canary 脚本、app-free 本地 verifier、read-switch/rollback、primary-write/rollback 门禁、全序列 runner、本地 connectivity preflight 和一键远程编排；R54 已新增 `./run.sh doctor` 部署前只读自检，用于 Mac/单服务器/Compose 环境提前发现工具链、`compose.env`、敏感文件误跟踪和端口问题。默认运行态仍为 file-only，下一步先让 `./run.sh doctor` 与 `scripts/pre_studio_connectivity_preflight.sh` 均退出 `0`，再用 `CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh` 逐级进入 staging 小域灰度和回滚验证。

需要回答的问题：

1. 用现有 Compose 单机 + 轻量优化，是否已经能覆盖目标人数和体验？
2. 主要瓶颈到底是：
   - 前端轮询
   - JSON 文件扫描
   - API worker 被长任务占用
   - 供应商限流
   - 带宽/OSS/临时资源
   - 还是服务器规格不足
3. 如果确实需要新增组件，最小可接受方案是什么？
4. 新组件是否值得它带来的备份、监控、升级、排障成本？

候选方向只作为讨论，不作为当前决策：

- 保持 JSON + 文件锁，但补索引和缓存。
- 引入 Compose 内 PostgreSQL，并允许 JSON 过渡一段时间。
- 引入 Redis 只做 session / 限流 / 短缓存。
- 引入轻量后台任务进程，但不直接上复杂队列。
- 引入更完整的队列和数据库方案。

验收：

- 形成新的 spec / ADR 草案。
- 用户确认后才进入实施。

## 当前建议执行顺序

1. 已完成阶段 1：服务器验证闭环。
2. 已完成阶段 2：Redis 最小接入与服务器验证。
3. 阶段 3 Worker 图片工作室最小接入已完成。
4. 阶段 3.5 Redis + Worker 稳定性补强已闭环：Redis restart / unavailable、worker restart stale 兜底和 1 个真实 DashScope 图片队列 smoke 均已验证。
5. 视频工作室 Worker 迁移 v1 已完成本地实现、pre 基础部署、无 key 失败路径、`worker-video` restart 基础恢复和 1 个真实 DashScope 视频 smoke；视频 worker v1 服务器验收已闭环。
6. Compose PostgreSQL R1/R2 本地实现已完成；服务器 rollout 已启动但未闭环，当前记录在 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r1-r2-staging/`。R3 本地 schema/Alembic 已完成并记录在 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r3-local-schema/`。R4 本地 repository boundary 已完成并记录在 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r4-local-repository/`。R5 本地 backfill/reconcile 已完成并记录在 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r5-backfill-reconcile/`。R6 runtime dual-write/read-switch/primary-write 已完成。R8-R12 `studio_tasks`、R13-R17 `projects`、R19-R23 media metadata、R24-R28 project entities、R30-R34 benchmark records 均已完成本地域 schema/repository、backfill/reconcile、dual-write、read-switch 和 primary-write 闭环。R35-R39 user/config 本地域也已完成相同本地门禁。R41 已新增本地 live database rehearsal 脚本；R48 已在本机临时 Compose PostgreSQL 完成 Alembic、全域 backfill/reconcile、备份和恢复演练；R42 服务器 repo 已更新到 `e731245` 并启动 `postgres`；R43 已完成服务器 Alembic、live backfill/reconcile、备份和恢复演练。R44 尝试进入 `video_studio_tasks` staging dual-write canary，但中断在新镜像 build/SSH banner 恢复阶段，未重启容器也未启用数据库业务开关。R45 已新增可重复服务器脚本 `scripts/postgres_staging_video_task_canary.sh`，R46 已新增 `scripts/verify_postgres_staging_canary_script.py` 作为不加载 app 的本地安全 verifier，R49/R50 已补 `read-switch-canary`、`rollback-read-switch`、`primary-write-canary` 和 `rollback-primary-write`；R51 已新增 `scripts/postgres_staging_video_task_sequence.sh` 全序列 runner，R52 已新增 `scripts/pre_studio_connectivity_preflight.sh` 本地连通性门禁，R53 已新增 `scripts/pre_studio_remote_postgres_sequence.sh` 远程编排，R54 已新增 `./run.sh doctor` 部署前只读自检。当前应用运行态仍默认 file-only，服务器最终切库未完成。下一步：部署环境 doctor 与 connectivity preflight 均通过后，用 R53 wrapper 先只读审计镜像/容器/health，再继续 staging dual-write 小域灰度、staging read switch 和 staging primary-write；SSE 继续后置，不与数据库第一阶段绑定。

## 暂不做

- 不引入 RabbitMQ / Kubernetes / 微服务拆分。
- 不一次性全量替换 JSON，不把 PostgreSQL 与 SSE 绑成同一轮大改。
- 不做真实供应商高并发压测。
- 不合并旧实验服务数据目录。
- 不改反向代理边界。
- 不为了追求“高可用”增加明显超过当前规模需求的复杂度。
