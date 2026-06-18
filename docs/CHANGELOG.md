# 变更日志

> 记录平台的重要变更、新功能和 Bug 修复。
> 格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/)。

## [Unreleased]

### 修复 (Fixed)
- `miemie-pre` StorageService 修复部署：运行版本 `00091f21f5ee207f78a1092e7e5e164ab4567c7f` 复跑 Cloudflare `100 VU / 120s` 后 API 侧观察类 GET 为 `200 19263`、无 500；Cloudflare timeout 仍独立存在，证据归档到 `docs/reports/artifacts/2026-06-01-w2-storage-fix-cloudflare-rerun/`。
- JSON 文件存储：`StorageService._write_json_with_lock()` 原子写入改用唯一临时文件，避免多个 worker 进程并发保存同一目标 JSON 时共享 `<name>.tmp` 触发 `FileNotFoundError`；新增并发回归覆盖该场景。
- 用户配置写入：per-user `config.json` 原子写入改用唯一临时文件，避免多个 worker 进程首次并发初始化同一用户配置时共享 `config.tmp` 触发 `FileNotFoundError`；pre 复跑 preview 阶梯后 `preview-payload` 状态码为 `200 120`、无 5xx。
- 图片工作室 pre 体验门禁：真实浏览器验证工作室页面可渲染、生成点击有“提交中...”即时反馈，普通模式未自动触发 heavy `/api/studio/preview-payload`。
- 前端生产构建：Ant Design 主包不再按组件强拆为多个 `antd-*` 子 chunk，避免生产环境出现 `createContext` / `Cannot access before initialization` 循环依赖白屏。
- 图片工作室 Worker 试点：生成任务新增 `generation_attempt` 元数据和 stale `generating` 兜底；worker 中断或重启后，超时任务会被标记失败，旧 attempt 不再覆盖新 attempt。
- 图片工作室 Worker 试点：pre 服务器已验证 `restart worker` 后任务不会永久停留 `generating`，90 秒测试窗口后会进入 `failed` 并记录 `failure_reason=stale_generating`。
- 图片工作室 Worker 试点：pre 服务器已补跑 1 个真实 DashScope 图片队列 smoke，任务快速返回 `generating` 并最终 `completed`，测试用户临时 key 已删除。
- 视频工作室：任务卡片的类型、Provider、状态和完成进度支持换行布局，避免 HappyHorse 等较长标签把“已完成”和 `1/1` 挤出卡片。
- 视频工作室：HappyHorse 提示词长度改为中文 2 单位、非中文 1 单位的加权检测，并在前后端保持一致。
- 视频工作室：HappyHorse 参考生视频新建提示改为 `[Image 1]` / `[Image 2]` 指代参考图，匹配新版 API 文档。
- `deployment_version` 与运行时 `git_commit` 统一对齐，避免健康检查和响应头口径不一致。
- 视频工作室状态接口不再因前端轮询而直接触发厂商状态查询和副作用写入。
- 前端多个页面重复实现的轮询逻辑收敛为同一套 hook，降低状态查询放大与清理遗漏风险。
- 修复 Docker Compose 容器启动时 `sh -lc` 重置 `PATH`，导致找不到 venv 内 `gunicorn` 的问题。
- 修复 OSS 未启用时 DashScope 成功视频结果被标记为失败的问题，改为保留供应商视频 URL。
- 视频工作室后台提交与状态协调器改为显式使用目标用户存储，避免后台协程在测试或异步边界下依赖 `contextvars` 代理导致任务状态写入错误目录。

### 安全 (Security)
- **密码哈希**: 用户密码从明文存储改为 bcrypt 哈希，新注册用户自动使用 bcrypt，已有明文密码在首次登录时自动迁移
- **认证中间件**: 从 Starlette `BaseHTTPMiddleware` 重写为纯 ASGI 实现，修复 `contextvars` 在并发请求间泄漏的问题
- **原子文件写入**: `storage.py`、`config.py`、`user_service.py` 的 JSON 写入改为 temp→fsync→os.replace 原子操作，防止进程崩溃导致数据文件损坏
- **CORS 配置**: 从硬编码改为环境变量 `MIEMIE_CORS_ORIGINS` 驱动，修复 `origins=["*"]` + `credentials=True` 违反 CORS 规范的问题
- **接口限流**: 登录接口添加 slowapi 限流 5次/分钟，注册接口 3次/分钟，防止暴力破解

