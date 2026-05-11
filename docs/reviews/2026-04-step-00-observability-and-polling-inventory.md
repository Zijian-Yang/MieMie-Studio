# 2026-04 Step 00：观测与轮询现状盘点

## 范围

- 前端高频轮询页面
- 任务状态查询接口
- 平台级观测字段现状
- 适合作为容量基线的接口候选

## 执行摘要

当前平台已经具备多条“提交任务 → 前端轮询状态”的完整链路，但这套模式存在三个明显问题：

1. **前端轮询分散在多个页面，频率与错误策略不一致**
2. **多个状态接口在每次轮询时会直接触发外部厂商状态查询和本地持久化**
3. **平台级 `request_id / deployment_version` 之前缺少统一注入，只在部分业务对象里零散保留 `task_id / request_id`**

本轮已先落地最小观测补丁：

- 所有 HTTP 响应统一暴露 `X-Request-ID`
- 所有 HTTP 响应统一暴露 `X-Deployment-Version`
- 日志上下文支持记录请求 ID

## 前端轮询现状

### 1. 图片工作室

- 页面：`frontend/src/pages/Studio/StudioPage.tsx`
- 查询接口：`GET /api/studio/{task_id}`
- 节奏：
  - 首次延迟约 `2s`
  - 后续每 `3s` 轮询一次
- 风险：
  - 页面内自行管理轮询与提示
  - 出错时直接停止当前轮询，没有统一重试/退避策略

### 2. 视频工作室

- 页面：`frontend/src/pages/VideoStudio/VideoStudioPage.tsx`
- 查询接口：`GET /api/video-studio/{task_id}/status`
- 节奏：
  - 立即开始
  - 后续每 `5s` 轮询一次
- 风险：
  - 轮询逻辑重复
  - 出错后会停止轮询

### 3. 音频工作室

- 页面：`frontend/src/pages/AudioStudio/AudioStudioPage.tsx`
- 查询接口：`GET /api/audio-studio/{task_id}`
- 节奏：
  - 首次延迟约 `2s`
  - 后续每 `3s` 轮询一次
- 特点：
  - 出错时没有立即停止，策略比图片/视频更稳

### 4. 旧视频页面

- 页面：`frontend/src/pages/Videos/VideosPage.tsx`
- 查询接口：`GET /api/videos/status/{task_id}`
- 节奏：
  - 立即开始
  - 正常每 `5s`
  - 出错后每 `10s`
- 风险：
  - 轮询逻辑仍是页面内自管
  - 与新视频工作室形成并行模式

### 5. 图片测评运行页

- 页面：`frontend/src/pages/ImageBenchmark/ImageBenchmarkPage.tsx`
- 查询接口：`GET /api/image-benchmark/runs/{run_id}`
- 节奏：
  - 运行中每 `3s`
- 特点：
  - 当前 run 查询是纯读，较适合作为基线观测对象

## 状态接口现状

### 1. 图片工作室状态接口

- 路由：`backend/app/routers/studio.py`
- 接口：`GET /api/studio/{task_id}`
- 当前行为：
  - 主要读取本地任务文件
  - 如缺失快照会回填 `provider_payload_snapshot`
- 评价：
  - 相对偏“本地状态读”
  - 仍包含一定回填副作用

### 2. 视频工作室状态接口

- 路由：`backend/app/routers/video_studio.py`
- 接口：`GET /api/video-studio/{task_id}/status`
- 当前行为：
  - 对 `processing` 任务会遍历 `task.task_ids`
  - 每次轮询都调用 adapter 到厂商侧查询状态
  - 可能更新 `provider_result_meta`
  - 成功时还可能抽取缩略图并持久化
- 评价：
  - **当前最不适合作为高频轮询长期形态**
  - 每次前端轮询都会放大为“平台读 + 外部状态查询 + 本地写入”

### 3. 旧视频状态接口

- 路由：`backend/app/routers/videos.py`
- 接口：`GET /api/videos/status/{task_id}`
- 当前行为：
  - 每次查询直接调用 `ImageToVideoService.get_task_status`
  - 成功后更新本地视频记录与项目脚本
- 评价：
  - 同样存在“轮询即副作用”的问题

### 4. 音频工作室状态接口

- 路由：`backend/app/routers/audio_studio.py`
- 接口：`GET /api/audio-studio/{task_id}`
- 当前行为：
  - 纯读取本地任务
- 评价：
  - 是当前最适合作为“状态查询基线”的任务页接口之一

### 5. 图片测评运行状态接口

- 路由：`backend/app/routers/image_benchmark.py`
- 接口：`GET /api/image-benchmark/runs/{run_id}`
- 当前行为：
  - 纯读取 run 记录
