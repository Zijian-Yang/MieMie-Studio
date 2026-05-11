# Step 00 验证包（本地已完成项 + Linux staging 结果）

## 目的

把 Step 00 已完成的本地验证与 Linux staging S0 基线压测放到同一个验证包里，方便后续关账与 Step 01 对比。

## 当前已完成的本地验证

- `./run.sh test`：`130 passed in 39.56s`
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_video_studio_capabilities.py backend/tests/test_video_studio_vace.py -q`：`65 passed`
- `cd frontend && npm run typecheck`：通过
- `cd frontend && npm run lint`：通过
- `cd frontend && npm run build`：通过
- `cd frontend && npm run test:e2e:helper`：`2 passed`
- `cd frontend && npm run test:e2e`：`4 passed`
- `docker compose config`：通过
- `docker build -t miemie-studio:step01-check .`：当前阻塞（本机会话中 Docker daemon 未运行）

## Step 00 当前状态

- 文档口径：已统一
- 最小观测补丁：已落地
- 统一轮询抽象：已落地
- 本地验证包：已齐
- **Linux staging S0 基线压测：已执行**

## Linux staging S0 结果

- 报告：`docs/reports/2026-04-24-step-00-s0-linux-baseline-template.md`
- 归档：`docs/reports/artifacts/2026-05-08-step00-s0/`
- 服务器：`<staging-host>`
- Git commit / deployment_version：`8fb46106a6347667bf527e6a4b3250088f9befb6`
- 运行模式：S0 / `./run.sh start --prod`
- S1 纯读流量：50 VUs, 60s, 0% HTTP 失败, P95 48.62ms, P99 246.18ms
- S3 状态观察：300 VUs, 60s, 3s 轮询, 0% HTTP 失败, P95 133.93ms, P99 229.67ms
- S3 提交 smoke：已执行，因 staging 未配置真实 DashScope key，提交段出现 2 次 transport failure，记录为限制项

## Step 01 Compose 验证入口

- 报告：`docs/reports/2026-05-08-step-01-linux-compose-validation.md`
- 归档：`docs/reports/artifacts/2026-05-08-step01-compose/`
- Git commit / deployment_version：`cebf8b4e49cbb963b9e8bfad16925cf9cf390936`
- 运行模式：Docker Compose，宿主端口 `18000` 映射容器端口 `8000`
- 健康检查：`GET /api/health` 返回 200，包含 `X-Request-ID` / `X-Deployment-Version`
- 前端入口：`GET /` 返回 200 `text/html`
- S1 纯读流量：50 VUs, 60s, 0% HTTP 失败, P95 44.30ms, P99 120.41ms
- S3 状态观察：300 VUs, 60s, 3s 轮询, 0% HTTP 失败, P95 141.16ms, P99 193.99ms
- S3 真实供应商提交 smoke：`wan2.7-t2v`, 1 个任务, 1 个供应商 task id, 1 个 request id, 1 个视频结果, 平台状态 `succeeded`
- Compose 修复：Dockerfile 避免 `sh -lc` login shell 重置 `PATH`，改为显式执行 `/opt/venv/bin/gunicorn`
- 供应商结果修复：OSS 未启用时保留供应商视频 URL，成功状态清理旧 provider 错误信息

## 当前限制项

- S0 脚本模式的历史提交 smoke 仍保留原限制记录；真实 DashScope 提交已在 Step 01 Compose 路径低频 smoke 验证通过。
- 真实 OSS 未启用：当前视频结果未转存长期 OSS，仅验证供应商提交、状态查询和平台任务记录落盘。
- 本机 Docker daemon 仍未运行：本机 `docker build` 未验证；Linux staging 已完成 Compose 构建与运行验证。
- npm install 报告 16 个依赖漏洞：本轮未做依赖升级，避免改变压测基线。

## 下一步执行入口

1. 进入 `docs/specs/2026-04-step-01-linux-runtime-and-edge.md`。
2. Step 01 文档口径收口：确认部署文档、运行模式矩阵和反向代理边界没有冲突。
3. 后续如需长期资产闭环，补 OSS staging 配置并复跑一次真实供应商结果转存。
4. 进入 Step 02 Redis session/cache/rate-limit 准备。

## 进入 Step 01 的前提

- Linux staging S0 基线记录已落盘：已满足
- 当前本地验证结果已汇总到同一验证包：已满足
- 无新增“先补 Step 00 基础观测字段”的阻塞项：已满足