### 新增 (Added)
- 数据库升级 R78 server fallback all-domain contract：服务器自运行入口 `pre_studio_server_postgres_sequence.sh` 现在在执行前强制校验 all-domain canary 脚本、全域 sequence 阶段和 final cutover readiness `ready_for_final_cutover_sequence`，避免服务器 fallback 误跑旧 video-only 门禁。
- 数据库升级 R77 server sequence preflight：R76 后尝试恢复服务器 sequence 前置检查，network-scope preflight 仍 blocked；DNS 返回 Clash fake-IP `198.18.0.94`，源站 `47.79.99.190` route 仍走 `utun1024`。本轮未进入 TCP/SSH/public-health，未执行任何远端命令或业务数据库开关。
- 数据库升级 R76 all-domain provider-free canary：新增 `scripts/postgres_staging_all_domain_canary.sh` 与 verifier，默认 staging sequence 改为 `audit -> roll-runtime -> live-data-gate -> all-domain-dual-write-canary -> all-domain-read-switch-canary -> all-domain-rollback-read-switch -> all-domain-primary-write-canary -> all-domain-rollback-primary-write`。final cutover readiness 现在为 `ready_for_final_cutover_sequence`，下一步回到服务器执行 sequence。
- 数据库升级 R75 final cutover readiness：新增 `scripts/postgres_final_cutover_readiness.py` 与 verifier，汇总 domain coverage、live-data gate、staging sequence、server fallback 和 app-level canary 覆盖度。当前状态为 `needs_all_domain_app_canary`：9 个域的 coverage/live-data/sequence/fallback 契约通过，但 app-level canary 仍只覆盖 `video_studio_tasks`，下一步需要新增全域 provider-free canary。
- 数据库升级 R74 staging preflight：R73 后回到服务器灰度前置检查，network-scope preflight 仍 blocked；DNS 返回 Clash fake-IP `198.18.1.154`，源站 `47.79.99.190` route 仍走 `utun1024`，因此本机 remote sequence 仍不可用，下一步需走服务器终端 fallback 或清理本机 TUN/fake-IP 后复测。
- 数据库升级 R73 coverage after audio：更新 PostgreSQL domain coverage 审计口径，将 `audio_studio` 纳入已覆盖本地域；当前 9 个核心业务状态域均具备本地 schema/repository/backfill/reconcile/runtime gates，pending tracked domain 为 0，下一步回到服务器 `staging_live_data_canary`。
- 数据库升级 R72 audio_studio PostgreSQL primary-write：新增音频工作室主写 feature flag，显式开启后音频任务与音色档案保存/删除以 PostgreSQL 为主；默认不写 JSON，`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时保留临时 JSON archive mirror。主写失败会冒泡且不落 JSON，避免切换窗口分叉状态；默认运行态仍为 JSON/file-only，服务器业务开关未启用。
- 数据库升级 R71 audio_studio read-switch：新增音频工作室读侧 feature flag，显式开启后音频任务、音色档案、项目列表和 `voice_id` 查询可优先读取 PostgreSQL；`MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时 miss/空列表/异常回退 JSON。默认运行态仍为 JSON/file-only，服务器业务开关未启用。
- 数据库升级 R70 audio_studio runtime dual-write：新增音频工作室运行态双写 feature flag，显式开启后音频任务与音色档案 JSON 主写/删除成功再 shadow 写 PostgreSQL；默认仍为 JSON/file-only，shadow 失败默认不打断主路径，严格模式才冒泡。
- 数据库升级 R69 audio_studio backfill/reconcile：新增音频任务与音色档案 JSON 回填、脱敏对账服务和维护脚本；摘要只输出安全索引字段、计数、缺失项和错误类型，不输出任务文本、prompt、音频 URL、provider payload、key/token/password 或私有用户数据。`postgres_live_rehearsal.sh` 与 staging live data gate 已纳入 `audio_studio` 域，默认运行态仍为 JSON/file-only。
- 数据库升级 R68 audio_studio 本地基础：新增 `audio_studio_tasks` 与 `voice_profiles` schema、Alembic migration `20260617_0009`、`AudioStudioRepository` 协议和 file/PostgreSQL/dual repository boundary；音频任务与音色档案完整快照保留在 JSONB，索引列覆盖项目列表、状态扫描和 voice_id 查询。运行态仍默认 JSON/file-only，未启用服务器业务开关。
- 数据库升级 R67 domain coverage audit：新增 `scripts/postgres_domain_coverage.py` 与 `scripts/verify_postgres_domain_coverage.py`，把 PostgreSQL 分域迁移覆盖面固化为可重复报告；当前 8 个 domain 已有本地 schema/repository/backfill/reconcile/runtime gates，剩余明确 JSON-only 业务状态域为 `audio_studio`（`audio_studio/*.json` 与 `voices/*.json`），下一迁移域建议为 `audio_studio`。本轮未执行服务器命令或业务开关。
- 数据库升级 R66 remote wrapper 对齐：`scripts/pre_studio_remote_postgres_sequence.sh` 现在默认在远端同步 `origin/pre` 后调用 `CONFIRM_SERVER_SEQUENCE=run SERVER_SYNC=none scripts/pre_studio_server_postgres_sequence.sh`，复用 R65 server fallback 的 `live-data-gate` 契约；本轮仅 dry-run/verifier 通过，服务器未执行。
- 数据库升级 R65 连通性 remediation 与服务器 fallback 契约：`pre_studio_connectivity_preflight.sh` 现在会在 route 被 `32.0.0.0/3` TUN 捕获时输出精确 `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve` 建议；`pre_studio_server_postgres_sequence.sh` 在 dry-run 和 run precheck 中显式检查 sequence 包含 `live-data-gate` 且 live gate 脚本存在。本轮真实 network-scope preflight 仍 blocked，服务器未执行。
- 数据库升级 R64 staging live data gate：新增 `scripts/postgres_staging_live_data_gate.sh` 与 `scripts/verify_postgres_staging_live_data_gate.py`，在 app-level canary 前先执行服务器侧 Alembic、全域 backfill/reconcile、PostgreSQL 备份和恢复演练；`scripts/postgres_staging_video_task_sequence.sh` 默认序列更新为 `audit -> roll-runtime -> live-data-gate -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write`。本轮仅本地 dry-run/verifier 通过，服务器未执行。
- 数据库升级 R63 sessions primary-write：新增 `sessions` 主写 feature flag，显式开启后 session 保存/删除/按用户清理以 PostgreSQL 为主，Redis 保持热 cache，`sessions.json` 默认不写、仅在 `MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时作为临时归档镜像；默认运行态不变。
- 数据库升级 R62 连通性复测：新增 Clash 直连规则后，network preflight 仍显示 fake-IP/TUN 路径；手动 TCP 22 可达但 SSH banner exchange 超时，远程 PostgreSQL sequence 未执行，证据归档到 `docs/reports/artifacts/2026-06-17-postgres-connectivity-direct-rule/`。
- 数据库升级 R61 sessions read-switch：新增 `sessions` 读侧 feature flag，显式开启 `MIEMIE_DATABASE_READ_DOMAINS=sessions` 或全局 PostgreSQL read mode 后，`get_user_by_token()` 可优先读取 PostgreSQL session；`MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时 miss/error 回退现有 Redis/file session 路径，默认运行态不变。
- 数据库升级 R60 sessions runtime dual-write：新增 `session_runtime` feature flag 边界，显式开启 `sessions` 双写域后，登录 session 保存、登出删除和改密清理会 shadow 写入 PostgreSQL；默认仍为 Redis + file fallback，shadow 失败默认不打断主路径，严格模式才冒泡，日志不记录 raw token。
- 数据库升级 R59 sessions PostgreSQL 本地基础：新增 `sessions` schema、Alembic migration `20260607_0008`、`PostgresSessionRepository`、脱敏 backfill/reconcile 服务和维护脚本；数据库仅保存 `token_hash`，不落 raw token，运行态仍保持 Redis + file fallback。`postgres_live_rehearsal.sh` 已纳入 `sessions` 域；本机新增 DIRECT 规则后 preflight 仍 blocked，DNS `198.18.0.124`、route `utun1024`、SSH banner 和公网 health 超时，未执行服务器命令或业务开关。
- 数据库升级 R58 server self sequence wrapper：再次补 Clash DIRECT 规则后完整 preflight 仍 blocked，DNS `198.18.0.100`、route `utun1024`、SSH banner 和公网 health 超时；新增 `scripts/pre_studio_server_postgres_sequence.sh` 与 `scripts/verify_pre_studio_server_postgres_sequence.py`，允许在服务器 `/opt/miemie-pre` 直接 dry-run 或显式执行同一套 staging PostgreSQL sequence，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r58-server-self-sequence-wrapper/`。
- 数据库升级 R57 network-scope preflight：`scripts/pre_studio_connectivity_preflight.sh` 新增 `MIEMIE_PREFLIGHT_SCOPE=network`，可在几秒内只检查 DNS fake-IP 与源站 route/TUN，不再每次等待 SSH/public health 超时；当前实跑仍 blocked，DNS 为 `198.18.0.100`、route 走 `utun1024`，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r57-network-scope-preflight/`。
- 数据库升级 R56 DIRECT 规则复测：用户在 Clash 中添加 DIRECT 规则后复跑 `scripts/pre_studio_connectivity_preflight.sh`，本机命令路径仍 blocked，DNS 仍为 `198.18.0.100`、route 仍走 `utun1024`、SSH banner 超时、公网 health 20 秒超时；远端 PostgreSQL sequence 未执行，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r56-direct-rule-still-blocked/`。
- 数据库升级 R55 connectivity rediagnosis：`scripts/pre_studio_connectivity_preflight.sh` 新增 `remediation.md` 输出，自动汇总 fake-IP DNS、TUN route、SSH banner 和 public health timeout 的恢复动作；本轮实跑仍 blocked，DNS 为 `198.18.0.100`、route 走 `utun1024`、SSH banner 超时、公网 health 20 秒超时，未执行服务器命令或业务开关，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r55-connectivity-preflight-rediagnosis/`。
- 部署体验 R54 deploy doctor：新增 `scripts/deploy_doctor.sh`、`scripts/verify_deploy_doctor.py` 与 `./run.sh doctor`，提供 Mac/单服务器/Compose 部署前只读自检；默认不安装依赖、不修改配置、不启动服务，检查工具链、关键文件、敏感文件误跟踪、`compose.env` 占位值、Docker/Compose 可用性和端口占用，本机实跑 `passed_with_warnings` 并归档到 `docs/reports/artifacts/2026-06-17-deploy-doctor/`。
- 数据库升级 R53 remote PostgreSQL sequence wrapper：新增 `scripts/pre_studio_remote_postgres_sequence.sh` 与 `scripts/verify_pre_studio_remote_postgres_sequence.py`，把 R52 本地连通性 preflight 与 R51 服务器 sequence 串起来；默认 dry-run，显式 `CONFIRM_REMOTE_SEQUENCE=run` 后先跑 preflight，通过后才 SSH 到 `/opt/miemie-pre`，用 `git merge --ff-only origin/pre` 同步并执行 `CONFIRM_STAGING_SEQUENCE=run`。当前实跑停在本地 preflight，未进入远端命令。
- 数据库升级 R52 staging connectivity preflight：新增 `scripts/pre_studio_connectivity_preflight.sh` 与 `scripts/verify_pre_studio_connectivity_preflight.py`，在执行 R51 服务器灰度序列前统一检查 DNS fake-IP、TUN route、TCP 22、SSH banner 与公网 health。当前预检结果为 blocked：DNS `198.18.0.80`，route `utun1024`，TCP 22 可达但 SSH banner 被关闭，public health 出现 HTTP/2 framing error；未执行服务器命令或业务开关。
- 数据库升级 R51 staging sequence runner 与连通性复查：新增 `scripts/postgres_staging_video_task_sequence.sh` 与 `scripts/verify_postgres_staging_canary_sequence.py`，默认 dry-run，显式 `CONFIRM_STAGING_SEQUENCE=run` 后按 `audit -> roll-runtime -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write` 逐级执行并失败即停。本轮 SSH 仍在 banner exchange 超时，DNS/route 仍走 fake-IP/TUN，未执行服务器命令或业务开关。
- 数据库升级 R50 staging primary-write/rollback 自动化：扩展 `scripts/postgres_staging_video_task_canary.sh`，新增显式 `primary-write-canary` 与 `rollback-primary-write` 模式；primary canary 证明 PostgreSQL 主写且不生成 JSON archive，rollback canary 证明回到 JSON 主写并保留 PostgreSQL shadow 写。服务器业务开关仍未执行，等待 SSH 命令路径恢复。
- 数据库升级 R49 staging read-switch/rollback 自动化：扩展 `scripts/postgres_staging_video_task_canary.sh`，新增显式 `read-switch-canary` 与 `rollback-read-switch` 模式；通过 JSON/PG 分叉状态 canary 证明读切换后读取 PostgreSQL、回滚后读取 JSON，并加强 verifier 自动编译脚本内嵌 Python。服务器业务开关仍未执行，等待 SSH 命令路径恢复。
- 数据库升级 R48 本地实库演练通过：修复 `scripts/postgres_live_rehearsal.sh` 查找备份扩展名与 `postgres_backup.sh` 输出不一致的问题，重跑临时 Compose PostgreSQL、Alembic、全域 backfill/reconcile、`.sql` 备份和 restore rehearsal 全链路通过；原始本地用户明细不入库，只提交脱敏摘要。
- 数据库升级 R46 staging canary verifier：新增 `scripts/verify_postgres_staging_canary_script.py`，在不加载后端 app、不依赖 Docker daemon 或服务器 `compose.env` 的情况下校验 R45 灰度脚本；覆盖 shell 语法、缺 env blocked precheck、不触碰 Docker、默认只读、安全开关和 no-provider smoke 契约。服务器 dual-write 仍未开启，等待 SSH banner 路径恢复后再执行脚本三段门禁。
- 数据库升级 R45 staging canary 自动化：新增 `scripts/postgres_staging_video_task_canary.sh`，把 R44 恢复后的审计、新镜像滚动和 `video_studio_tasks` dual-write canary 固化为三段显式模式；默认只读 `audit`，`roll-runtime` 保持 `MIEMIE_DATABASE_ENABLED=false`，`dual-write-canary` 才开启单域双写，并通过容器内维护写入验证 JSON 主写与 PostgreSQL shadow 写，不触发真实供应商调用。
- 数据库升级 R44 staging dual-write canary 预备中断：尝试进入 `video_studio_tasks` dual-write canary 前，先将服务器 `compose.env` 的 runtime commit 更新为 `e731245` 并保持 `MIEMIE_DATABASE_ENABLED=false`；构建 `miemie-studio:pre-local` 期间 SSH 会话超时，后续 SSH banner 仍因本机 `utun1024`/fake-IP 路径超时。本轮未重启容器，未启用数据库业务开关，未开始 dual-write canary。
- 数据库升级 R43 staging live migration/backfill/reconcile：服务器 PostgreSQL 已执行 Alembic 到 `20260607_0007`，全域 backfill/reconcile 均通过，备份与恢复演练通过；应用运行态仍未启用数据库读写开关，现有本机和 Cloudflare health 均为 `200`。
- 数据库升级 R42 staging 恢复：服务器 SSH 一度恢复后，`/opt/miemie-pre` 已 fast-forward 到 `e731245`，并启动 `postgres` 服务且 `pg_isready` 接受连接；现有 API health 仍为 `200`，但在 build 最新 `api` 镜像期间 SSH 控制面再次 banner 超时，尚未执行 Alembic/backfill/reconcile，也未启用任何数据库业务开关。
- 数据库升级 R41 本地实库演练脚本：新增 `scripts/postgres_live_rehearsal.sh`，可在临时 Compose PostgreSQL 上串联 `alembic upgrade head`、全域 backfill/reconcile、备份和恢复演练；本机实跑因 Docker daemon 不可用在 `docker-precheck` 产出 blocked artifact，未修改业务数据或服务器状态。
- 数据库升级 R40 staging 连通性复查：user/config 本地门禁完成后只读复查服务器路径，DNS 仍返回 `198.18.2.211`、源站路由走 `utun1024`、TCP 22 可达但 SSH banner 超时，公网 `/api/health` 20 秒超时；本轮未修改服务器状态。
- 数据库升级 R39 user/config PostgreSQL primary-write：新增 `user_config` 主写开关和可选 JSON archive mirror；显式启用后注册、登录更新、改密码和 per-user config 保存以 PostgreSQL 为主，主写失败不落 JSON 分叉状态，focused `7 passed`，目标回归 `33 passed`，后端全量 `399 passed`。
- 数据库升级 R38 user/config read-switch：新增 `user_config` 读侧 feature flag 与 JSON fallback；用户 ID/token 恢复和 per-user config 读取可显式优先 PostgreSQL，登录密码校验仍保持 JSON 主路径，focused `7 passed`，目标回归 `26 passed`，后端全量 `392 passed`。
- 数据库升级 R37 user/config runtime dual-write：新增 `user_config` 写侧 feature flag，注册、登录更新、改密码和 per-user config 保存仍以 JSON 为主，显式启用后 shadow 写 PostgreSQL；shadow 失败默认不打断 JSON 主路径，focused `6 passed`，目标回归 `19 passed`，后端全量 `385 passed`。
- 数据库升级 R36 user/config backfill/reconcile：新增 `users.json` 与 per-user `config.json` 回填、脱敏对账服务和维护脚本；摘要只输出计数、缺失项和字段名，不输出 password hash、key/token、完整配置或私有用户数据，focused `5 passed`，目标回归 `13 passed`，后端全量 `379 passed`。
- 数据库升级 R35 user/config 本地基础：新增 `users` 与 `user_configs` schema、Alembic migration `20260607_0007`、用户/配置 PostgreSQL repository boundary 和安全索引字段；登录、session 和配置运行态仍默认走 JSON/Redis，focused `8 passed`，目标回归 `13 passed`，后端全量 `374 passed`。
- 数据库升级 R34 benchmark records PostgreSQL primary write：新增图片/视频测评 dataset、suite、run 主写开关和可选 JSON archive mirror；显式启用后保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，后端全量 `366 passed`。
- 数据库升级 R33 benchmark records read-switch：新增图片/视频测评 dataset、suite、run 的 PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式启用后单条读取、项目列表和 suite run 列表可优先读 PostgreSQL，后端全量 `362 passed`。
- 数据库升级 R32 benchmark records runtime dual-write：新增图片/视频测评 dataset、suite、run 的写侧 feature flag，默认 file-only；显式启用后 JSON 主写/删除成功再 shadow 写 PostgreSQL，shadow 失败默认不打断 JSON 主路径，后端全量 `358 passed`。
- 数据库升级 R31 benchmark records backfill/reconcile：新增图片/视频测评 dataset、suite、run 的 JSON 扫描、PostgreSQL upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；摘要不包含 prompt、provider payload、request id、task id、key/token/password、私有 URL、名称或描述，后端全量 `354 passed`。
- 数据库升级 R30 benchmark records 本地基础：新增图片/视频测评 dataset、suite、run 的统一 PostgreSQL schema、Alembic migration `20260607_0006` 和 file/PostgreSQL repository boundary；运行态仍默认 JSON/file-only，后端全量 `351 passed`。
- 数据库升级 R29 staging 连通性刷新：服务器 rollout 前置检查仍显示 operator path 经 Clash/fake-IP 与 `utun1024`，公网 health 超时，TCP 22 可达但 SSH 命令被远端关闭；本轮未修改服务器状态，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r29-staging-connectivity-refresh/`。
- 数据库升级 R28 project entities PostgreSQL primary write：新增角色、场景、道具、首帧、视频和风格主写开关和可选 JSON archive mirror；显式启用后保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，后端全量 `346 passed`。
- 数据库升级 R27 project entities read switch：新增角色、场景、道具、首帧、视频和风格 PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式开启后 get/list 以及 frame/video by-shot、video by-task 可优先读 PostgreSQL，后端全量 `342 passed`。
- 数据库升级 R26 project entities runtime dual-write：新增角色、场景、道具、首帧、视频和风格写侧 feature flag，默认 file-only；显式开启后 JSON 主写/删除成功再 shadow 写 PostgreSQL，shadow 失败默认不打断 JSON 主路径，后端全量 `338 passed`。
- 数据库升级 R25 project entities backfill/reconcile：新增角色、场景、道具、首帧、视频和风格 JSON 扫描、PostgreSQL upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；摘要不包含名称、描述、prompt、text style body、provider task id、key/token/password 或私有 URL，后端全量 `334 passed`。
- 数据库升级 R24 project entities 本地基础：新增 `project_entities` schema、Alembic migration `20260607_0005`、角色/场景/道具/首帧/视频/风格统一 repository boundary；运行态仍默认 JSON/file-only，后端全量 `331 passed`。
- 数据库升级 R23 media metadata PostgreSQL primary write：新增图库、音频库、视频库和文本库主写开关和可选 JSON archive mirror；显式启用后保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，后端全量 `324 passed`。
- 数据库升级 R22 media metadata read switch：新增图库、音频库、视频库和文本库 PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式启用后 get/list 可优先读 PostgreSQL，miss/空列表/异常可回退 JSON，后端全量 `320 passed`。
- 数据库升级 R21 media metadata runtime dual-write：新增 `media_metadata` 写侧 feature flag，默认 file-only；显式启用后图库、音频库、视频库和文本库 JSON 主写/删除成功再 shadow 写 PostgreSQL，shadow 失败默认不打断 JSON 主路径，后端全量 `316 passed`。
- 数据库升级 R20 media metadata backfill/reconcile：新增图库、音频库、视频库和文本库 metadata 的 JSON 扫描、PostgreSQL upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；对账只比较安全索引字段，不包含文本内容、prompt、provider payload、key/token/password 或私有 URL，后端全量 `313 passed`。
- 数据库升级 R19 media metadata 本地基础：新增 `media_assets` 与 `text_items` schema、Alembic migration `20260607_0004`、图库/音频库/视频库/文本库 file/PostgreSQL repository boundary；文件本体仍留在 OSS/URL，运行态默认 file-only，后端全量 `310 passed`。
- 数据库升级 R18 staging 连通性刷新：只读检查显示本机仍经 Clash TUN/fake-IP 路径，SSH 命令被远端关闭、公网 health 超时，TCP 22 可达但不足以执行服务器 rollout；本轮未修改服务器状态，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r18-staging-connectivity-refresh/`。
- 数据库升级 R17 `projects` PostgreSQL primary write：新增项目主写开关和可选 JSON archive mirror；显式启用后项目保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，后端全量 `301 passed`。
- 数据库升级 R16 `projects` read switch：新增项目 PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式启用后项目详情与项目列表优先读 PostgreSQL，miss/空列表/异常可回退 JSON，后端全量 `297 passed`。
- 数据库升级 R15 `projects` runtime dual-write：新增项目写侧 feature flag，默认 file-only；显式启用后 JSON 主写/删除成功再 shadow 写 PostgreSQL，shadow 失败默认不打断 JSON 主路径，后端全量 `293 passed`。
- 数据库升级 R14 `projects` backfill/reconcile：新增项目 JSON 扫描、PostgreSQL repository upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；摘要不包含项目名、描述、剧本内容、model config 细节、prompt、key/token/password 或私有 URL，后端全量 `290 passed`。
- 数据库升级 R13 `projects` 本地基础：新增项目 PostgreSQL schema、Alembic migration `20260607_0003`、`ProjectRepository` 协议和 file/PostgreSQL/dual repository；运行态仍默认 JSON/file-only，后端全量 `287 passed`。
- 数据库升级 R12 `studio_tasks` PostgreSQL primary write：新增图片工作室任务主写开关和可选 JSON archive mirror；显式启用后图片任务保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，后端全量 `280 passed`。
- 数据库升级 R11 `studio_tasks` read switch：新增图片工作室任务 PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式启用后任务详情与项目任务列表优先读 PostgreSQL，miss/异常可回退 JSON，后端全量 `276 passed`。
- 数据库升级 R10 `studio_tasks` runtime dual-write：新增图片工作室任务写侧 feature flag，默认 file-only；显式启用后 JSON 主写/删除成功再 shadow 写 PostgreSQL，shadow 失败默认不打断 JSON 主路径，后端全量 `272 passed`。
- 数据库升级 R9 `studio_tasks` backfill/reconcile：新增图片工作室任务 JSON 扫描、PostgreSQL repository upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；摘要不包含 prompt、raw provider payload、key/token/password 或私有 URL，后端全量 `269 passed`。
- 数据库升级 R8 `studio_tasks` 本地基础：新增图片工作室任务 PostgreSQL schema、Alembic migration `20260607_0002`、`StudioTaskRepository` 协议和 file/PostgreSQL/dual repository；运行态仍默认 JSON/file-only，后端全量 `266 passed`。
- 数据库升级 R7 staging precheck 记录：尝试恢复服务器 live rollout，但本机 Clash TUN/fake-ip 路径导致 SSH banner timeout、公网 health 超时；本轮未修改服务器状态，证据归档到 `docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r7-staging-precheck/`。
- 数据库升级 R6 PostgreSQL primary write：新增 `video_studio_tasks` PostgreSQL 主写开关和可选 JSON archive mirror；显式启用后视频任务保存/删除先写 PostgreSQL，默认不再写 JSON，主写失败不落 JSON 分叉状态，Compose/API/worker 环境变量已补齐，目标集 `82 passed`。
- 数据库升级 R6 read switch：新增 `video_studio_tasks` PostgreSQL 优先读开关与 JSON fallback，默认 file-only；显式启用后任务详情/状态、项目任务列表和全量任务列表优先读 PostgreSQL，miss/异常可回退 JSON，后端全量 `255 passed`。
- 数据库升级 R6 runtime dual-write：新增 `video_studio_tasks` 写侧 feature flag，默认 file-only；显式启用后视频任务 JSON 主写/删除成功再 shadow 写 PostgreSQL，后台 `get_user_storage(user_id)` 路径携带 owner user id，shadow 失败默认不打断 JSON 主路径，后端全量 `251 passed`。
- 数据库升级 R5 本地 backfill/reconcile：新增视频工作室任务 JSON 扫描、PostgreSQL repository upsert、脱敏 JSON/Markdown 对账摘要和两个维护脚本；摘要不包含 prompt、raw provider payload、key/token/password 或私有 URL，后端全量 `248 passed`。
- 数据库升级 R4 本地 repository boundary：新增 `backend/app/repositories/`，为视频工作室任务建立 file/postgres/dual repository；JSON 仍为默认主路径，PostgreSQL 映射保留 `raw_task_snapshot`，dual shadow 写失败不打断 JSON 主写路径，后端全量 `245 passed`。
- 数据库升级 R3 本地 schema：新增 Alembic 配置、`video_studio_tasks` SQLAlchemy metadata、首个 PostgreSQL migration 和 schema 回归测试；生成的 DDL 包含 JSONB snapshot、任务状态索引和 partial indexes，业务读写路径仍未切库。
- 数据库升级 R1/R2 本地实现：Compose 新增 `postgres:16-alpine` 基础设施和保守内存参数，API/worker 默认仍 `MIEMIE_DATABASE_ENABLED=false` 且不依赖 PostgreSQL；`/api/health` 新增 `database` 观测，新增懒连接数据库 health helper、PostgreSQL 备份/恢复演练脚本和数据库 health 回归测试。
- 数据库升级 R1/R2 staging 记录：服务器已 fast-forward 到 `cb2d4ff`、写入未跟踪 `compose.env` PostgreSQL 设置并通过 Compose config；`up -d --build postgres api worker worker-video` 执行中 SSH 被远端断开，后续 SSH/TUN 验证暂未闭环，证据记录为 `in_progress`。
- 数据库升级执行路线：新增 `docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md`，把 Compose PostgreSQL 升级拆为 preflight、基础设施、health/备份、Alembic、视频任务 shadow/dual-write/read-switch、服务器 rollout、性能门禁和真实 provider smoke 边界。
- 数据库升级设计：新增 `docs/plans/2026-06-06-postgres-upgrade-optimization-plan.md`，确认 Compose 内 PostgreSQL、JSON 过渡、双写对账、分域读切换和最终数据库主数据源路线；`ADR-0003` 更新为 Accepted。
- 架构治理阶段 7：新增 `docs/adr/ADR-0003-pre-database-architecture-checkpoint.md`，沉淀数据库阶段前检查点、触发条件和准备包。
- 前端页面治理阶段 6B 第十一刀：新增 `frontend/src/pages/VideoStudio/InputAssetSelector.tsx`，拆出首帧、尾帧、音频、首段视频、待编辑视频和源视频选择器；`CapabilityCreateModal.tsx` 继续保留素材状态、源视频准备回调、preview 和提交逻辑，行为保持不变。
- 前端页面治理阶段 6B 第十刀：新增 `frontend/src/pages/VideoStudio/MaskEditorPanel.tsx`，拆出局部编辑 Mask 展示、工具按钮、警告和编辑模式复用提示；`CapabilityCreateModal.tsx` 继续保留源视频准备、Mask 上传、preview 和提交逻辑，行为保持不变。
- 前端 smoke 补强：`frontend/e2e/smoke.spec.ts` 新增视频工作室局部编辑源视频/Mask 面板样本，mock `video_edit_local` 能力、视频库源视频和 `prepare-source-video`，覆盖源视频选择后元数据与 Mask 面板出现；`npm run test:e2e` 扩展到 9 个 smoke。
- 前端页面治理阶段 6B 第九刀：新增 `frontend/src/pages/VideoStudio/ReferenceCollectionsPanel.tsx`，拆出参考图片/视频选择、已选参考素材、参考音色、顺序调整、删除和指代词按钮挂载；`CapabilityCreateModal.tsx` 继续保留状态、preview 和提交逻辑，行为保持不变。
- 前端 smoke 补强：`frontend/e2e/smoke.spec.ts` 新增视频工作室参考素材创建流程样本，mock `wan2.7-r2v` 能力、图库参考图、preview payload 与创建提交，断言 `reference_media` 请求体；`npm run test:e2e` 扩展到 8 个 smoke。
- 前端页面治理阶段 6B 第八刀：新增 `frontend/src/pages/VideoStudio/VideoFieldLabel.tsx`，收敛视频工作室创建/编辑弹窗中素材、Mask 和提示词区域共用的字段标题、必填星号和 hover 帮助入口；行为保持不变。
- 前端页面治理阶段 6B 第七刀：新增 `frontend/src/pages/VideoStudio/DeveloperPreviewPanel.tsx`，从 `CapabilityCreateModal.tsx` 拆出开发者模式提交状态、canonical 请求体、厂商请求体和 validation warning 展示；行为保持不变。
- 前端页面治理阶段 6B 第六刀：删除 `VideoStudioPage.tsx` 中两个 `{false && ...}` 包裹的旧创建/编辑弹窗死代码，以及只服务旧弹窗的旧状态、handler、Mask 处理和模型分支引用；页面降至 152 行，当前创建/编辑继续统一走 `CapabilityCreateModal`。
- 前端 smoke 补强：`frontend/e2e/smoke.spec.ts` 新增视频工作室文生视频创建流程样本，mock 能力接口、preview payload 与创建提交，覆盖新建任务弹窗、提示词填写、提交成功和新任务卡片回显；`npm run test:e2e` 扩展到 7 个 smoke。
- 前端 smoke 补强：`frontend/e2e/smoke.spec.ts` 新增项目列表样本，覆盖登录态项目列表、已有项目卡片、描述、分镜/角色统计和打开/删除入口；`npm run test:e2e` 扩展到 6 个 smoke。
- 前端 smoke 补强：`frontend/e2e/smoke.spec.ts` 新增视频工作室成功任务样本，覆盖任务列表卡片、状态/Provider/进度、详情弹窗、输入素材、关键参数、生成结果、提示词、编辑/重生成、保存到视频库、保存尾帧和开发者模式入口。
- 前端页面治理阶段 6B 第五刀：新增 `frontend/src/pages/VideoStudio/useVideoStudioTaskActions.ts`，拆出保存到视频库、提取尾帧、视频标记、单任务删除、全部删除和重新生成动作；`VideoStudioPage.tsx` 的 API 调用继续收窄到源视频准备、创建和编辑表单路径。
- 前端页面治理阶段 6B 第四刀：新增 `frontend/src/pages/VideoStudio/TaskDetailModal.tsx`，拆出视频工作室任务详情弹窗、输入素材、生成结果、标记按钮、保存动作和开发者模式展示；`VideoStudioPage.tsx` 继续保留数据状态、表单和任务操作回调。
- 前端页面治理阶段 6B 第三刀：新增 `frontend/src/pages/VideoStudio/TaskListPanel.tsx`，拆出视频工作室任务列表卡片、空状态、新建入口、批量删除入口和单任务查看/删除动作；`VideoStudioPage.tsx` 继续保留数据、表单和详情弹窗编排。
- 前端页面治理阶段 6B 第二刀：新增 `frontend/src/pages/VideoStudio/useVideoStudioData.ts`，拆出视频工作室任务列表、素材库数据、模型配置占位状态、初始加载和后台任务轮询启动逻辑；`VideoStudioPage.tsx` 继续保留表单、弹窗和 UI 编排。
- 前端页面治理阶段 6B 第一刀：新增 `frontend/src/pages/VideoStudio/taskViewUtils.ts`，拆出视频工作室任务类型解析、输入素材归一化、参数摘要和预览图选择等纯工具函数；`VideoStudioPage.tsx` 保持页面编排与 UI 行为不变。
- 前端服务层治理阶段 6A：新增 `frontend/src/services/studioApi.ts` 与 `frontend/src/services/videoStudioApi.ts`，拆出图片/视频工作室 API 与类型；`api.ts` 继续 re-export，保持页面 import 兼容。
- W2 本地客户端 Cloudflare 美国代理样本：本地 Mac 经 Clash TUN 美国代理节点访问 Cloudflare，最新有效 `100 VU / 120s` 无失败、无 header check 缺失，但 P95 `960.63ms`；服务器 API 同窗口 `200 11159`，作为代理出口风险记录而非 W2 平台侧硬门禁，证据归档到 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-us-proxy/`。
- W2 本地客户端 Cloudflare 干净直连复测：关闭 Clash TUN/fake-ip 后，DNS 为 Cloudflare 真实 IP 且 route 走 `en0`；`100 VU / 120s` 无失败、无 header check 缺失，但 P95 `734.57ms`，因目标不关注大陆访问效果，本轮作为跨境客户端风险记录而非目标市场硬门禁，证据归档到 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-clean-direct/`。
- W2 本地客户端 Cloudflare DIRECT 规则复测：Clash Verge 已为 `pre-studio.miemie.co` 添加 domain DIRECT 规则，但系统层仍返回 fake-ip `198.18.2.211` 且 route 走 `utun1024`；`100 VU / 120s` P95 `969.79ms`，API 侧同窗口 `200 10523`，证据归档到 `docs/reports/artifacts/2026-06-04-w2-client-cloudflare-direct-rule/`。
- W2 本地客户端 Cloudflare 复测：本地 Mac 经 Clash Verge TUN / fake-ip 代理出口访问 Cloudflare，`100 VU / 120s` 失败率 `0`、check failures `0`，但 P95 `925.75ms`，证据归档到 `docs/reports/artifacts/2026-06-03-w2-client-cloudflare-baseline/`。
- W2 300 VU 入口对照：同一批状态观察读路径下，app direct P95 `244.29ms`、本机 Nginx P95 `271.69ms` 均通过；源站公网 IP forced P95 `325.81ms` 略超，Cloudflare 真实入口 P95 `512.92ms` 且有 1 次连接超时，证据归档到 `docs/reports/artifacts/2026-06-03-w2-300-entry-comparison/`。
- W2 Cloudflare Ray 诊断：关闭临时 Skip 规则后，Cloudflare `100 VU / 120s` 通过且无 timeout；`300 VU / 120s` 无 timeout、无 5xx，但 P95 `351.64ms` 超过 `300ms` 保守门槛，证据归档到 `docs/reports/artifacts/2026-06-03-w2-cloudflare-ray-diagnostics/`。
- W2 Cloudflare Skip 规则复验：按压测来源 IP 与 `/api/*` 临时跳过 rate limiting、managed rules、Super Bot Fight Mode 与 Browser Integrity Check 后，真实入口 `100 VU / 120s` 仍出现 15 个 timeout，并暴露 `StorageService._write_json_with_lock()` 固定 tmp 文件并发写入竞态，证据归档到 `docs/reports/artifacts/2026-06-01-w2-cloudflare-skip-rule/`。
- W2 Cloudflare HTTP/3 关闭复验：关闭 `HTTP/3 (with QUIC)` 后真实入口 `100 VU / 120s` P95 降至 `190.14ms`，timeout 从 9 个降至 5 个但仍未清零，证据归档到 `docs/reports/artifacts/2026-06-01-w2-cloudflare-http3off/`。
- W2 Cloudflare 入口复验：恢复 Cloudflare 代理后真实入口 `100 VU / 120s` P95 `207.86ms`，但出现 9 个 k6 `request timeout` 并触发 27 个响应 check 失败，证据归档到 `docs/reports/artifacts/2026-05-31-w2-cloudflare-entry-retune/`。
- W2 DNS only 状态观察阶梯：Cloudflare DNS only 后公网 `100 VU / 120s` 通过，`300 VU / 120s` 无失败、无 timeout、无 header check 失败，但 P95 `307.78ms` 略超保守门槛，证据归档到 `docs/reports/artifacts/2026-05-31-w2-dns-only-staircase/`。
- W2 公网链路对照：应用直连、Nginx 本机源站、Nginx 源站公网 IP 三组 `100 VU / 120s` 状态观察均通过，Cloudflare 公网域名复测因 P95 `409.26ms` 与 5 个 k6 `request timeout` 失败，证据归档到 `docs/reports/artifacts/2026-05-30-w2-link-comparison/`。
- W2 状态观察阶梯：在 `miemie-pre` 上补跑平台侧状态观察读路径，本机 `100 VU / 120s` 通过，公网 `100 VU / 120s` 因 4 个 k6 `request timeout` 触发严格门禁停止；API 侧观察类 GET 汇总为 `200 43785`，证据归档到 `docs/reports/artifacts/2026-05-30-w2-status-observation/`。
- W2 阶梯压测 v1：在 `miemie-pre` 上完成本机/公网 `50/100/200 VU` 只读阶梯与 `10/20/30 VU` preview 受控提交阶梯；性能 P95 均达标，但发现 `1` 次 per-user config 首次并发初始化写入竞态导致的 `500`，严格门禁不完全通过，证据归档到 `docs/reports/artifacts/2026-05-29-w2-staircase-baseline/`。
- S4 公网反代后性能基线：在 `miemie-pre` 上完成本机/公网只读查询与 preview 受控提交四组 k6 保守门禁，失败率均为 `0`，P95 均低于 `800ms`，证据归档到 `docs/reports/artifacts/2026-05-29-s4-public-baseline/`。
- 下一阶段体验与性能治理：新增 `docs/reports/2026-05-24-next-phase-experience-and-performance.md`，记录 `miemie-pre` 无 key 体验 smoke、当前运行门禁和后续浏览器验证缺口。
- 运行态轻量观测：新增高频图片/视频工作室与测评查询路径的脱敏耗时日志，不改变公开 API，不记录 key/token/password。
- 压测资产：新增 `loadtest/k6/s4-mixed-query-generate.js`，用于“多人查询 + 少量提交”的 Compose + Redis + Worker 路径基线采集。
- 前端服务层治理：新增 `frontend/src/services/apiClient.ts`，先拆出 axios transport、认证 token 注入与 401 处理，`api.ts` 继续保持原业务 API 聚合入口。
- 视频工作室 Worker 迁移 v1：视频工作室创建/重新生成任务改为通过统一 dispatcher 入队，Compose 新增独立 `worker-video` 服务消费 `video_studio` 队列，避免长视频任务阻塞图片 worker。
- 视频工作室 Worker 迁移 v1：`VideoStudioTask` 新增 `submit_state`、`submit_started_at`、`submit_attempt_id`，并在 `provider_result_meta.worker_attempt` 中记录 dispatcher、Celery task id、heartbeat 和 stale 窗口。
- 视频工作室 Worker 迁移 v1：新增 submit stale 兜底、worker stale 恢复、旧 attempt 丢弃、delete/regenerate 防旧 worker 复活等后端回归；pre 服务器已完成基础部署、无 key 失败路径、`worker-video` restart 基础恢复和 1 个真实 DashScope 视频 smoke 验证。
- 视频工作室：支持在已选参考图/参考视频上点击 `@`，按模型 capability 中的 `reference_token_policy` 自动把 `[Image 1]`、`图1`、`视频1`、`<<<image_1>>>` 等指代词插入提示词光标位置。
- 设置：DashScope API 地域新增美国（弗吉尼亚）`https://dashscope-us.aliyuncs.com/api/v1`。
- 阿里生图/生视频同步/异步限流校准：
  - 新增统一模型限流定义，区分 `submit_rate_limit` 与 `max_concurrent`
  - Qwen 图片同步接口保留 `2/min` 或 `2/sec` 提交频率，处理中任务数量不再误套异步并发上限
  - Wan / HappyHorse / Kling / Vidu 异步任务从提交到终态占用 in-flight lease，Kling / Vidu 支持共享并发池
  - 图片工作室、图片测评、视频工作室、视频测评统一接入提交频率与并发 helper
  - 能力 schema 暴露 `api_mode`、`submit_rate_limit`、`max_concurrent`、`concurrency_scope` 和共享池信息
