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

## 压测与供应商 smoke 状态

本轮尚未完成 S1/S3 k6 和 DashScope smoke。原因不是应用接口失败，而是远端 SSH 在创建验证用户后开始于握手前关闭连接：

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

## 未完成项

- S1 纯读 k6：未执行。
- S3 状态观察 k6：未执行。
- 低频真实 DashScope smoke：未执行。
- 压测后 `docker stats` 资源快照：未执行。
- k6 summary JSON 与 smoke summary JSON：未生成。

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
- 未完成：S1/S3 k6、DashScope smoke 和资源快照，阻塞于 SSH 服务层访问中断。
- 下一步：先恢复 SSH，再按补跑清单完成压测和供应商 smoke，随后更新本报告为完整闭环报告。
