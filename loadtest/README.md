# Step 00 压测资产

本目录提供 Step 00 收口所需的最小压测资产，默认面向 **Linux staging**。

## 当前资产

- `loadtest/k6/s1-read.js`
  - S1 纯读流量基线
  - 重点检查 `X-Request-ID` 与 `X-Deployment-Version`
- `loadtest/k6/s3-task-observe.js`
  - S3 任务提交/状态观察基线骨架
  - 默认推荐以 **已存在任务 ID 的状态观察** 建立平台侧基线
  - 可选地追加一个轻量的提交请求，用于测量提交接口 P95
- `loadtest/k6/s4-mixed-query-generate.js`
  - S4 多人查询 + 少量提交草案
  - 默认只压已有查询接口；提交样本必须显式配置
  - 用于判断现有 Compose + Redis + Worker 路径是否已足够支撑下一阶段体验目标

## 前提

- Linux staging 已通过 `./run.sh start --prod` 或 Compose 启动
- 已准备测试账号、认证 token、项目 ID、任务状态 URL
- 本机或服务器已安装 `k6`

## 推荐执行方式

### S1：纯读流量

```bash
k6 run loadtest/k6/s1-read.js \
  -e MIEMIE_BASE_URL=http://127.0.0.1:8000 \
  -e MIEMIE_AUTH_TOKEN=<token> \
  -e LOADTEST_RUN_ID=step00-s0-s1-001 \
  -e SCENARIO_NAME=S1-read-baseline
```

### S3：任务提交 + 状态观察

#### 推荐：平台侧状态观察基线

```bash
k6 run loadtest/k6/s3-task-observe.js \
  -e MIEMIE_BASE_URL=http://127.0.0.1:8000 \
  -e MIEMIE_AUTH_TOKEN=<token> \
  -e MIEMIE_TASK_STATUS_URLS=/api/video-studio/<task-id>/status,/api/image-benchmark/runs/<run-id> \
  -e LOADTEST_RUN_ID=step00-s0-s3-001 \
  -e SCENARIO_NAME=S3-task-observe
```

#### 可选：附带一个提交接口样本

```bash
k6 run loadtest/k6/s3-task-observe.js \
  -e MIEMIE_BASE_URL=http://127.0.0.1:8000 \
  -e MIEMIE_AUTH_TOKEN=<token> \
  -e MIEMIE_TASK_STATUS_URLS=/api/video-studio/<task-id>/status \
  -e MIEMIE_SUBMIT_URL=/api/video-studio/preview-payload \
  -e MIEMIE_SUBMIT_BODY='{"project_id":"<project-id>","task_type":"text_to_video","prompt":"压测校验","group_count":1}' \
  -e LOADTEST_RUN_ID=step00-s0-s3-submit-001 \
  -e SCENARIO_NAME=S3-task-submit-and-observe
```

说明：

- 默认不建议在 Step 00 对真实供应商发起大规模压测。
- 如果必须走真实供应商提交，请在报告里显式标记“真实供应商模式”。
- `MIEMIE_TASK_STATUS_URLS` 可以混合平台已有的状态查询接口，但应优先选择平台侧纯读接口。

### S4：多人查询 + 少量提交

默认只跑平台查询接口，不触发真实供应商任务：

```bash
k6 run loadtest/k6/s4-mixed-query-generate.js \
  -e MIEMIE_BASE_URL=http://127.0.0.1:8000 \
  -e MIEMIE_AUTH_TOKEN=<token> \
  -e MIEMIE_QUERY_URLS=/api/projects,/api/studio?project_id=<project-id>,/api/video-studio?project_id=<project-id> \
  -e LOADTEST_RUN_ID=step00-s4-mixed-001 \
  -e SCENARIO_NAME=S4-mixed-query-only
```

如需测少量提交，只使用平台 preview 或无 key 受控失败路径，不做真实供应商并发压测：

```bash
k6 run loadtest/k6/s4-mixed-query-generate.js \
  -e MIEMIE_BASE_URL=http://127.0.0.1:8000 \
  -e MIEMIE_AUTH_TOKEN=<token> \
  -e MIEMIE_QUERY_URLS=/api/projects,/api/video-studio?project_id=<project-id> \
  -e MIEMIE_SUBMIT_URL=/api/video-studio/preview-payload \
  -e MIEMIE_SUBMIT_BODY='{"project_id":"<project-id>","task_type":"text_to_video","prompt":"压测校验","group_count":1}' \
  -e MIEMIE_SUBMIT_EVERY=20 \
  -e LOADTEST_RUN_ID=step00-s4-mixed-002 \
  -e SCENARIO_NAME=S4-mixed-query-preview-submit
```
