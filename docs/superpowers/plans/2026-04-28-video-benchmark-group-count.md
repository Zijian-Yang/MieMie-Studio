# 视频测评生成数量补齐计划

**Goal:** 让视频测评中选中的首帧生视频模型可以配置生成数量，并在一个 case × model 单元下保存和展示多条输出。

**Context:** 视频工作室已有 `group_count` 概念，但视频测评 v1 初始实现把每个 case × model 固定为 1 条视频，导致模型 override 表单无法设置生成数量。

## Tasks

- [x] 后端 capabilities 为每个支持 `image_to_video` 的视频测评模型注入测评层 `group_count` 参数，默认 1，范围 1-5。
- [x] preview 与 run 保留 `effective_params.group_count` 和 `canonical_request.normalized_params.group_count`，但构造 provider request 时移除该参数，避免下发给厂商。
- [x] run 按 `group_count` 提交多次任务，累计 `task_ids`、`request_ids`、`provider_result_meta.tasks` 和多条 `output_videos`。
- [x] 前端视频测评模型 override 表单自动显示 `生成数量`，结果矩阵与单元详情展示多条输出视频。
- [x] 更新 spec、API、BACKEND、FRONTEND、MODELS 与 CHANGELOG。

## Verification

- [x] `venv/bin/pytest backend/tests/test_video_benchmark.py backend/tests/test_video_studio_capabilities.py -q`
- [x] `cd frontend && npm run typecheck`
- [x] `git diff --check`
