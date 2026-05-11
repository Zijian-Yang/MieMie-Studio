# Step 00 S0 Linux staging 基线报告

## 基本信息

- 日期：2026-05-08
- 执行人：Codex + 用户
- Git commit：`8fb46106a6347667bf527e6a4b3250088f9befb6`
- deployment_version：`8fb46106a6347667bf527e6a4b3250088f9befb6`
- 环境类型：S0
- 服务器：`<staging-host>`
- 服务器规格：2 vCPU / 3.4GiB RAM / 49G root disk / 0 swap
- 操作系统：Ubuntu 24.04.4 LTS, Linux 6.8.0-63-generic
- 运行模式：`./run.sh start --prod`
- 实际进程：Gunicorn + UvicornWorker, 2 workers, bind `127.0.0.1:8000`
- 反向代理：无，项目仅监听本机应用端口
- 是否真实供应商：否
- 是否真实 OSS：否
- k6 版本：`k6 v2.0.0-rc1`
- 测试账户：`step00_loadtest_07a907e6`
- 测试项目：`b7f31d7c-2996-489b-8421-d95e58e106f3`
- synthetic 状态任务：`/api/video-studio/step00_status_5b504d48e44c/status`

## 执行前检查

- [x] `GET /api/health` 返回 `status=ok`
- [x] 响应头包含 `X-Request-ID`
- [x] 响应头包含 `X-Deployment-Version`
- [x] `git_commit` 与 `deployment_version` 对齐
- [x] 测试账号、token、项目 ID、状态 URL 已准备

健康检查摘录：

```json
{
  "status": "ok",
  "git_commit": "8fb46106a6347667bf527e6a4b3250088f9befb6",
  "run_mode": "prod",
  "serve_frontend": true,
  "started_at": "2026-05-08T07:39:45Z"
}
```

## 场景 S1：纯读流量

命令：

```bash
K6_VUS=50 K6_DURATION=60s K6_SLEEP_SECONDS=1 \
MIEMIE_BASE_URL=http://127.0.0.1:8000 \
LOADTEST_RUN_ID=step00-s0-s1-20260508-final \
SCENARIO_NAME=S1-read-baseline \
MIEMIE_AUTH_TOKEN=<token> \
k6 run --summary-export loadtest/results/step00-s0-s1-20260508-final-summary.json \
  loadtest/k6/s1-read.js
```

结果：

- 持续时间：60s
- 目标负载：50 VUs，每轮请求 `/api/health`、`/api/models`、`/api/projects`
- 实际负载摘要：8,637 HTTP requests，2,879 iterations，约 141.56 req/s
- 检查结果：25,911 / 25,911 通过
- HTTP 失败率：0.00%
- P95 / P99：48.62ms / 246.18ms
- 最大延迟：583.20ms
- 5xx 错误率：0.00%
- 是否出现文件 I/O 放大：未观察到错误；`/api/models` 响应体较大，60s 内下行约 309MB
- 主要瓶颈：当前样本未触发明显平台瓶颈，后续 W2 全量读场景需关注模型元数据响应体大小

## 场景 S3：任务提交 + 状态观察

### S3-A：提交 smoke

命令：

```bash
K6_VUS=5 K6_DURATION=30s K6_SLEEP_SECONDS=2 \
MIEMIE_BASE_URL=http://127.0.0.1:8000 \
LOADTEST_RUN_ID=step00-s0-s3-submit-20260508 \
SCENARIO_NAME=S3-submit-status-smoke \
MIEMIE_AUTH_TOKEN=<token> \
MIEMIE_TASK_STATUS_URLS=/api/video-studio/step00_status_5b504d48e44c/status \
MIEMIE_SUBMIT_URL=/api/video-studio \
MIEMIE_SUBMIT_BODY=<text-to-video-json> \
k6 run --summary-export loadtest/results/step00-s0-s3-submit-20260508-summary.json \
  loadtest/k6/s3-task-observe.js
```

结果：

