# pre 分支 Ubuntu 服务器优先验证计划

## 摘要

- 目标：在 Ubuntu staging 上独立部署并验证 `origin/pre@8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b`。
- 部署边界：不接入公网域名、不接入宝塔/Nginx、不影响旧实验服务。
- 默认隔离：远端目录 `/opt/miemie-pre`、Compose project `miemie-pre`、宿主回环端口 `127.0.0.1:18100`。
- 验证闭环：Compose build/up、health headers、前端入口、S1/S3 k6、低频真实 DashScope smoke、报告归档。

## 执行原则

- 不复用旧目录，不共用旧 `backend/data`。
- 不停止、不删除旧实验服务。
- 端口只绑定 `127.0.0.1`，公网不可直接访问。
- DashScope key 仅写入服务器测试用户私有配置，禁止进入命令输出、报告、仓库或 artifact。
- 若 SSH、Docker daemon、磁盘或依赖出现阻塞，先记录最小证据和恢复建议，再决定是否继续执行。

## 步骤

1. 服务器预检。
   - SSH 可用性。
   - 磁盘、内存、Docker、Docker Compose、k6。
   - 当前容器与端口占用。
   - `18100` 被占用时改用 `18101`；两者都被占用则停止。

2. 独立部署。
   - 在 `/opt/miemie-pre` clone/fetch 仓库并切到 `pre`。
   - 写入未跟踪 `compose.env`。
   - 设置 `MIEMIE_HOST_BIND=127.0.0.1`、`MIEMIE_HOST_PORT=18100`、`MIEMIE_WORKERS=2`。
   - 设置 `MIEMIE_RUNTIME_GIT_COMMIT=$(git rev-parse HEAD)`。
   - 使用本轮专属镜像标签，避免覆盖旧服务镜像。

3. Compose 验证。
   - 执行 `docker compose -p miemie-pre --env-file compose.env config`。
   - 执行 `docker compose -p miemie-pre --env-file compose.env up -d --build --force-recreate api`。
   - 确认容器 `healthy`。
   - 确认端口映射为 `127.0.0.1:18100->8000/tcp`。

4. 接口验证。
   - `curl -i http://127.0.0.1:18100/api/health`。
   - 确认 `X-Request-ID`、`X-Deployment-Version`。
   - 确认 JSON 中 `git_commit` 与 `origin/pre` commit 对齐。
   - 验证前端入口 `GET /`。

5. 压测验证。
   - S1：`loadtest/k6/s1-read.js`，目标为登录态读接口。
   - S3：`loadtest/k6/s3-task-observe.js`，目标为平台侧任务状态观察。
   - 保存 k6 summary JSON 与日志。
   - 记录 P95/P99、错误率、请求量、是否出现轮询放大。

6. 低频真实供应商 smoke。
   - 仅提交 1 个真实 DashScope 视频任务。
   - 只验证提交、状态观察、平台落状态。
   - 不做真实供应商并发压测。
   - 未配置可用 key 时标记为阻塞项。

7. 归档。
   - 更新 `docs/reports/2026-05-18-pre-server-validation.md`。
   - 原始摘要放入 `docs/reports/artifacts/2026-05-18-pre-server/`。
   - 报告只保留脱敏服务器标识、commit、deployment version、端口、命令摘要和结果。

## 当前阻塞处理

如果 SSH 在执行中断开且恢复失败：

- 先保留已经完成的部署和接口证据。
- 明确标记未执行项：S1、S3、DashScope smoke、资源快照。
- 给出服务器侧最小排障命令。
- 不伪造压测或 smoke 结果。
