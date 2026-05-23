# pre 分支 Ubuntu 服务器验证报告

## 基本信息

- 日期：2026-05-18
- 执行人：Codex + 用户
- 服务器：`<staging-host>`
- 服务器规格：2 vCPU / 3.4GiB RAM / 49G root disk / 0 swap
- 操作系统：Ubuntu 24.04.4 LTS, Linux 6.8.0-63-generic
- 远端路径：`/opt/miemie-pre`
- 运行模式：Docker Compose / 单 API 容器
- Compose project：`miemie-pre`
- 宿主绑定：`127.0.0.1:18100`
- 容器端口：`8000`
- 反向代理：无；本轮不接入宝塔、域名或 Nginx
- Docker：`29.1.3`
- Docker Compose：`2.40.3`
- k6：`k6 v2.0.0-rc1`

## 目标版本

- Git 分支：`pre`
- Git commit / deployment_version：`8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b`
- 镜像标签：`miemie-studio:pre-local`
- 旧实验服务：保留运行，未停止、未删除

## 预检结果

- `/` 磁盘：49G total，11G used，37G free，22%
- 内存：3.4Gi total，1.7Gi used，1.7Gi available
- 旧服务端口：`18000` 已被旧实验服务占用
- 目标端口：`18100` 预检空闲
- 旧服务容器：`miemie-studio-ha-lab-api-1`，最后确认状态为 `Up ... (healthy)`，映射 `0.0.0.0:18000->8000/tcp`

## Compose 部署验证

执行摘要：

```bash
docker compose -p miemie-pre \
  --env-file compose.env \
  -f docker-compose.yml \
  -f docker-compose.pre.override.yml \
  config

docker compose -p miemie-pre \
  --env-file compose.env \
  -f docker-compose.yml \
  -f docker-compose.pre.override.yml \
  up -d --build --force-recreate api
```

结果：

- `docker compose config`：完成，输出保存于服务器 `/tmp/miemie-pre-compose-config.txt`
- `docker compose up`：退出码 `0`
- 容器：`miemie-pre-api-1`
- 状态：`Up ... (healthy)`
- 端口映射：`127.0.0.1:18100->8000/tcp`
- 旧服务仍在 `18000`，未被本轮 Compose project 影响

## 健康检查与前端入口

`GET /api/health`：

```text
HTTP/1.1 200 OK
x-request-id: 9def9922f367
x-deployment-version: 8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b
```

```json
{
  "status": "ok",
  "git_commit": "8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b",
  "run_mode": "prod",
  "serve_frontend": true,
  "started_at": "2026-05-18T01:02:23Z"
}
```

`GET /`：

- HTTP 状态：`200 OK`
- `content-type`：`text/html; charset=utf-8`
- `x-request-id`：`8019438b3682`
- `x-deployment-version`：`8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b`
- body 起始：`<!DOCTYPE html><html lang="zh-CN">`

`HEAD /`：

- HTTP 状态：`405 Method Not Allowed`
- 响应头仍包含 `X-Request-ID` 与 `X-Deployment-Version`
- 结论：当前前端入口以 `GET /` 作为有效验证口径；是否补齐 `HEAD /` 支持留作运行边界待评估项。

## 2026-05-23 补跑状态

SSH 于 2026-05-23 恢复可用后，按补跑清单只操作 `/opt/miemie-pre` 与 Compose project `miemie-pre`，旧实验服务未停止、未删除、未重启。

补跑前状态：

- `miemie-pre-api-1`：`Up 5 days (healthy)`
- 端口映射：`127.0.0.1:18100->8000/tcp`
- 旧服务：`miemie-studio-ha-lab-api-1` 仍在 `18000`
- Git commit / deployment version：`8ed6c246991650eb6ac43b28fd43c1ba9b0d4d0b`
- `/api/health`：`200 OK`
- `GET /`：`200 OK`
- `HEAD /`：仍为 `405 Method Not Allowed`，响应头保留 `X-Request-ID` 与 `X-Deployment-Version`

### S1 纯读 k6

命令摘要：

```bash
K6_VUS=50 K6_DURATION=60s K6_SLEEP_SECONDS=1 \
MIEMIE_BASE_URL=http://127.0.0.1:18100 \
LOADTEST_RUN_ID=pre-server-s1-20260523 \
SCENARIO_NAME=S1-read-pre-server \
k6 run --summary-export validation-artifacts/2026-05-18-pre-server/pre-server-s1-20260523-summary.json \
  loadtest/k6/s1-read.js
```