- 评价：
  - 很适合作为 Step 00 / Step 05 前后的对比样本

## 观测字段现状

### 已有能力

- `/api/health` 已返回：
  - `git_commit`
  - `run_mode`
  - `serve_frontend`
  - `started_at`
- 多个业务对象已保留：
  - `task_id`
  - `last_task_id`
  - `request_id`
  - `request_ids`
  - `provider_result_meta`
- `run.sh` 启动时已注入：
  - `MIEMIE_RUNTIME_GIT_COMMIT`
  - `MIEMIE_RUNTIME_RUN_MODE`
  - `MIEMIE_RUNTIME_STARTED_AT`

### 本轮补齐

- 所有 HTTP 响应统一输出：
  - `X-Request-ID`
  - `X-Deployment-Version`
- 日志上下文现在可附带请求 ID

### 仍然缺失

- 统一的 `request_id` 贯穿到所有结构化业务日志
- 统一的 `provider_request_id` 命名与采集口径
- 统一的 `worker_id`（当前尚未进入独立 Worker 阶段）
- 平台级 `loadtest_run_id` 注入与透传

## 基线压测接口建议

### S1：纯读流量优先候选

- `GET /api/health`
- `GET /api/projects`
- `GET /api/models`
- `GET /api/audio-studio/{task_id}`
- `GET /api/image-benchmark/runs/{run_id}`

原因：

- 更接近平台自身读能力
- 不容易被外部供应商耗时污染
- 便于建立第一版 API 延迟基线

### S2：读写混合优先候选

- 登录
- 项目创建 / 列表
- 工作室任务创建但不触发真实供应商重压
- 任务详情读取

### S3：任务提交 + 状态观察候选

- 图片工作室任务提交
- 图片工作室状态查询
- 图片测评运行查询

说明：

- 视频工作室与旧视频状态接口可以纳入“现状评估”，但不宜作为平台纯承载基线的主要样本，因为其当前轮询会直接打到外部厂商状态查询。

## 风险排序

### P1

1. **视频工作室状态查询放大**
2. **旧视频页与新工作室双轨轮询并存**
3. **前端轮询错误策略不一致**

### P2

1. **图片工作室状态查询仍含回填副作用**
2. **请求 ID 虽已补头，但还没沉入所有结构化业务日志**
3. **缺少统一轮询 hook / 状态订阅抽象**

## 下一步建议

1. **先不要急着上 SSE**
   - 先统一“状态查询语义”和“状态真相来源”
   - 否则只是把分散轮询换成分散 SSE

2. **先做统一状态读取抽象**
   - 前端抽一个统一的 polling / task-status hook
   - 后端明确哪些状态接口允许副作用，哪些必须纯读

3. **优先收敛视频链路**
   - 旧视频页应逐步让位于视频工作室主路径
   - 视频工作室状态查询后续应尽量转为“读平台任务状态”，而不是每次轮询直打厂商

4. **在 Step 01 前后复跑同一组场景**
   - 先以脚本生产模式建立基线
   - Compose 落地后复跑同样的 S1 / S3 场景

## 2026-04-23 至 2026-04-24 验证记录

- `./run.sh test`：通过，`130 passed in 39.56s`
- `backend/.venv/bin/pytest backend/tests/test_fixes.py backend/tests/test_video_studio_capabilities.py backend/tests/test_video_studio_vace.py -q`：通过，`65 passed`
- `cd frontend && npm run typecheck`：通过
- `cd frontend && npm run lint`：通过
- `cd frontend && npm run build`：通过，未再出现单 chunk 超过 `500 kB` 的构建警告
- `cd frontend && npm run test:e2e:helper`：通过，`2 passed`
- `cd frontend && npm run test:e2e`：通过，`4 passed`
- `docker compose config`：通过
- `docker build -t miemie-studio:step01-check .`：当前阻塞，Docker daemon 未运行

### 验证中发现并修复

- `./run.sh test` 原先会在激活项目 venv 前固定 `python3`，导致无项目根 `venv` 时落到系统 Python 并缺少 `starlette` 等依赖。
- 本轮已改为先确认项目后端依赖，再使用 `venv/bin/python` 执行 pytest，并新增 `backend/tests/test_run_script.py` 作为回归保护。
- Playwright smoke 现已支持在 macOS 下自动发现 `~/Library/Caches/ms-playwright` 中最新的 Chromium；仍保留 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 显式覆盖能力。
- 已补齐 Step 00 的压测资产骨架（k6 S1/S3）与验证归档模板；当前仍缺真实 Linux staging 执行结果。
