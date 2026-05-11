# Step 01 Linux Compose 运行时验证报告

## 基本信息

- 日期：2026-05-08
- 执行人：Codex + 用户
- 服务器：`<staging-host>`
- 服务器规格：2 vCPU / 3.4GiB RAM / 49G root disk / 0 swap
- 操作系统：Ubuntu 24.04.4 LTS, Linux 6.8.0-63-generic
- 远端路径：`/root/miemie-studio-ha-lab`
- 运行模式：Docker Compose / 单 API 容器
- 宿主端口：`18000`
- 容器端口：`8000`
- 反向代理：无；本轮仅验证项目应用端口，反向代理继续用户自管
- Docker：`29.1.3`
- Docker Compose：`2.40.3`
- k6：`k6 v2.0.0-rc1`

## 远端快照

- Step 00 S0 基线 commit：`8fb46106a6347667bf527e6a4b3250088f9befb6`
- Step 01 Compose 修复后 commit / deployment_version：`2e1cd0d7875d4cb29dd2db25a9015d4f0d27e83e`
- Step 01 真实供应商 smoke 后 commit / deployment_version：`cebf8b4e49cbb963b9e8bfad16925cf9cf390936`
- 修复内容：Dockerfile 容器启动命令从 `sh -lc` 改为 `sh -c`，并显式执行 `/opt/venv/bin/gunicorn`
- 真实供应商 smoke 补丁：OSS 未启用时保留供应商视频 URL，成功状态清理旧错误信息
- 回归测试：`venv/bin/pytest backend/tests/test_docker_runtime.py -q`，本地通过，`1 passed`

## Compose 启动验证

命令：

```bash
MIEMIE_HOST_PORT=18000 \
MIEMIE_RUNTIME_GIT_COMMIT=2e1cd0d7875d4cb29dd2db25a9015d4f0d27e83e \
docker compose --project-directory /root/miemie-studio-ha-lab up -d --build --force-recreate api
```

结果：

- 镜像构建完成
- 容器：`miemie-studio-ha-lab-api-1`
- 状态：`Up ... (healthy)`
- 端口映射：`0.0.0.0:18000->8000/tcp`
- 进程：`gunicorn 26.0.0` + `uvicorn.workers.UvicornWorker`
- Worker：2 个

日志摘录：

```text
Starting gunicorn 26.0.0
Listening at: http://0.0.0.0:8000
Using worker: uvicorn.workers.UvicornWorker
Booting worker with pid: 8
Booting worker with pid: 9
Application startup complete.
```

健康检查：

```text
HTTP/1.1 200 OK
x-request-id: 28c8f7897ac1
x-deployment-version: 2e1cd0d7875d4cb29dd2db25a9015d4f0d27e83e
```

```json
{
  "status": "ok",
  "git_commit": "2e1cd0d7875d4cb29dd2db25a9015d4f0d27e83e",
  "run_mode": "prod",
  "serve_frontend": true,
  "started_at": "2026-05-08T08:04:19Z"
}
```

前端入口：

- `GET http://127.0.0.1:18000/`：200
- `content-type`：`text/html; charset=utf-8`
- 响应头包含 `X-Request-ID`
- 响应头包含 `X-Deployment-Version`
- 说明：`HEAD /` 返回 405，当前应用入口只验证 `GET /`。

## Compose 基线：S1 纯读流量

命令：

```bash
K6_VUS=50 K6_DURATION=60s K6_SLEEP_SECONDS=1 \
MIEMIE_BASE_URL=http://127.0.0.1:18000 \
LOADTEST_RUN_ID=step01-compose-s1-20260508 \
SCENARIO_NAME=S1-read-compose \
MIEMIE_AUTH_TOKEN=<token-from-server-env> \
k6 run --summary-export loadtest/results/step01-compose-s1-20260508-summary.json \
  loadtest/k6/s1-read.js
```

结果：

- 持续时间：60s
- 目标负载：50 VUs，每轮请求 `/api/health`、`/api/models`、`/api/projects`
- HTTP requests：8,676
- 平均请求率：约 142.37 req/s
- checks：26,028 / 26,028 通过
- HTTP 失败率：0.00%
- P95 / P99：44.30ms / 120.41ms
- 最大延迟：610.85ms
- 阈值：通过，`http_req_failed rate<0.01`，`http_req_duration p(95)<300`
- 数据下行：约 311MB

与 S0 脚本模式对比：

- S0 S1：8,637 requests，约 141.56 req/s，P95 48.62ms，P99 246.18ms
- Compose S1：8,676 requests，约 142.37 req/s，P95 44.30ms，P99 120.41ms
- 结论：同负载下 Compose 路径没有观察到读流量退化；P99 本轮更低，但只作为单次基线，不作为稳定性能结论。

## Compose 基线：S3 状态观察

命令：