- 测评运行结果即时展示：
  - 图片测评与视频测评启动后立即返回完整 `pending` 矩阵
  - 后台执行中增量保存 `running` / 终态 cell，前端轮询即可看到已完成结果
  - 视频测评 `group_count` 多输出会在单条视频完成 OSS 持久化后立即展示，后续失败也保留已完成视频
  - 运行统计新增待运行、生成中、完成计数
- 视频测评首帧生视频模块：
  - 侧边栏新增 `视频数据集` 与 `视频测评`
  - 新增 `/api/video-benchmark/*`，独立保存 video benchmark datasets / suites / runs
  - v1 自动筛选所有支持 `image_to_video` 的视频工作室模型，复用 video adapter 构造 payload、提交和轮询
  - 数据集样例支持首帧图、可选驱动音频和可选样例级 `duration`
  - 视频数据集页补齐图片数据集同级批量能力，支持行多选、批量导入首帧或 prompt、批量填充首帧、批量编辑字段、选中排序和删除
  - 视频数据集允许暂存缺首帧样例，保存/导入返回 warnings，运行测评和 payload preview 前阻断缺首帧
  - 视频测评模型参数新增 `生成数量`，上限跟随模型 `max_concurrent`，并在矩阵和详情中展示多条输出
  - 视频测评页移除 `Baseline Params JSON`，参数只通过每个参与测评模型的独立设置填写
  - 运行矩阵展示输出视频，详情保留 effective params、canonical request、provider payload、provider result meta、task/request id
  - Markdown / HTML 报告导出保留视频 URL，不内嵌视频字节
