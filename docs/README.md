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
| [容量基线与压测手册](./playbooks/CAPACITY_BASELINE_AND_LOADTEST.md) | Step 00 的压测执行方法、字段要求与结果模板 |
| [运行模式矩阵](./playbooks/RUNTIME_MODE_MATRIX.md) | 开发环境、脚本生产模式、Compose 生产模式的边界对比 |
| [观测与轮询盘点](./reviews/2026-04-step-00-observability-and-polling-inventory.md) | 当前轮询热点、状态接口副作用与最小观测缺口 |
| [扩容架构 ADR](./adr/ADR-0002-server-grade-scalability-architecture.md) | 为什么采用 Redis + PostgreSQL + Worker + SSE 的渐进式路线 |
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
- E2E smoke：`npm run test:e2e`（2026-04-24，4 passed，macOS 可自动发现本机 `ms-playwright` Chromium 缓存）
- Compose 静态校验：`docker compose config`（2026-05-24，通过）
- `pre` Ubuntu staging：独立 Compose project `miemie-pre` 构建与启动通过，`/api/health` 与 `GET /` 通过；S1/S3 k6 与 1 个低频 DashScope 视频 smoke 已于 2026-05-23 补跑通过；Redis session / slowapi Redis storage / Celery worker 图片工作室队列 smoke 已在服务器通过；2026-05-24 Redis restart / unavailable 稳定性补强通过，worker 执行中断后任务永久 `generating` 已完成并通过 pre stale 验证；1 个真实 DashScope 图片队列 smoke 已补跑通过并删除测试用户 key；视频工作室 Worker 迁移 v1 已部署到 pre，health/首页/Celery、无 key 失败路径、`worker-video` restart 基础恢复和 1 个真实 DashScope 视频 smoke 均已通过；下一阶段无 key 体验 smoke 已验证列表快、提交即时反馈、重复点击去重和错误可见性；2026-05-25 真实浏览器补齐图片工作室门禁，普通模式未触发 `/api/studio/preview-payload`，生成点击有“提交中...”即时反馈，临时项目已清理；2026-05-29 `pre-studio.miemie.co` 公网反代门禁通过，Cloudflare / aaPanel Nginx 可稳定回源到 `127.0.0.1:18100`，登录页真实浏览器可渲染和切换注册表单；2026-05-30 至 2026-06-04 W2 阶梯压测、preview 修复复跑、状态观察、链路对照、DNS only 复跑、Cloudflare 入口复验、HTTP/3 关闭复验、Skip 规则复验、StorageService 修复部署复跑、Cloudflare Ray 诊断、300 VU 入口对照和本地客户端 Cloudflare 复测后，本机/公网 health 仍为 `200`，`api`、`redis`、`worker`、`worker-video` 均保持运行
- 性能治理入口：新增高频运行路径脱敏耗时日志与 `loadtest/k6/s4-mixed-query-generate.js`，用于“多人查询 + 少量提交”的小而美容量证据采集；2026-05-29 公网反代后 S4 保守基线已完成，本机/公网只读与 preview 受控提交四组均失败率 `0`、P95 `<800ms`；2026-05-30 W2 阶梯压测性能 P95 达标，随后修复 per-user config 初始化竞态并复跑 preview 阶梯，服务端 `preview-payload` 状态码 `200 120`、无 5xx；W2 状态观察本机 100 VU 通过，DNS only 后公网 100 VU 通过、300 VU 无失败但 P95 `307.78ms` 略超保守门槛；StorageService 固定 tmp 文件竞态已修复并部署，应用侧 500 已清零；2026-06-03 Cloudflare 100 VU 已恢复通过，300 VU 入口对照显示 app direct / 本机 Nginx 通过，源站公网 IP P95 `325.81ms` 略超，Cloudflare P95 `512.92ms` 且有 1 次连接超时；本地 Mac 经 Clash TUN/fake-ip 代理出口访问 Cloudflare 时 100 VU P95 `925.75ms`，添加 domain DIRECT 规则后系统层仍走 fake-ip/TUN 且 100 VU P95 `969.79ms`，下一步需临时关闭 TUN/fake-ip 或换不经 Clash 的客户端网络补直连样本
- 当前已消除：
  - FastAPI `on_event is deprecated` 警告
  - `baseline-browser-mapping` 数据过期提示
  - `./run.sh test` 落到系统 Python 导致依赖缺失的问题
- 当前保留为后续治理：
  - CI / 服务器环境仍需显式安装 Playwright Chromium；当前自动发现主要覆盖本机已有缓存的开发场景

## 文档维护规则

- 供应商 API 变化，先更新 spec / ADR / checklist，再决定是否更新镜像文档
- 如果旧文档与新 spec 冲突，以 spec / ADR 为准，并尽快修正文档入口
- 不要把聊天上下文当规范；规范必须落盘

*最后更新：2026-06-04*
