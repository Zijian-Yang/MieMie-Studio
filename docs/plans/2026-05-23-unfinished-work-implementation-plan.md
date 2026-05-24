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

## 阶段 6：代码治理，降低维护压力

目标：先把后续最容易出问题的大文件拆小，降低维护成本。只做行为保持型重构。

优先顺序：

1. 拆 `frontend/src/services/api.ts`
   - 先分 transport、shared types、domain API。
   - 不改接口语义。
   - 每拆一小步跑 typecheck/lint。

2. 拆 `frontend/src/pages/VideoStudio/VideoStudioPage.tsx`
   - 提取数据加载、任务列表、任务详情、能力表单、媒体预处理。
   - 主页面保留编排逻辑。
   - 不重做 UI，不换状态管理。

3. 补前端 smoke tests
   - 登录页 smoke。
   - 项目列表 smoke。
   - 至少一个工作室创建流程 smoke。

4. 视风险再拆 `StudioPage` / `FramesPage`
   - 等前两项稳定后再做。

验收：

- 行为保持。
- `npm run typecheck`、`npm run lint`、相关脚本测试通过。
- 拆分后的文件边界写入对应 docs 或 report。

## 阶段 7：架构选型讨论检查点

本阶段只准备讨论材料，不直接实施新技术栈。

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
- 引入轻量 SQLite / 单机数据库。
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
6. PostgreSQL / SSE 继续后置，基于 Redis + Worker 图片工作室稳定基线通过后的数据再讨论。

## 暂不做

- 不引入 RabbitMQ / Kubernetes / 微服务拆分。
- 不立即引入 PostgreSQL / SSE。
- 不做真实供应商高并发压测。
- 不合并旧实验服务数据目录。
- 不改反向代理边界。
- 不为了追求“高可用”增加明显超过当前规模需求的复杂度。