- 图片测评导出支持内嵌图片资源：
  - `导出 Markdown` 与 `导出 HTML` 统一改为后端生成
  - 导出时会把输入图 / 输出图下载并转成 `data:` 内嵌到单文件中
  - 导出页新增“快速导出”，可跳过内嵌、直接保留原 URL
  - 新增 `export-md-file / export-html-file` 附件接口，前端直接下载文件而非传超大 JSON
  - 响应新增 `embedded_image_count` 与 `fallback_url_count`
- 平台最小观测闭环：
  - 所有 HTTP API 响应统一暴露 `X-Request-ID`
  - 所有 HTTP API 响应统一暴露 `X-Deployment-Version`
  - 未授权响应也保留统一请求标识，便于压测与排障
- 视频工作室后台状态协调器：
  - `/api/video-studio/{task_id}/status` 改为纯读平台任务状态
  - 厂商状态轮询、结果落盘、缩略图生成统一收口到后台协调器
  - 应用启动时会恢复遗留 `processing` 视频任务的状态协调器
- 前端统一任务轮询 hook：
  - 图片工作室、音频工作室、视频工作室、图片测评改为复用统一轮询基础设施
  - 统一初始延迟、轮询间隔、错误退避和组件卸载清理逻辑
- Step 00 / Step 01 高性能实验资产：
  - 新增 k6 S1/S3 压测脚本、Linux staging 基线记录与验证包归档
  - 新增 `.dockerignore`、`Dockerfile`、`docker-compose.yml`、`compose.env.example`
  - 新增运行模式矩阵文档，明确开发 / 脚本生产 / Compose 生产边界
