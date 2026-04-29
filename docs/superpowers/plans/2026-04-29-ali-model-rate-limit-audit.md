# 阿里生图/生视频同步/异步限流校准 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按阿里模型限流文档区分任务下发频率与同步/异步处理中并发，避免保守并发影响吞吐，也避免误把“同步接口无限制”理解成不需要提交频率限制。

**Architecture:** 新增 `model_rate_limits.py` 作为唯一限流映射源，capabilities/schema 只消费该映射；工作室与测评运行时通过统一 helper 获取 submit token 与 in-flight lease。

---

### Task 1: 限流定义与能力 schema

**Files:**
- Add: `backend/app/services/model_rate_limits.py`
- Modify: `backend/app/models_registry/base.py`
- Modify: `backend/app/routers/models.py`
- Modify: `backend/app/routers/settings.py`
- Modify: `backend/app/services/video_capabilities.py`

- [x] 定义 `api_mode`、`submit_rate_limit`、`max_inflight`、`inflight_scope`、`shared_pool_id`。
- [x] 录入 Qwen/Wan/HappyHorse/Kling/Vidu 已接入模型限流。
- [x] Qwen 图片按平台同步接口处理：保留提交频率，`max_concurrent=null`。
- [x] Kling/Vidu 使用共享 pool。
- [x] capabilities 与 settings 可用模型返回限流元数据。

### Task 2: 工作室与测评调度接入

**Files:**
- Modify: `backend/app/routers/studio.py`
- Modify: `backend/app/routers/video_studio.py`
- Modify: `backend/app/routers/image_benchmark.py`
- Modify: `backend/app/routers/video_benchmark.py`
- Modify: `backend/app/services/video_benchmark_runtime.py`

- [x] 图片工作室真实提交前执行 `wait_for_model_submit()`。
- [x] 异步图片任务提交到终态期间占用模型 in-flight lease。
- [x] 视频工作室每个 API task 从提交到状态终态期间占用 lease。
- [x] 视频测评每条输出任务独立占用 lease，并在单条终态后释放。
- [x] 图片测评移除固定全局 4 并发，改由底层真实提交路径限流。
- [x] 有限并发模型的 `group_count` 超限返回 400；同步无限并发模型不设并发上限。

### Task 3: 前端与文档

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/Studio/StudioPage.tsx`
- Modify: `frontend/src/pages/VideoStudio/CapabilityCreateModal.tsx`
- Modify: `docs/API.md`
- Modify: `docs/BACKEND.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/MODELS.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/specs/2026-04-video-benchmark-i2v.md`

- [x] 前端类型支持 `api_mode`、`submit_rate_limit`、`max_concurrent=null`、共享池字段。
- [x] 图片/视频工作室生成组数上限从 capabilities 读取。
- [x] 视频测评 `group_count` 上限按模型 `max_concurrent` 注入，不固定为 5。
- [x] 文档说明提交频率与处理中并发是两个独立限制。

### Verification

- [x] `venv/bin/pytest backend/tests/test_model_rate_limits.py backend/tests/test_studio_capabilities.py backend/tests/test_image_benchmark.py backend/tests/test_video_studio_capabilities.py backend/tests/test_video_benchmark.py -q`
- [x] `cd frontend && npm run typecheck`
- [x] `git diff --check -- <本次变更文件>`