结果：

- HTTP requests：8,532
- 平均请求率：约 139.83 req/s
- checks：25,596 / 25,596 通过
- HTTP 失败率：0.00%
- P95 / P99：58.78ms / 142.51ms
- 最大延迟：802.61ms
- 阈值：通过，`http_req_failed rate<0.01`，`http_req_duration p(95)<300`
- 数据下行：约 381MB

### S3 状态观察 k6

本轮创建了一个平台侧视频工作室状态观察任务。由于验证用户未配置 DashScope API key，供应商提交失败，平台任务进入 `failed`，但 `/api/video-studio/{task_id}/status` 作为纯读状态观察目标可用。

命令摘要：

```bash
K6_VUS=300 K6_DURATION=60s K6_SLEEP_SECONDS=3 \
MIEMIE_BASE_URL=http://127.0.0.1:18100 \
LOADTEST_RUN_ID=pre-server-s3-observe-20260523 \
SCENARIO_NAME=S3-status-observe-pre-server \
MIEMIE_TASK_STATUS_URLS="/api/video-studio/<task-id>/status" \
k6 run --summary-export validation-artifacts/2026-05-18-pre-server/pre-server-s3-observe-20260523-summary.json \
  loadtest/k6/s3-task-observe.js
```

结果：

- HTTP requests：6,000
- 平均请求率：约 98.68 req/s
- checks：18,000 / 18,000 通过
- HTTP 失败率：0.00%
- P95 / P99：151.62ms / 281.65ms
- 最大延迟：325.68ms
- 阈值：通过，`http_req_failed rate<0.01`，`http_req_duration p(95)<800`
- 请求量符合 300 VUs / 3s 轮询间隔，未观察到轮询放大

### 低频真实 DashScope smoke

首次补跑时未执行真实供应商 smoke，阻塞原因是 staging 验证用户未配置 DashScope API key：

```json
{
  "executed": false,
  "blocked_reason": "DashScope API key is not configured for the staging validation user.",
  "platform_status": "failed",
  "error_class": "missing_api_key_or_empty_bearer",
  "result_video_count": 0
}
```

随后使用用户提供的 DashScope API key 临时写入 staging 验证用户私有配置，仅提交 1 个真实文生视频任务。任务完成后已删除 staging 验证用户中的 API key，报告与 artifact 不包含 key 或真实视频 URL。

成功摘要：

```json
{
  "executed": true,
  "platform_status": "succeeded",
  "result_video_count": 1,
  "selected_video_url_set": true,
  "thumbnail_url_set": false,
  "request_id_count": 1,
  "task_id_count": 1,
  "error_message": null,
  "oss_enabled": false
}
```

说明：当前未启用 OSS，因此 smoke 只证明真实 DashScope 提交、平台状态协调与结果落状态可用，不证明生成视频已经转存到长期对象存储。

### 资源快照

压测后 `docker stats --no-stream miemie-pre-api-1` 摘要：

- CPU：0.21%
- 内存：266.1MiB / 3.417GiB，约 7.60%
- 网络：约 7.89MB in / 398MB out
- PIDs：13

宿主机摘要：

- `/` 磁盘：49G total，13G used，34G free，28%
- 内存：3.4Gi total，2.0Gi used，1.4Gi available
- Swap：0B

## 2026-05-23 Redis / Worker 服务器验证

在本地提交 `c46c83db378f3c02759da44135233617673445ea` 推送到 `origin/pre` 后，已在服务器 `/opt/miemie-pre` 执行真实部署验证。本轮仍只操作 Compose project `miemie-pre`，旧实验服务未停止、未删除、未重启。

部署动作摘要：

```bash
cd /opt/miemie-pre
git fetch origin
git pull --ff-only origin pre
sed -i "s/^MIEMIE_RUNTIME_GIT_COMMIT=.*/MIEMIE_RUNTIME_GIT_COMMIT=$(git rev-parse HEAD)/" compose.env

docker compose -p miemie-pre \
  --env-file compose.env \
  -f docker-compose.yml \
  -f docker-compose.pre.override.yml \
  config

docker compose -p miemie-pre \
  --env-file compose.env \
  -f docker-compose.yml \
  -f docker-compose.pre.override.yml \
  up -d --build --force-recreate api redis worker
```

运行态隔离修正：