- Step 02 / Step 03 扩容最小实装：
  - Compose 新增 Redis 服务，用于 session、限流存储和后续短缓存基础设施
  - session 支持 Redis 优先、文件兜底，改密码后清理旧 session
  - slowapi 限流支持 Redis storage URI，未配置时保留内存行为
  - `/api/health` 暴露 Redis 配置与连通状态
  - Compose 新增 Celery worker，图片工作室生成可通过统一 dispatcher 入队，默认本地开发仍回退 asyncio
  - 2026-05-23 已在 `miemie-pre` 服务器验证 Redis session、限流 Redis key、Celery worker 注册和图片工作室队列 smoke
  - 2026-05-24 稳定性补强验证 Redis restart / unavailable 路径可受控恢复，且文件 session 兜底未出现未捕获 500；worker 执行中断后图片工作室任务永久 `generating` 风险已通过 stale 兜底修复，并补跑真实 DashScope 图片队列 smoke
- `pre` 实验分支说明：
  - 新增 `README.pre.md` 与分支计划，明确 `main`/`pre` 并行开发、Compose 本机构建交付和反向代理用户自管边界
  - Compose 默认绑定 `127.0.0.1:${MIEMIE_HOST_PORT}`，降低应用端口直接暴露公网的风险
- `pre` Ubuntu staging 验证归档：
  - 新增服务器优先验证计划、实际验证报告和脱敏 artifact 摘要
  - 记录独立 Compose project、回环端口、health/frontend 证据，以及 SSH 访问中断曾导致 S1/S3 和供应商 smoke 未闭环的阻塞项
  - 2026-05-23 补跑 S1/S3 k6、资源快照与 1 个低频真实 DashScope smoke，S1/S3 均 0% HTTP 失败，smoke 成功落 1 个视频结果
