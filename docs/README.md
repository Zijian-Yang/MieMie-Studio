# MieMie-Studio 文档入口

这份文件是**人类开发者与 AI 代理的共同入口**。如果你只读一份文档，请先读这里。

## 先看什么

### 规则优先级
1. 仓库根 `AGENTS.md`
2. 本文件
3. 当前要改的 spec：`docs/specs/`
4. 相关 ADR：`docs/adr/`
5. 相关 checklist / playbook：`docs/checklists/`、`docs/playbooks/`
6. 背景性资料：`docs/BACKEND.md`、`docs/FRONTEND.md`、`docs/DASHSCOPE.md`

### 推荐阅读顺序

- **第一次接手仓库**：`AGENTS.md` → `docs/README.md` → `docs/ARCHITECTURE.md` → `docs/reviews/2026-04-platform-audit.md`
- **做功能或修 bug**：对应 spec / ADR → 代码 → checklist
- **接入新模型**：`docs/STUDIO_MODEL_INTEGRATION_GUIDE.md` → `docs/checklists/MODEL_INTEGRATION.md` → 相关 playbook
- **做扩容/性能改造**：`docs/specs/2026-04-step-00-capacity-baseline-and-slo.md` → `docs/playbooks/CAPACITY_BASELINE_AND_LOADTEST.md` → 对应步骤 spec
- **验证 `pre` 实验分支服务器部署**：`docs/plans/2026-05-18-pre-server-validation-plan.md` → `docs/reports/2026-05-18-pre-server-validation.md`
- **做发布或大改**：`docs/checklists/CHANGE_GATE.md` → `docs/checklists/RELEASE_READINESS.md`

## 文档分层

| 目录/文件 | 用途 | 是否当前有效 |
|---|---|---|
| `docs/specs/` | 功能规格与验收标准 | 是 |
| `docs/adr/` | 架构决策、权衡、迁移策略 | 是 |
| `docs/checklists/` | 评审、模型接入、发布前、文档更新门禁 | 是 |
| `docs/playbooks/` | 真实模型验证、供应商文档治理等操作手册 | 是 |
| `docs/reviews/` | 审计报告、整改 backlog、阶段性结论 | 是 |
| `docs/superpowers/plans/` | 代理执行计划、阶段性 TODO 与完成追踪 | 是 |
| `docs/阿里云模型api文档/` | 厂商原始镜像/摘录 | 否，原始参考，不是平台规范 |

## 当前结论

- 平台已具备基本自动化验证链：后端 pytest、前端 `typecheck/lint/build`
- 当前主风险不在“代码完全不可用”，而在：
  - 复杂页面/路由/服务文件过大
  - 前端自动化测试缺口明显
  - 主题 token 与文档约束存在回潮
  - `config.py ↔ models_registry ↔ frontend types ↔ docs` 多份真相并存
  - 供应商文档镜像包含样式碎片/控制字符，容易误导 AI

详见：`docs/reviews/2026-04-platform-audit.md`

## 开发门禁

任何非微小改动都应同时交付：

- 代码
- 验证证据
- 文档更新

以下情况还必须补齐 spec / ADR：

- 新功能或新任务能力
- 新模型接入
- 接口语义变化
- 重要状态流/数据流调整
- 影响多个页面/多个 router 的重构

## 常用文档