- 持续时间：30s
- 目标负载：5 VUs，低并发提交 + 状态读取 smoke
- 实际负载摘要：150 HTTP requests，75 iterations，约 4.89 req/s
- 检查结果：444 / 450 通过
- 任务提交：73 / 75 被平台接受
- 状态观察：75 / 75 成功
- HTTP 失败率：1.33%
- P95：41.84ms
- 结论：未通过阈值，作为限制项记录

限制说明：

- 当前 staging 未配置真实 DashScope key。
- 后台供应商提交出现 `Illegal header value b'Bearer '`，说明缺 key 时后台提交会失败。
- k6 记录 2 次 submit transport failure：`connection reset by peer` / `EOF`。
- Gunicorn 进程仍存活，无 OOM 或 worker 崩溃证据。
- 该结果不作为真实供应商提交承载结论，只作为“无供应商配置时提交路径 smoke”记录。

### S3-B：状态观察基线

命令：

```bash
K6_VUS=300 K6_DURATION=60s K6_SLEEP_SECONDS=3 \
MIEMIE_BASE_URL=http://127.0.0.1:8000 \
LOADTEST_RUN_ID=step00-s0-s3-observe-20260508-final \
SCENARIO_NAME=S3-status-observe-baseline \
MIEMIE_AUTH_TOKEN=<token> \
MIEMIE_TASK_STATUS_URLS=/api/video-studio/step00_status_5b504d48e44c/status \
k6 run --summary-export loadtest/results/step00-s0-s3-observe-20260508-final-summary.json \
  loadtest/k6/s3-task-observe.js
```

结果：

- 持续时间：60s
- 目标负载：300 个状态观察者，3s 轮询间隔
- 实际负载摘要：6,000 HTTP requests，6,000 iterations，约 98.86 req/s
- 检查结果：18,000 / 18,000 通过
- HTTP 失败率：0.00%
- P95 / P99：133.93ms / 229.67ms
- 最大延迟：255.82ms
- 状态可见延迟 P95：本轮使用已存在 synthetic 状态任务，不测新任务状态可见延迟
- 状态查询 QPS：约 98.86 req/s
- 是否出现轮询放大：未超出配置模型；请求量与 300 VUs / 3s 轮询间隔一致
- 平台错误率：0.00%
- 供应商错误率：不适用，供应商关闭
- 主要瓶颈：未观察到状态读取瓶颈

## 本地验证包引用

- `./run.sh test`
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_video_studio_capabilities.py backend/tests/test_video_studio_vace.py -q`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm run test:e2e:helper`
- `cd frontend && npm run test:e2e`
- `docker compose config`

## 原始结果归档

- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s1-20260508-final.log`
- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s1-20260508-final-summary.json`
- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s3-observe-20260508-final.log`
- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s3-observe-20260508-final-summary.json`
- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s3-submit-20260508.log`
- `docs/reports/artifacts/2026-05-08-step00-s0/step00-s0-s3-submit-20260508-summary.json`

## 结论

- 是否通过：有条件通过，可作为 Step 00 首份 Linux S0 基线。
- 已满足：S0 脚本生产模式启动、健康检查、`X-Request-ID`、`X-Deployment-Version`、S1 读基线、S3 状态观察基线、结果归档。
- 限制项：S3 真实任务提交承载仍需有效供应商测试 key，或后续补一个明确的 provider-disabled synthetic submit 模式。
- 下一步动作：进入 Step 01 Linux runtime and edge，优先验证脚本兼容 + Compose 推荐双路径；Compose 基线完成后复跑 S1/S3。

## 后续补充

- 2026-05-08：Step 01 Compose 路径已使用真实 DashScope key 完成低频提交 smoke。
- 结果：`wan2.7-t2v` 真实任务提交、供应商 task id / request id、状态查询与平台任务记录落盘均已验证通过。
- 归档：`docs/reports/2026-05-08-step-01-linux-compose-validation.md` 与 `docs/reports/artifacts/2026-05-08-step01-provider-smoke/`。
- 说明：本 S0 报告保持历史原始结果不改写；真实供应商补验以 Step 01 Compose 报告为准。
