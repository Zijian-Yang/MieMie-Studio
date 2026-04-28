# 视频测评移除 Baseline Params JSON 计划

**Goal:** 视频测评配置只保留参与测评模型的独立参数设置，不再让用户填写全局 `Baseline Params JSON`。

**Reason:** 模型卡片已经提供按模型独立的参数表单，Baseline JSON 会形成第二套参数入口，容易让用户误解参数优先级。

## Tasks

- [x] 移除视频测评页的 `Baseline Params JSON` 文本框、state 和 JSON 解析逻辑。
- [x] 创建、保存、运行和 payload preview 时统一传 `baseline_params: {}`。
- [x] 保留后端 `baseline_params` 字段，作为历史数据和外部 API 兼容层。
- [x] 更新 spec、API、BACKEND、FRONTEND、MODELS 与 CHANGELOG。

## Verification

- [x] `cd frontend && npm run typecheck`
- [x] `venv/bin/pytest backend/tests/test_video_benchmark.py backend/tests/test_video_studio_capabilities.py -q`
- [x] `git diff --check`