| 文档 | 说明 |
|------|------|
| [架构概览](./ARCHITECTURE.md) | 系统整体结构、请求流、多用户隔离 |
| [扩容转型路线图](./specs/2026-04-platform-scalability-transformation-roadmap.md) | 面向 1000 在线与 Linux 生产部署的渐进式改造总方案 |
| [pre 分支与 Docker 交付计划](./plans/2026-05-11-pre-branch-docker-delivery-plan.md) | `pre` 实验分支、Compose 本机构建交付和反向代理边界 |
| [pre 服务器优先验证计划](./plans/2026-05-18-pre-server-validation-plan.md) | `pre` 分支在 Ubuntu staging 独立 Compose 部署与验证的执行计划 |
| [pre 服务器验证报告](./reports/2026-05-18-pre-server-validation.md) | `pre` 分支 Ubuntu staging 部署、health/frontend 证据与未完成压测阻塞记录 |
| [2026-05-23 项目进度盘点报告](./reports/2026-05-23-project-progress-review.md) | 当前 `pre` 分支仓库、文档、测试、Compose 与未完成项盘点 |
| [未完成工作实施计划](./plans/2026-05-23-unfinished-work-implementation-plan.md) | 先补齐当前未闭环工作，并把后续架构选型延后到数据驱动讨论 |
| [下一阶段体验与性能治理报告](./reports/2026-05-24-next-phase-experience-and-performance.md) | Redis + Worker 闭环后的 pre 体验 smoke、轻量观测、S4 基线与 W2 阶梯压测记录 |
| [Compose PostgreSQL 升级优化计划](./plans/2026-06-06-postgres-upgrade-optimization-plan.md) | Compose 内 PostgreSQL、JSON 过渡、双写对账、分域读切换和最终数据库主数据源路线 |
| [PostgreSQL 平台升级执行计划](./superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md) | 数据库升级 goal 模式执行路线、前置检查、分阶段任务、服务器门禁和真实 smoke 边界 |
| [容量基线与压测手册](./playbooks/CAPACITY_BASELINE_AND_LOADTEST.md) | Step 00 的压测执行方法、字段要求与结果模板 |
| [运行模式矩阵](./playbooks/RUNTIME_MODE_MATRIX.md) | 开发环境、脚本生产模式、Compose 生产模式的边界对比 |
| [观测与轮询盘点](./reviews/2026-04-step-00-observability-and-polling-inventory.md) | 当前轮询热点、状态接口副作用与最小观测缺口 |
| [扩容架构 ADR](./adr/ADR-0002-server-grade-scalability-architecture.md) | 为什么采用 Redis + PostgreSQL + Worker + SSE 的渐进式路线 |
| [数据库前架构检查点 ADR](./adr/ADR-0003-pre-database-architecture-checkpoint.md) | 阶段 5/6 后接受 Compose 内 PostgreSQL 路线，以及分阶段迁移、JSON 过渡和对账边界 |
| [后端开发规范](./BACKEND.md) | FastAPI、服务层、schema/capabilities、适配器边界 |
| [前端开发规范](./FRONTEND.md) | React 页面、状态管理、错误处理、动态表单 |
| [UI 设计规范](./UI_GUIDELINES.md) | 主题 token、组件视觉约束 |
| [开发经验指南](./DEVELOPMENT_GUIDE.md) | 现有经验沉淀与补丁历史 |
| [工作室模型接入范式指南](./STUDIO_MODEL_INTEGRATION_GUIDE.md) | 模型接入总方法论 |
| [HappyHorse 视频工作室接入 Spec](./specs/2026-04-happyhorse-video-studio-integration.md) | HappyHorse 文生/图生/参考生/视频编辑接入约束与验收标准 |
| [审计报告](./reviews/2026-04-platform-audit.md) | 全平台批判性审计 |
| [整改 Backlog](./reviews/2026-04-remediation-backlog.md) | 分阶段治理路线 |
| [线上工作室卡顿调查](./reviews/2026-04-22-online-studio-investigation.md) | 2026-04-22 生产站 Edge 复现与接口超时证据 |
| [图片工作室卡顿治理 Spec](./specs/2026-04-studio-prod-latency-hardening.md) | 图片工作室预览降噪与生成接口异步化 |
| [Seedream 图片工作室接入 Spec](./specs/2026-04-seedream-image-studio-integration.md) | 火山引擎 Seedream 5.0 lite / 4.5 接入约束与验收标准 |
| [Nano Banana 图片工作室接入 Spec](./specs/2026-04-nano-banana-image-studio-integration.md) | Google Gemini Nano Banana 2 / Pro 接入约束与验收标准 |
| [代理执行计划](./superpowers/plans/) | 排查/实现计划落盘目录 |

## 运行与验证

### 环境要求

- Python 3.10+
- Node.js 18+
- `screen`