```bash
K6_VUS=300 K6_DURATION=60s K6_SLEEP_SECONDS=3 \
MIEMIE_BASE_URL=http://127.0.0.1:18000 \
LOADTEST_RUN_ID=step01-compose-s3-observe-20260508 \
SCENARIO_NAME=S3-status-observe-compose \
MIEMIE_AUTH_TOKEN=<token-from-server-env> \
MIEMIE_TASK_STATUS_URLS=/api/video-studio/step00_status_5b504d48e44c/status \
k6 run --summary-export loadtest/results/step01-compose-s3-observe-20260508-summary.json \
  loadtest/k6/s3-task-observe.js
```

结果：

- 持续时间：60s
- 目标负载：300 个状态观察者，3s 轮询间隔
- HTTP requests：6,000
- 平均请求率：约 98.61 req/s
- checks：18,000 / 18,000 通过
- HTTP 失败率：0.00%
- P95 / P99：141.16ms / 193.99ms
- 最大延迟：309.54ms
- 阈值：通过，`http_req_failed rate<0.01`，`http_req_duration p(95)<800`
- 是否出现轮询放大：未观察到；请求量与 300 VUs / 3s 轮询间隔一致

与 S0 脚本模式对比：

- S0 S3 observe：6,000 requests，约 98.86 req/s，P95 133.93ms，P99 229.67ms
- Compose S3 observe：6,000 requests，约 98.61 req/s，P95 141.16ms，P99 193.99ms
- 结论：同负载下 Compose 状态观察路径可用，P95 略高、P99 略低；只作为首份 Compose 基线，不作容量上限判断。

## 真实供应商 S3 提交 smoke

目的：

- 补齐 Step 00 / Step 01 之前因未配置 DashScope key 而留下的真实供应商提交限制项。
- 只做低频 smoke，不对真实供应商做并发压测，避免费用和限流风险。

配置方式：

- DashScope key 通过 `/api/settings/api-key` 写入 staging 测试用户私有配置。
- key 未写入仓库、未拉回本地，报告与 artifacts 只保留脱敏结果。

提交参数：

- Runtime：Compose
- Base URL：`http://127.0.0.1:18000`
- deployment_version：`cebf8b4e49cbb963b9e8bfad16925cf9cf390936`
- 任务类型：`text_to_video`
- Provider：`wan`
- Model：`wan2.7-t2v`
- 规格：2 秒、720P、16:9、1 个 group
- App task：`8ef32388-087c-423c-a6d6-2a7449513f11`

结果：

- 平台任务状态：`succeeded`
- 供应商 task id 数量：1
- 供应商 request id 数量：1
- 视频结果数量：1
- `selected_video_url`：已设置
- `thumbnail_url`：未设置，因为 OSS 未启用
- `error_message`：`null`
- provider meta：1 条，包含 raw output，旧错误信息已清理

说明：

- 本轮验证证明真实 DashScope 提交、状态查询、结果落盘到平台任务记录的链路可用。
- 当前未配置真实 OSS，因此平台保留供应商返回的视频 URL；该 URL 可能是临时 URL，不作为长期资产持久化结论。
- 本轮不代表供应商提交承载上限，只代表低频 smoke 通过。

## 资源观察

压测后 `docker stats --no-stream miemie-studio-ha-lab-api-1` 摘要：

- CPU：0.20%
- 内存：286.2MiB / 3.417GiB，约 8.18%
- 网络：约 7.89MB in / 326MB out
- PIDs：10

说明：该快照是压测结束后的瞬时值，不代表压测峰值。

## 原始结果归档

- `docs/reports/artifacts/2026-05-08-step01-compose/step01-compose-s1-20260508.log`
- `docs/reports/artifacts/2026-05-08-step01-compose/step01-compose-s1-20260508-summary.json`
- `docs/reports/artifacts/2026-05-08-step01-compose/step01-compose-s3-observe-20260508.log`
- `docs/reports/artifacts/2026-05-08-step01-compose/step01-compose-s3-observe-20260508-summary.json`
- `docs/reports/artifacts/2026-05-08-step01-provider-smoke/miemie_provider_smoke_summary.json`
- `docs/reports/artifacts/2026-05-08-step01-provider-smoke/miemie_provider_health.txt`

## 结论

- Compose 推荐路径：首轮 Linux staging 验证通过。
- Step 01 运行边界：仍保持“项目只提供应用端口，反向代理用户自管”。
- 已验证：单一应用端口、健康检查、前端静态资源、`X-Request-ID`、`X-Deployment-Version`、S1 读基线、S3 状态观察基线、真实 DashScope 提交 smoke。
- 限制项：真实 OSS 未启用，生成视频未转存到长期存储；未做真实供应商高并发提交压测。
- 下一步：补齐 Step 01 文档收口后，进入 Step 02 Redis session/cache/rate-limit 设计与最小实装准备。