- 初次启动后 `worker` 仍显示默认镜像名 `miemie-studio:local`。
- 为减少与旧实验服务的镜像标签交叉，服务器本地 `docker-compose.pre.override.yml` 已补充 `worker.image: miemie-studio:pre-local`。
- 重新 `up -d --no-build --force-recreate worker` 后，`api` 与 `worker` 均显示 `miemie-studio:pre-local`。

容器状态：

```text
NAME                  IMAGE                     SERVICE   STATUS
miemie-pre-api-1      miemie-studio:pre-local   api       Up ... (healthy)
miemie-pre-redis-1    redis:7-alpine            redis     Up ... (healthy)
miemie-pre-worker-1   miemie-studio:pre-local   worker    Up ...
```

`GET /api/health`：

```text
HTTP/1.1 200 OK
x-deployment-version: c46c83db378f3c02759da44135233617673445ea
```

```json
{
  "status": "ok",
  "git_commit": "c46c83db378f3c02759da44135233617673445ea",
  "run_mode": "prod",
  "serve_frontend": true,
  "redis": {
    "configured": true,
    "ok": true
  }
}
```

`GET /`：

- HTTP 状态：`200`

Redis session / rate-limit smoke：

```json
{
  "register_status": 200,
  "token_returned": true,
  "redis_session_count_after_register": 1,
  "redis_rate_limit_keys_after_register": 1,
  "me_status_before_logout": 200,
  "logout_status": 200,
  "me_status_after_logout": 401,
  "login_status_after_logout": 200,
  "redis_session_count_after_login": 1,
  "change_password_status": 200,
  "me_status_after_change_password": 401,
  "redis_session_count_after_change_password": 0,
  "old_password_login_status": 401,
  "new_password_login_status": 200,
  "new_token_returned": true
}
```

Celery worker 验证：

- `celery inspect ping`：`1 node online`
- `celery inspect registered`：注册任务包含 `studio.generate`
- 图片工作室 API 队列 smoke：`POST /api/studio/{task_id}/generate` 在约 `157.5ms` 返回 `generating`
- 本轮没有再次写入真实供应商 key；任务被 worker 接走后因缺少供应商 key 受控进入 `failed`，用于证明 API 快速返回、Celery 消费和平台状态写回链路可用。
- worker 日志包含 `Task studio.generate[...] received` 与随后成功结束 worker 函数调用。

资源快照：

- `api`：约 284.2MiB / 3.417GiB，CPU 0.20%
- `worker`：约 147.6MiB / 3.417GiB，CPU 0.13%
- `redis`：约 25.02MiB / 3.417GiB，CPU 0.40%
- `/` 磁盘：49G total，15G used，33G free，31%
- 宿主内存：3.4Gi total，2.1Gi used，1.3Gi available，0 swap

脱敏 artifacts：

- `docs/reports/artifacts/2026-05-23-redis-worker-server/compose-ps-post-worker-image-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/health-post-worker-image-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/get-root-redis-worker-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/auth-redis-session-smoke-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/worker-dispatch-smoke-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/celery-ping-post-worker-image-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/celery-registered-post-worker-image-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/docker-stats-redis-worker-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/disk-redis-worker-20260523.txt`
- `docs/reports/artifacts/2026-05-23-redis-worker-server/memory-redis-worker-20260523.txt`

边界与后续项：

- 服务器 SSH 新连接仍偶发 `Connection closed by <staging-host> port 22`，但既有会话可完成部署与验证；后续仍建议排查 sshd / 云安全策略。
- Celery 当前容器以 root 用户运行，worker 启动日志有 Celery `SecurityWarning`；本轮不改变容器用户，作为后续容器硬化项记录。
- 本轮 worker smoke 未消耗真实供应商额度；真实图片生成队列成功率需要在确认要使用供应商 key 时再补 1 个低频任务。

## 原始阻塞记录

2026-05-18 本轮尚未完成 S1/S3 k6 和 DashScope smoke。原因不是应用接口失败，而是远端 SSH 在创建验证用户后开始于握手前关闭连接：

```text
kex_exchange_identification: Connection closed by remote host
Connection closed by <staging-host> port 22
```

已额外确认：

- `nc` 可建立到 22 端口的 TCP 连接。
- `ssh-keyscan -T 10 <staging-host>` 未返回 SSH host key。
- 现象更接近 sshd 或云安全策略临时拒绝新 SSH 会话，而不是应用容器本身的 HTTP 健康检查失败。