- 管理脚本运行时可观测性：
  - `GET /api/health` 新增 `git_commit`、`run_mode`、`serve_frontend`、`started_at`
  - `./run.sh status` / TUI 状态栏新增默认模式、实际模式、当前运行提交与前端服务方式
- 图片测评数据集导入增强：
  - `POST /api/image-benchmark/datasets/import` 新增 `migrate_images_to_oss` 参数
  - 跨环境导入时可将输入图下载并重新上传到当前用户 OSS
  - 响应返回 `migration_report`，包含转存成功、失败、跳过数量和失败明细
- 图片测评支持 wan2.7 交互式编辑：
  - 新增 `interactive_edit` 测评任务类型
  - 数据集样例新增 `bbox_list`，导入/导出/保存均保留框选数据
  - 数据集编辑弹窗复用图片工作室画框组件，可对每个输入图绘制最多 2 个框
  - 测评运行时会将 bbox 归一化后传入 wan2.7 provider payload
- 图片测评单元详情增强：
  - 单元详情弹窗展示完整 `task_ids` 与 `request_ids`
  - 自动重试时会累计每次尝试产生的所有 task/request id
  - `provider_result_meta.auto_retry` 同步记录累计后的追踪 ID
- 视频工作室参数帮助升级：
  - 所有视频工作室前端可见关键参数支持结构化帮助信息
  - 问号悬浮说明从短 Tooltip 升级为 Popover
  - 帮助内容统一包含“概览 / 含义 / 限制 / 怎么选 / 示例 / 补充说明”
- 视频工作室帮助体系：
  - `video_capabilities.py` 新增参数级 `help`
  - `ui_hints.asset_help` 和 `ui_hints.prompt_help` 升级为结构化帮助
  - Kling / Vidu / Wan 的关键参数和素材位说明统一由后端 schema 下发
- 视频工作室：临时接入 `wan2.7-i2v-2026-04-25` 快照模型
  - 与长期主用 `wan2.7-i2v` 并存，不作为别名、不替换默认模型
  - 支持图生视频、首尾帧生视频和视频续写，复用 wan2.7 i2v 新版 `video-synthesis` 请求结构
  - 开发者模式和真实提交 payload 保留用户选择的独立模型 ID，便于对比快照效果
- 视频工作室：接入 `wanx2.1-vace-plus`
  - 新增 `video_repainting` 视频重绘任务类型
  - 新增 `video_edit` 局部编辑任务类型
  - 后端新增 `VaceVideoEditService`，统一处理任务提交、轮询和结果视频 OSS 回传
  - 视频工作室新增 `POST /video-studio/prepare-source-video` 和 `POST /video-studio/upload-mask` 接口
  - 局部编辑 Mask 编辑器支持画笔、橡皮擦，以及“逐点连线 + Enter 闭环”的多边形模式
- 视频尾帧提取功能：
  - 视频工作室：每个生成视频下方新增"保存尾帧"按钮，使用 ffmpeg 提取最后一帧保存到图库
  - 分镜首帧：当上一个镜头已有视频时，显示"上一视频尾帧"按钮，一键提取并设为当前镜头首帧
  - 后端新增 `POST /video-studio/{id}/extract-last-frame` 和 `POST /frames/set-from-video-last-frame` 两个 API
  - 使用 ffmpeg/ffprobe 提取视频尾帧，上传 OSS 后保存到图库
- 结果标记功能：图片工作室、视频工作室、音频工作室均支持对生成结果添加星标/红旗/对号/红叉标记
  - 图片工作室：每张生成图片下方显示标记按钮，标记保存在 `StudioTaskImage.markers` 字段
  - 视频工作室：每个生成视频下方显示标记按钮，标记保存在 `VideoStudioTask.video_markers` 字典
  - 音频工作室：每条任务历史标题行显示标记按钮，标记保存在 `AudioStudioTask.markers` 字段
  - 后端新增 `POST /studio/{id}/markers`、`POST /video-studio/{id}/markers`、`POST /audio-studio/{id}/markers` 三个 API
- React ErrorBoundary 组件：JS 运行时错误不再导致白屏，显示友好提示和刷新按钮
- pytest 自动化测试：28 个测试用例覆盖认证、bcrypt、CORS、中间件、级联删除、原子写入、单例安全、限流，以及 VACE 视频工作室流程
- `./run.sh test` 命令：一键运行后端测试，交互菜单也新增测试入口
- 自定义端口：支持通过 `./run.sh port backend 9000` / `./run.sh port frontend 3001` 自定义服务端口，持久化到 `.miemie.conf`，也支持环境变量 `MIEMIE_BACKEND_PORT` / `MIEMIE_FRONTEND_PORT` 覆盖

- 视频工作室：接入 HappyHorse 1.0 文生/图生视频
  - 新增 `happyhorse-1.0-t2v`（文生视频）与 `happyhorse-1.0-i2v`（图生视频）两个可选模型
  - 采用独立 `provider=happyhorse`，设置页可单独选择 HappyHorse 使用测试 Key 或生产 Key
  - capability schema 新增 HappyHorse 结构化帮助、参数约束与开发者模式 payload 支持
- 视频工作室：按新版官方文档扩展 HappyHorse 系列
  - 新增 `happyhorse-1.0-r2v`（参考生视频）与 `happyhorse-1.0-video-edit`（视频编辑）两个可选模型
  - `happyhorse-1.0-r2v` 映射到现有 `reference_to_video`，仅支持 1-9 张参考图
  - `happyhorse-1.0-video-edit` 映射到现有 `video_edit_global`，支持 1 个输入视频与 0-5 张参考图
  - 4 个 HappyHorse 模型继续通过 `provider=happyhorse` 复用 DashScope 异步提交、轮询、OSS 与开发者模式链路
- 图片工作室：接入火山引擎 Seedream 图片模型
  - 新增 `doubao-seedream-5.0-lite` 与 `doubao-seedream-4.5`，`provider=volcengine`
  - 支持文生图、1-14 张参考图编辑、0-14 张参考图组图生成
  - 5.0 lite 支持 `output_format=jpeg/png` 与 `web_search`
  - 开发者模式展示 Seedream canonical request、厂商 payload、request id、usage、tools、单图错误和 raw response
- 设置页：新增独立“火山引擎 Ark API Key”模块
  - `volcengine_api_key` 独立保存，不复用 DashScope 测试/生产 Key 池
  - 设置接口返回 `volcengine_api_key_masked` 与 `is_volcengine_api_key_set`
- 图片工作室/图片测评：接入 Google Gemini Nano Banana 图片模型
  - 新增 `nano-banana-2` 与 `nano-banana-pro`，`provider=google`
  - 支持文生图和 1-14 张参考图图像编辑，v1 不开放组图生成
  - 参数按 Google 文档开放 `aspect_ratio`、`image_size`、`google_search_mode`，Nano Banana 2 额外开放 `thinking_level`
  - 后端新增 inline 图片字节持久化路径，优先上传 OSS，失败或未启用时回退 `/assets/oss_staging/...`
  - 开发者模式和图片测评详情保留 canonical request、provider payload、request id、usage、grounding metadata、规范化 `grounding_source_links` 与 raw response
  - 新增 Google image search grounding 样本夹具测试，覆盖 web/image/retrieved context 来源链接归一化
- 设置页：新增独立“Google Gemini API Key”模块
  - `google_api_key` 独立保存，不复用 DashScope 测试/生产 Key 池
  - 设置接口返回 `google_api_key_masked` 与 `is_google_api_key_set`

### 变更 (Changed)
- 扩容路线图当前正式目标固定为 **W2**。
- 部署边界明确为“项目只提供应用端口，反向代理由用户自管”。
- Step 03 当前规划调整为优先 `Celery + Redis`，RabbitMQ 暂不在首阶段实装。
- 后端应用启动恢复逻辑从 FastAPI `on_event("startup")` 迁移到 `lifespan`。
- `./run.sh test` 现在会先确认项目后端依赖，再固定使用项目根目录 `venv/bin/python` 执行测试。
- 部署文档从“Compose 规划中”更新为“脚本兼容 + Compose 推荐”的双路径口径。
- 设置页保存交互改为模块化：
  - 移除页面底部“保存所有设置”
  - Key、火山 Key、API 地域、文本模型、OSS 各模块各自保存
  - 通知、文本模型开关和 OSS 启用开关变更后自动保存