### 常用命令

```bash
./run.sh start
./run.sh stop
./run.sh status
./run.sh test
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_video_studio_capabilities.py -q
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
docker compose config
```

### 当前验证状态

- 后端全量测试：`./run.sh test`（2026-05-24，本地 230 passed）
- 后端关键测试：`backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_video_studio_capabilities.py backend/tests/test_video_studio_vace.py -q`
- 前端验证：`npm run typecheck`、`npm run lint`、`npm run build`（2026-05-24 均通过；build 提示 Browserslist/caniuse-lite 数据约 6 个月未更新）
- E2E helper：`npm run test:e2e:helper`（2026-04-24，2 passed）
- E2E smoke：`npm run test:e2e`（2026-06-05，7 passed，覆盖登录/未登录跳转、项目列表、旧版视频页迁退提示、视频工作室空态、文生视频创建流程和成功任务详情；macOS 可自动发现本机 `ms-playwright` Chromium 缓存）
- Compose 静态校验：`docker compose config`（2026-05-24，通过）
- 数据库升级本地进度：Compose PostgreSQL 基础设施、database health、Alembic schema、视频工作室任务 repository、backfill/reconcile、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror 均已落地；`studio_tasks` schema、Alembic migration、repository 边界、backfill/reconcile 工具、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror 也已落地；`projects` schema、Alembic migration `20260607_0003`、repository 边界、backfill/reconcile 工具、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror 已落地；media metadata 已新增 `media_assets`/`text_items` schema、Alembic migration `20260607_0004`、repository boundary、backfill/reconcile 工具、脱敏对账报告、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；project entities 已新增 `project_entities` schema、Alembic migration `20260607_0005`、角色/场景/道具/首帧/视频/风格 repository boundary、backfill/reconcile 工具、脱敏对账报告、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；benchmark records 已新增图片/视频测评 dataset、suite、run 的统一 schema、Alembic migration `20260607_0006`、repository boundary、backfill/reconcile 工具、脱敏对账报告、runtime dual-write、read-switch/JSON fallback 和 PostgreSQL primary-write/JSON archive mirror；默认运行态仍是 file-only，服务器 live migration/backfill/reconcile/dual-write/read-switch/primary-write 尚未闭环。2026-06-07 R29 staging connectivity refresh 因本机 Clash TUN/fake-IP、public health 超时和 SSH 命令被远端关闭仍不能执行服务器 rollout，本轮未修改服务器状态。
- 数据库升级 R35：user/config 本地 schema/repository boundary 已新增 `users`、`user_configs`、Alembic migration `20260607_0007` 和安全索引映射；登录、session 和 per-user `config.json` 运行态仍默认走 JSON/Redis/file-only，下一步补 user/config backfill/reconcile。
- 数据库升级 R36：user/config backfill/reconcile 服务和维护脚本已新增，摘要保持脱敏且不迁移 `sessions.json`；运行态仍默认 JSON/Redis/file-only，下一步补 user/config runtime dual-write/read-switch/primary-write gates。
- 数据库升级 R37：user/config runtime dual-write 已新增，注册/登录更新/改密码/config 保存默认仍 JSON 主写，显式启用后 shadow 写 PostgreSQL；session 仍保持 Redis + file fallback。
- 数据库升级 R38：user/config read-switch + JSON fallback 已新增，用户 ID/token 恢复和 per-user config 可显式优先 PostgreSQL；登录密码校验仍保持 JSON 主路径。
- 数据库升级 R39：user/config PostgreSQL primary-write + JSON archive mirror 已新增，本地域本地门禁闭环；服务器 live rollout、live migration/backfill/reconcile 和最终切库仍待恢复执行。
- 数据库升级 R40：服务器连通性复查仍阻塞 live rollout，当前本机 DNS/route 走 `198.18.*` fake-IP/TUN，SSH banner 和公网 health 超时；本轮未修改服务器状态。
- 数据库升级 R41：新增本地 PostgreSQL 实库演练脚本 `scripts/postgres_live_rehearsal.sh`，用于临时 Compose PostgreSQL 上串联 Alembic、全域 backfill/reconcile、备份和恢复演练；当前本机因 Docker daemon 不可用在 `docker-precheck` 阶段记录 blocked artifact，下一步启动 Docker 后复跑，或恢复服务器路径后执行同等 live gates。
- 数据库升级 R42：服务器路径短暂恢复后，staging repo 已 fast-forward 到 `e731245`，`postgres` 容器已启动且 `pg_isready` 接受连接，现有 API health 仍为 `200`；但 build 最新 `api` 镜像期间 SSH 控制面再次 banner 超时，Alembic/backfill/reconcile 和数据库业务开关尚未执行。
- 数据库升级 R43：服务器 PostgreSQL live migration/backfill/reconcile 已完成；Alembic head 为 `20260607_0007`，`video_studio_tasks=6`、`studio_tasks=12`、`projects=9`、`users=46`、`user_configs=40` 等脱敏计数已归档，备份/恢复演练通过；应用运行态仍保持 JSON/file-only，尚未启用数据库业务读写开关。
- 数据库升级 R44：准备进入 `video_studio_tasks` staging dual-write canary 时，先更新服务器 `compose.env` runtime commit 并保持 `MIEMIE_DATABASE_ENABLED=false`；构建新 `pre-local` 镜像期间 SSH 会话超时，随后本机 route 仍走 `utun1024`/`198.18.*` fake-IP，SSH banner 超时。本轮未重启容器、未启用数据库业务开关、未开始 dual-write canary；恢复后必须先只读审计镜像/容器/health。
- 数据库升级 R45：新增 `scripts/postgres_staging_video_task_canary.sh`，用于恢复 SSH 后按 `audit -> roll-runtime -> dual-write-canary` 三段继续 R44；脚本默认只读，显式滚动运行态时仍关闭数据库开关，显式 canary 时仅开启 `video_studio_tasks` 双写，并用维护写入验证 shadow write，避免真实供应商调用。
- 数据库升级 R46：新增 `scripts/verify_postgres_staging_canary_script.py`，把 R45 脚本的 shell 语法、缺 env blocked precheck、不触碰 Docker、默认只读和 no-provider smoke 契约固化为 app-free 本地 verifier；服务器 dual-write 仍未开启，等待 SSH banner 路径恢复后再执行三段门禁。
- 数据库升级 R47/R48：本地 Docker daemon 在沙盒外可用后重跑 `scripts/postgres_live_rehearsal.sh`；R47 定位到演练脚本查找 `*.dump` 但备份脚本产出 `*.sql` 的契约不一致，R48 修复后临时 Compose PostgreSQL、Alembic、全域 backfill/reconcile、`.sql` 备份和 restore rehearsal 全链路通过，临时容器已清理；服务器业务开关仍未启用。
- 数据库升级 R49：扩展 `scripts/postgres_staging_video_task_canary.sh`，补齐 `video_studio_tasks` staging `read-switch-canary` 与 `rollback-read-switch` 两段门禁；维护 canary 使用 JSON/PG 分叉状态证明读切换源和回滚源，verifier 也会编译脚本内嵌 Python；服务器仍待 SSH 恢复后执行。
- 数据库升级 R50：继续扩展 `scripts/postgres_staging_video_task_canary.sh`，补齐 `primary-write-canary` 与 `rollback-primary-write`；primary canary 证明 PostgreSQL 主写且不生成 JSON archive，rollback canary 证明回到 JSON 主写并保留 PostgreSQL shadow 写；服务器仍待 SSH 恢复后执行。
- 数据库升级 R51：新增 `scripts/postgres_staging_video_task_sequence.sh`，把 `audit -> roll-runtime -> dual-write-canary -> read-switch-canary -> rollback-read-switch -> primary-write-canary -> rollback-primary-write` 串成默认 dry-run、显式执行、失败即停的服务器序列 runner；本轮 SSH 仍在 banner exchange 超时，DNS/route 仍走 fake-IP/TUN，服务器未被修改。
- 数据库升级 R52：新增 `scripts/pre_studio_connectivity_preflight.sh`，在执行 R51 sequence 前统一检查 DNS fake-IP、TUN route、TCP 22、SSH banner 和公网 health；当前预检仍 blocked，DNS `198.18.0.80`、route `utun1024`、TCP 22 可达但 SSH banner 被关闭，公网 health 出现 HTTP/2 framing error。
- 数据库升级 R53：新增 `scripts/pre_studio_remote_postgres_sequence.sh`，将 R52 preflight 和 R51 sequence 串成一键远程编排；默认 dry-run，显式确认后先本地 preflight，通过才 SSH 到 `/opt/miemie-pre`，用 `git merge --ff-only origin/pre` 同步并执行服务器 sequence。当前实跑停在本地 preflight，未进入远端命令。
- `pre` Ubuntu staging：独立 Compose project `miemie-pre` 构建与启动通过，`/api/health` 与 `GET /` 通过；S1/S3 k6 与 1 个低频 DashScope 视频 smoke 已于 2026-05-23 补跑通过；Redis session / slowapi Redis storage / Celery worker 图片工作室队列 smoke 已在服务器通过；2026-05-24 Redis restart / unavailable 稳定性补强通过，worker 执行中断后任务永久 `generating` 已完成并通过 pre stale 验证；1 个真实 DashScope 图片队列 smoke 已补跑通过并删除测试用户 key；视频工作室 Worker 迁移 v1 已部署到 pre，health/首页/Celery、无 key 失败路径、`worker-video` restart 基础恢复和 1 个真实 DashScope 视频 smoke 均已通过；下一阶段无 key 体验 smoke 已验证列表快、提交即时反馈、重复点击去重和错误可见性；2026-05-25 真实浏览器补齐图片工作室门禁，普通模式未触发 `/api/studio/preview-payload`，生成点击有“提交中...”即时反馈，临时项目已清理；2026-05-29 `pre-studio.miemie.co` 公网反代门禁通过，Cloudflare / aaPanel Nginx 可稳定回源到 `127.0.0.1:18100`，登录页真实浏览器可渲染和切换注册表单；2026-05-30 至 2026-06-04 W2 阶梯压测、preview 修复复跑、状态观察、链路对照、DNS only 复跑、Cloudflare 入口复验、HTTP/3 关闭复验、Skip 规则复验、StorageService 修复部署复跑、Cloudflare Ray 诊断、300 VU 入口对照和本地客户端 Cloudflare 直连复测后，本机/公网 health 仍为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行
- 性能治理入口：新增高频运行路径脱敏耗时日志与 `loadtest/k6/s4-mixed-query-generate.js`，用于“多人查询 + 少量提交”的小而美容量证据采集；2026-05-29 公网反代后 S4 保守基线已完成，本机/公网只读与 preview 受控提交四组均失败率 `0`、P95 `<800ms`；2026-05-30 W2 阶梯压测性能 P95 达标，随后修复 per-user config 初始化竞态并复跑 preview 阶梯，服务端 `preview-payload` 状态码 `200 120`、无 5xx；W2 状态观察本机 100 VU 通过，DNS only 后公网 100 VU 通过、300 VU 无失败但 P95 `307.78ms` 略超保守门槛；StorageService 固定 tmp 文件竞态已修复并部署，应用侧 500 已清零；2026-06-03 Cloudflare 100 VU 已恢复通过，300 VU 入口对照显示 app direct / 本机 Nginx 通过，源站公网 IP P95 `325.81ms` 略超，Cloudflare P95 `512.92ms` 且有 1 次连接超时；本地 Mac 经 Clash TUN/fake-ip 代理出口访问 Cloudflare时 100 VU P95 `925.75ms`，添加 domain DIRECT 规则后系统层仍走 fake-ip/TUN 且 100 VU P95 `969.79ms`，关闭 TUN/fake-ip 后干净直连 Cloudflare 100 VU 无失败但 P95 `734.57ms`，本机 TUN 美国代理样本 100 VU 无失败但 P95 `960.63ms`。由于目标不关注大陆访问效果，本地跨境/代理客户端结果作为风险记录，不作为目标市场硬门禁；W2 平台侧阶段可收口，后续进入阶段 6 代码治理或另建目标市场入口 SLO
- 当前已消除：
  - FastAPI `on_event is deprecated` 警告
  - `baseline-browser-mapping` 数据过期提示
  - `./run.sh test` 落到系统 Python 导致依赖缺失的问题
  - 前端 `api.ts` 继续承载所有 domain API 的维护压力：已拆出 `apiClient.ts`、`studioApi.ts`、`videoStudioApi.ts`，并保持 `api.ts` 兼容 re-export
  - 项目列表、视频工作室任务列表/详情弹窗与基础创建流程缺少 smoke 护栏：`frontend/e2e/smoke.spec.ts` 已补项目列表样本、视频工作室成功任务样本、文生视频创建流程样本、参考素材创建流程样本和局部编辑源视频/Mask 面板样本，覆盖项目卡片/统计/入口、视频任务列表卡片/详情弹窗，以及新建任务弹窗提交回显、参考素材请求体和源视频准备后 Mask 面板
  - `VideoStudioPage.tsx` 继续保留旧创建/编辑表单死代码的维护压力：已删除两个 `{false && ...}` 包裹的不可达旧弹窗和专属旧状态/handler，页面降至 152 行并仅保留编排逻辑