已完成但未继续验证的准备项：

- 创建了 staging 专用验证用户。
- 认证 token 仅保存于服务器 `/tmp/miemie-pre-auth.token`，未写入仓库或报告。
- S3 种子任务提交命令执行时 SSH 断开，任务是否创建需要 SSH 恢复后复查。

## 当前未完成项

- S1 纯读 k6：已于 2026-05-23 补跑通过。
- S3 状态观察 k6：已于 2026-05-23 补跑通过。
- 压测后 `docker stats` 资源快照：已于 2026-05-23 补采。
- 低频真实 DashScope smoke：已于 2026-05-23 补跑成功。
- 真实 smoke summary JSON：已生成阻塞摘要与成功摘要。

## SSH 恢复后补跑清单

1. 确认 SSH 恢复。

```bash
ssh root@<staging-host> 'date && docker ps --format "{{.Names}} {{.Status}} {{.Ports}}"'
```

2. 确认 `pre` 服务仍健康。

```bash
cd /opt/miemie-pre
docker compose -p miemie-pre --env-file compose.env \
  -f docker-compose.yml \
  -f docker-compose.pre.override.yml ps
curl -i http://127.0.0.1:18100/api/health
```

3. 如 `/tmp/miemie-pre-auth.token` 不存在，重新创建一次性验证用户。

4. 创建或确认一个平台侧状态观察任务。

5. 补跑 S1。

```bash
cd /opt/miemie-pre
K6_VUS=50 K6_DURATION=60s K6_SLEEP_SECONDS=1 \
MIEMIE_BASE_URL=http://127.0.0.1:18100 \
LOADTEST_RUN_ID=pre-server-s1-20260518 \
SCENARIO_NAME=S1-read-pre-server \
MIEMIE_AUTH_TOKEN="$(cat /tmp/miemie-pre-auth.token)" \
k6 run --summary-export validation-artifacts/2026-05-18-pre-server/pre-server-s1-20260518-summary.json \
  loadtest/k6/s1-read.js
```

6. 补跑 S3。

```bash
cd /opt/miemie-pre
K6_VUS=300 K6_DURATION=60s K6_SLEEP_SECONDS=3 \
MIEMIE_BASE_URL=http://127.0.0.1:18100 \
LOADTEST_RUN_ID=pre-server-s3-observe-20260518 \
SCENARIO_NAME=S3-status-observe-pre-server \
MIEMIE_AUTH_TOKEN="$(cat /tmp/miemie-pre-auth.token)" \
MIEMIE_TASK_STATUS_URLS="/api/video-studio/<task-id>/status" \
k6 run --summary-export validation-artifacts/2026-05-18-pre-server/pre-server-s3-observe-20260518-summary.json \
  loadtest/k6/s3-task-observe.js
```

7. 补跑低频真实 DashScope smoke。

- 仅 1 个视频任务。
- 不做并发供应商压测。
- key 只写入服务器验证用户私有配置。
- 报告只记录脱敏状态、task id 数量、request id 数量、平台状态和是否落结果。

## 结论

- 已验证：`pre` 分支可在 Ubuntu staging 上用独立 Compose project 构建并启动，容器健康，端口只绑定 `127.0.0.1:18100`，`/api/health` 与 `GET /` 均携带正确的请求追踪与部署版本。
- 已补齐：S1 纯读 k6、S3 状态观察 k6 与压测后资源快照。
- 已补齐：低频真实 DashScope smoke，1 个真实视频任务成功，平台记录 1 个结果视频、1 个供应商 task id 和 1 个 request id。
- 限制项：真实 OSS 未启用，生成视频未转存到长期对象存储；本轮不代表供应商并发提交能力。
- 下一步：阶段 1 服务器验证闭环已完成，可进入 Step 02 Redis session/cache/rate-limit 的最小实装准备。

## 2026-05-23 原始结果归档

- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-health-20260523.txt`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-compose-ps-20260523.txt`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-docker-stats-20260523.txt`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-disk-20260523.txt`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-memory-20260523.txt`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-s1-20260523.log`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-s1-20260523-summary.json`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-s3-observe-20260523.log`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-s3-observe-20260523-summary.json`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-provider-smoke-20260523-summary.json`
- `docs/reports/artifacts/2026-05-18-pre-server/pre-server-provider-smoke-20260523-success-summary.json`