- 设置页：Key 路由新增 HappyHorse 独立选择项，并确认 Wan / HappyHorse / Kling / Vidu 均按各自 profile 实际取用测试或生产 Key。
- 视频工作室：更新 HappyHorse 文生/图生视频参数口径，图片格式与媒体限制以新版官方文档和平台 spec 为准。
- 视频工作室：HappyHorse 文生/图生 capability 明确暴露语义化 smoke/full `verification_profiles`，不再只依赖通用默认档位。
- 图片测评导出体验升级：
  - 导出按钮增加 loading 态，避免大报告导出时误判为无响应
  - 图片内嵌下载改为并发执行，并对超时/网络抖动/5xx/429 做多次重试
  - 对 403/404/410 等明显失效 URL 快速回退，减少整体卡顿
- 管理脚本：TUI 中“更新到最新版本”改为默认执行“拉取代码并自动应用到当前运行服务”
- 管理脚本：更新流程会记录更新前实际运行模式，并在重启后校验运行中的 `git_commit / run_mode / serve_frontend`
- 管理脚本：依赖刷新从比较 `HEAD~1` 改为比较“更新前 commit → 更新后 commit”，避免多提交更新时漏装依赖
- 管理脚本：默认运行模式持久化到 `.miemie.conf`，服务器场景长期偏向 `prod`
- 图片测评手动重试范围从仅 `failed` 扩展为 `failed + unsupported`，用于重试因输入图预检暂时失败而标记为 `unsupported` 的单元
- 视频工作室：参数迁移提示只在用户主动切换模型时提示一次，创建/编辑弹窗初始化和切任务类型时不再重复弹出“已保留兼容参数”通知
- 视频工作室：设置页支持两把 DashScope Key（测试/生产），并为 `Wan / Kling / Vidu` 分别指定当前走哪把 Key
- 音频工作室：将"我的音色"和"任务历史"从页面底部独立卡片移至顶部标签页
  - 新增标签页：我的音色（显示数量）、任务历史（显示数量）
  - 与文本转语音、声音复刻、声音设计平级展示，切换更便捷
- 视频工作室：局部编辑任务改为“首帧提取 -> 前端绘制 Mask -> 服务端二值化上传 -> 提交 VACE”的完整流程
- 视频工作室：任务卡片和详情弹窗支持展示源视频首帧、参考图和 Mask 缩略图
- 管理脚本：`./run.sh install`、`./run.sh start --prod` 和维护菜单新增服务器资源检测与推荐逻辑
  - 自动检测内核、CPU、内存和当前 Swap
  - 自动推荐 `MIEMIE_WORKERS` 和 `NODE_BUILD_MEMORY_MB`
  - 用户确认后持久化到 `.miemie.conf`，并在应用后校验是否生效
- 管理脚本：生产模式启动顺序调整为“先构建前端，再启动后端”，降低小内存服务器的资源峰值
- 管理脚本：`./run.sh status` 新增当前 Workers 与 Node 构建内存显示

### 修复 (Fixed)
- 图片工作室：复核 Seedream 5.0 lite / 4.5 文档口径，清晰度档位 schema label 改为纯 `2K/3K/4K`，Seedream 参数面板新增“组图功能”开关；明确 `guidance_scale` 仅 Seedream 3.0 t2i 支持，5.0 lite / 4.5 不展示也不下发。
- 图片工作室：整理 Seedream 尺寸选项来源并参考 Wan2.7 改为互斥尺寸方案，`size` 参数只暴露 2K/3K/4K 清晰度档位，固定像素尺寸通过 `common_sizes` 展示；前端先选择“清晰度档位 / 固定尺寸”二选一，清晰度模式不再展示比例，差异说明收进 popover。
- 设置页：修复空白 Key 更新会覆盖已有火山引擎 Ark API Key，导致 Seedream 生成提示未配置的问题；Key 字段现在会 trim，空白表示不修改。
- 视频工作室：修复 capability 中 `max_reference_videos=0` 被前端默认值覆盖的问题，HappyHorse 参考生视频不再显示参考视频选择控件。
- 视频工作室：厂商在提交阶段直接失败且未返回 `task_id` 时，现在会把 `request_id`、错误码、错误信息和原始响应保存到 `provider_result_meta.submit_error`，开发者模式可直接查看。
- 图片工作室生产环境卡顿治理：
  - 开发者模式未展开时不再自动请求 `/api/studio/preview-payload`
  - payload 预览请求增加取消/去重，减少无效并发
  - `POST /api/studio/{task_id}/generate` 改为先返回 `generating`，再在后台执行 wan2.7 远程参考图探测与最终 payload 构建
  - 任务弹窗“开始生成/重新生成”按钮增加“提交中”即时反馈
  - 同一任务重复点击生成时，前端同步防重入，后端也会对重复 `generate` 请求执行 no-op 去重
- 图片工作室生成结果统一改为“先落本地暂存，再上传 OSS”：
  - 对 DashScope 临时图片链接补齐统一持久化入口，避免临时 URL 直接写入最终任务结果
  - OSS 上传增加多次自动重试；成功后立即删除本地暂存文件
  - 重试耗尽时，对可恢复故障临时回退 `/assets/...` 本地图片，并在前端返回 warning / 本地回退标记
  - 对 `HTTP 403/404`、Bucket/鉴权异常等不可恢复错误不保留本地回退，避免本地存储被滥用
- 图片工作室本地回退图增加补偿重传与清理：
  - 打开任务详情或列表时会懒触发到期图片后台重传 OSS
  - 新增任务级与项目级“一键重传回退图到 OSS”
  - 本地回退文件 7 天后自动标记过期并清理
  - 本地回退图禁止直接保存到图库，避免长期引用服务器本地文件
- `wan2.7` 图片工作室与图片测评在 OSS 转存失败时补充结构化日志，便于区分“代码未生效 / OSS 配置异常 / 服务器下载超时”
- 图片测评 `interactive_edit` 执行链路补齐 wan2.7 的 `bbox_list` 归一化快照，避免预览正确但真实提交时退化成空数组导致整批 `InvalidParameter`
- wan2.7 任务轮询失败时改为优先读取 `output.code / output.message`，测评与工作室可直接展示厂商返回的具体错误原因
- wan2.7 图片输入预检：
  - 支持 `data:image/...;base64,...`
  - 图片下载失败会返回 HTTP 状态、content-type、超时或协议错误
  - 图片解码失败会返回内容类型和字节数
  - 每张输入图预检增加短间隔重试，避免一次网络抖动直接把测评单元标记为 `unsupported`
- 可灵视频编辑：对输入视频时长、帧率和分辨率做前置校验，避免用户提交后才收到厂商侧 `InvalidParameter`
- 视频工作室：创建/编辑能力弹窗仅在打开时挂载，避免隐藏弹窗参与初始化导致重复通知
- 项目删除时补全所有 13 种关联数据（gallery、studio、audio、video_library、text_library、video_studio、audio_studio、voices 等）的级联删除
- Storage 缓存字典（`_storage_cache`）添加 `threading.Lock` 保护，防止多线程重复创建实例
- 所有 JSON 读操作统一使用 `_read_json_with_lock` + `fcntl.LOCK_SH` 共享锁，确保读写一致性
- 前端 Videos/VideoStudio 页面组件卸载时清空 `pollingRef`，防止离开页面后继续发送网络请求
- Studio/Frames/VideoStudio 页面中残余的硬编码十六进制颜色替换为 Ant Design `theme.useToken()` token
- Settings/LLMConfigForm 中 `form.getFieldValue()` 替换为 `Form.useWatch`，确保表单联动即时更新
- `generationStore` 中 `Set` 类型字段明确排除在 Zustand persist 序列化之外
- 5 处静默 `except Exception: pass` 改为 `logger.warning()`，保留降级逻辑但记录日志
- `oss.py` 和 `studio.py` 中约 25 处 `print()` 替换为标准 `logging`
- `UserService` 单例 `get_user_service()` 添加 `threading.Lock` double-checked locking
- `user_service.py` 中 `_save_users()` 和 `_save_sessions()` 改为原子写入
- slowapi 限流装饰器参数名冲突：Pydantic 模型参数从 `request` 重命名为 `data`，避免与 `starlette.requests.Request` 冲突导致 500 错误
- 管理脚本：生产模式默认 worker 数改为更保守的自动推荐，避免 `gunicorn + vite build` 同时启动时把小内存服务器打满
- 管理脚本：Linux 小内存服务器支持在用户确认后自动创建并校验 Swap，减少构建或重启时假死

### 之前的新增 (Added)
- 视频工作室：新增 wan2.6-r2v-flash 参考生视频模型
  - 极速参考生视频，支持有声/无声切换（audio toggle）
  - 支持多镜头叙事（shot_type: single/multi）
  - 720P/1080P 分辨率，2-10秒连续时长
  - 支持参考视频（最多3个）和参考图片（最多5张）
- 视频工作室：新增 wan2.6-t2v 文生视频模型
  - 支持多镜头叙事、自动配音/自定义音频
  - 720P/1080P 分辨率，2-15秒连续时长
  - 支持负面提示词、智能改写、水印、随机种子

### 变更 (Changed)
- 视频工作室：wan2.6-t2v 时长从固定选项 [5,10,15] 改为连续范围 [2,15]（对齐 API 文档）
- 视频工作室：wan2.6-i2v 时长从固定选项 [5,10,15] 改为连续范围 [2,15]（对齐 API 文档）
- 视频工作室：wan2.6-r2v audio 改为由参考视频自动决定，不再支持手动 toggle
- 视频工作室：参考生视频默认模型从 wan2.6-r2v 改为 wan2.6-r2v-flash
- 前端文生视频 tab 时长控件支持 duration_range 连续输入（InputNumber）
- 前端参考生视频 tab 支持动态切换模型，根据模型能力显隐 audio toggle