- 当前保留为后续治理：
  - CI / 服务器环境仍需显式安装 Playwright Chromium；当前自动发现主要覆盖本机已有缓存的开发场景
  - `CapabilityCreateModal.tsx` 仍是视频工作室创建/编辑能力的主要复杂点；已先拆出 `DeveloperPreviewPanel.tsx`、`VideoFieldLabel.tsx`、`ReferenceCollectionsPanel.tsx`、`MaskEditorPanel.tsx` 与 `InputAssetSelector.tsx`，后续可继续提取参数区域等子组件或 hook；前端 smoke 可继续随拆分补编辑提交等更重路径；`StudioPage.tsx` 等大页面也仍需继续做行为保持型拆分
  - 数据库阶段已进入分域迁移：`ADR-0003` 已接受 Compose 内 PostgreSQL 作为最终核心业务状态库，`2026-06-06-postgres-upgrade-optimization-plan.md` 明确 JSON 过渡、双写对账、分域迁移和最终数据库主数据源路线，`2026-06-07-postgres-platform-upgrade-execution.md` 进一步落盘 goal 模式执行路线、服务器 preflight、停止条件、真实 smoke 边界和阶段门禁；本地已实现 Compose PostgreSQL 基础设施、`/api/health.database`、备份/恢复演练脚本、health 回归测试、Alembic 配置、`video_studio_tasks`、`studio_tasks`、`projects`、media metadata、project entities、benchmark records 和 user/config 的 schema/migration、repository boundary、backfill/reconcile 脚本和脱敏对账报告、runtime dual-write、PostgreSQL read switch + JSON fallback，以及 PostgreSQL primary-write + JSON archive mirror；R48 已完成本地临时 Compose PostgreSQL 实库演练，覆盖 Alembic、全域 backfill/reconcile、备份和恢复；R43 已完成服务器 PostgreSQL live migration/backfill/reconcile 和备份/恢复演练。R44 尝试进入 staging dual-write 前中断在新镜像 build/SSH 控制面恢复阶段，尚未重启容器或启用业务开关；R45/R46/R49/R50/R51/R52/R53 已补可重复服务器 canary 脚本、本地 app-free verifier、read-switch/rollback、primary-write/rollback、全序列 runner、本地连通性 preflight 和一键远程编排。当前应用运行态仍默认 JSON/file-only，staging dual-write、staging read switch 和 staging primary-write 尚未启用。

## 文档维护规则

- 供应商 API 变化，先更新 spec / ADR / checklist，再决定是否更新镜像文档
- 如果旧文档与新 spec 冲突，以 spec / ADR 为准，并尽快修正文档入口
- 不要把聊天上下文当规范；规范必须落盘

*最后更新：2026-06-07*