- 视频工作室：接入万相2.2数字人模型（wan2.2-s2v）
  - 基于单张图片和音频生成口型同步的说话/唱歌/表演视频
  - 支持真人（肖像、半身、全身）及卡通人物
  - 支持 480P/720P 分辨率，默认 720P
  - 音频从音频库选取，图片从图库选取
  - 新建 `digital_human.py` 服务及 `wan22_s2v.py` 模型注册
  - VideoStudioPage 按模型能力动态显隐控件
- 图片工作室：接入千问图像 2.0 系列模型（qwen-image-2.0-pro / qwen-image-2.0）
  - 双模式：无参考图为文生图，有参考图（1-3张）为图像编辑
  - 单次请求支持输出 1-6 张图片（n 参数）
  - 自由尺寸设定，总像素 512×512 至 2048×2048
  - 支持负面提示词、智能改写、水印、随机种子
  - 新建 `qwen_image_2.py` 模型服务及注册
  - StudioPage 新增专属参数面板及验证逻辑
- 音频工作室：CosyVoice (cosyvoice-v3-flash) 文本转语音功能
  - 60+ 系统音色（社交、儿童、方言、海外、客服、助手等分类）
  - 支持音量/语速/音高/种子/格式/语言提示/SSML/Instruct 等参数
  - 生成音频自动上传 OSS，可保存至音频库
- 音频工作室：声音复刻功能
  - 从音频库选择 10~20 秒音频样本创建自定义音色
  - 后台自动轮询审核状态，审核通过后可用于 TTS
- 音频工作室：声音设计功能
  - 通过文本描述生成自定义音色，返回预览音频
  - 支持采样率和格式设置
- 音色管理：我的音色列表，支持试听和删除
- 后端新增 `AudioStudioTask` 和 `VoiceProfile` 数据模型
- 后端新增 `CosyVoiceTTSService`、`CosyVoiceCloneService`、`CosyVoiceDesignService`
- 后端新增 `/api/audio-studio` 路由（TTS/复刻/设计/音色管理）
- Storage 新增 `audio_studio` 和 `voices` 目录与 CRUD 方法
- 前端 `audioStudioApi` 接口和 TypeScript 类型定义
- 前端 AudioStudioPage 三 Tab 页面完整实现

- 后台异步生成：图片工作室 `/generate` 端点通过 `asyncio.create_task()` 后台执行，立即返回
- 前端轮询模式：StudioPage 参照 VideoStudioPage 实现 polling，支持多任务并发生成
- 生产部署支持：`./run.sh start --prod` 启动 gunicorn 多 worker + 前端构建
- API 限流：slowapi 全局限流（200 请求/分钟/IP）
- 自动更新机制：`./run.sh auto-update enable` 每日自动拉取更新，含数据备份
- 版本回滚：`./run.sh rollback` 支持回滚到上一个版本
- 双主题系统：日间模式（蓝白色系）和夜间模式（灰金色系）
- 侧边栏主题切换按钮（用户名右侧，太阳/月亮图标）
- `themeStore.ts`：主题状态管理（Zustand + localStorage 持久化）
- `theme/index.ts`：集中管理双主题 ThemeConfig 定义
- `docs/UI_GUIDELINES.md`：UI 设计规范文档
- 登录页双主题适配（不同渐变背景、毛玻璃效果）

### 变更 (Changed)
- 图片工作室从同步阻塞改为后台异步 + 前端轮询，UI 不再阻塞
- HTTP 客户端统一为 httpx，移除 requests 和 aiohttp 依赖
- DashScope SDK 同步调用包装为 `asyncio.to_thread()`，避免阻塞事件循环
- 会话验证改为每次从文件读取，支持多 worker 部署
- 全站 22 个页面 + 5 个通用组件使用 `theme.useToken()` 替代硬编码颜色
- 统一 CSS 变量系统：移除 `--studio-*` 和 `--color-*` 两套旧变量，改由 Ant Design token 驱动
- 清理 Tailwind 配置：移除硬编码 studio 颜色
- 更新 `main.tsx`：ConfigProvider 根据主题状态动态切换算法
- 创建开发文档目录 (`docs/`)

### 修复 (Fixed)
- 图片生成任务不再阻塞 UI，可同时创建多个任务
- StorageService 所有保存方法统一使用文件锁，确保并发安全
- 批量生成重置时同时清空 `generatingItems` 状态

---

## [1.0.0] - 2025-12-30

### 新增 (Added)

#### 核心功能
- 多用户支持：用户注册、登录、数据隔离
- 项目管理：创建、编辑、删除项目
- 分镜脚本：AI 生成/优化、手动编辑、多版本对比
- 角色/场景/道具管理：从脚本提取、图片生成、多版本选择
- 分镜首帧生成：基于分镜自动生成首帧图
- 视频生成：首帧转视频、批量生成

#### 工作室
- 图片工作室：灵活的图片生成任务管理
- 视频工作室：文生视频、图生视频、参考生视频、首尾帧生视频任务管理

#### 媒体库
- 图库：图片上传、URL 导入、分类管理
- 音频库：音频上传管理
- 视频库：视频上传管理
- 文本库：文本片段管理

#### 模型支持
- 文生图：wan2.6-t2i, wan2.5-t2i-preview, wan2.6-image
- 图生图：wan2.5-i2i-preview, qwen-image-edit-plus
- 图生视频：wan2.5-i2v-preview, wan2.6-i2v-preview, wanx2.1-i2v-preview
- 视频生视频：wan2.6-r2v
- LLM：qwen3-max, qwen-plus-latest

#### 集成
- 阿里云 OSS 图片/视频持久化存储
- DashScope API 集成（文生图、图生视频、LLM）

### 变更 (Changed)
- 平台名称从 "AI 视频工作室" 改为 "MieMie-Studio"
- 模型显示名称标准化为 "x生x <model code>" 格式

### 修复 (Fixed)
- OSS 测试连接误报权限错误
- 批量生成首帧按钮不响应
- wan2.6-r2v 前端只能选择 2 个参考视频（已改为 3 个）
- 图片工作室文生图任务无法设置输出尺寸

---

## 版本规范

### 版本号格式

`MAJOR.MINOR.PATCH`

- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的新功能
- PATCH: 向后兼容的 Bug 修复

### 变更类型

- **Added**: 新功能
- **Changed**: 现有功能变更
- **Deprecated**: 即将移除的功能
- **Removed**: 已移除的功能
- **Fixed**: Bug 修复
- **Security**: 安全相关修复

### 示例条目

```markdown
## [1.1.0] - 2025-01-15

### Added
- 新增 xxx 功能 (#issue-number)
- 支持 xxx 模型

### Changed
- 优化 xxx 性能
- 调整 xxx 默认值

### Fixed
- 修复 xxx 问题 (#issue-number)
```

---

*请在每次发布时更新此文档。*
# 2026-04-01

## 视频工作室稳定化
- 对齐 `Wan / Kling / Vidu` 本地视频文档中的参数、条件逻辑、互斥规则与尺寸/分辨率关系
- 统一视频工作室默认值：`watermark=false`，支持布尔 `audio` 的模型默认 `audio=true`
- 移除视频工作室中的推荐标签与推荐状态展示
- 新增 `POST /api/video-studio/preview-payload`，支持预览 canonical 请求与厂商请求体
- 新建任务弹窗和任务详情新增默认折叠的“开发者模式”
- 任务成功后自动抽取输出视频首帧缩略图并保存到 `thumbnail_url`
- 新增视频任务完成浏览器通知和设置项 `video_task_notifications_enabled`
- 参数帮助统一使用 Popover，补充了含义、限制、选择建议、示例和依赖关系说明
# 2026-04-01

## 数据库升级执行治理

- 新增 R81 post JSON exit validation：`scripts/postgres_post_json_exit_validation.sh` 会在 final JSON exit audit 通过后滚动最终运行态、检查本机/公网 health、执行 9 个 tracked 核心域 reconcile、采集 Compose/Docker 状态并跑 k6 S1 读负载门禁；当前 artifact 为 dry-run plan。
- 新增 R80 final JSON exit audit：`scripts/postgres_final_json_exit_audit.py` 会只读检查服务器 sequence 证据与最终 PostgreSQL-only 运行态策略，要求全局主读/主写、关闭 JSON fallback/archive，并把当前状态归档为 `needs_server_sequence_evidence`。
- 记录 R80 network-scope preflight 复测：命令行路径仍返回 `198.18.0.94` fake-IP 并走 `utun1024`，服务器数据库 sequence 尚未执行。
- 记录 R79 network-scope preflight 复测：Clash direct 规则调整后命令行路径仍返回 `198.18.*` fake-IP 并走 `utun1024`，服务器数据库 sequence 尚未执行。

---

# 2026-04-01

## 图片工作室

- 接入 `wan2.7-image-pro` 与 `wan2.7-image`
- 图片工作室新增能力化任务类型：文生图、图像编辑、交互式编辑、组图生成
- 新增 `wan2.7` 的尺寸模式、交互式框选、颜色主题、组图模式与开发者模式
- 图片工作室开发者模式支持查看 canonical 请求体、厂商 payload、task_ids、request_ids、provider_result_meta
- 图片工作室新增任务完成浏览器通知，页面失焦时继续轮询
- 修复 `/studio/models/available` 被旧配置覆盖导致 registry 参数帮助丢失的问题
- 接入 `wan2.7-i2v` 与 `wan2.7-videoedit` 到视频工作室
- 新增视频任务类型 `video_extension`（视频续写），支持 `first_clip + optional last_frame`
- `wan2.7-videoedit` 接入现有“视频编辑”，支持 `ratio`、`audio_setting`、0-3 张参考图
- 视频工作室能力 schema、开发者模式、任务详情与回归测试已同步支持 `wan2.7` 视频模型
