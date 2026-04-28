# 测评运行结果即时展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 图片测评与视频测评运行中持续落盘已完成结果，让前端轮询即可边看边等。

**Architecture:** run 创建时写入完整 pending cell 矩阵；后台执行时用 per-run lock 按 `case_id + model_id` 合并写入 running/终态 cell。视频测评在每条视频完成 OSS 持久化后通过 progress callback 立即保存部分 `output_videos`。

**Tech Stack:** FastAPI, Pydantic, JSON storage, asyncio, React, TypeScript, Ant Design.

---

### Task 1: 后端增量持久化

**Files:**
- Modify: `backend/app/routers/image_benchmark.py`
- Modify: `backend/app/routers/video_benchmark.py`
- Modify: `backend/app/services/video_benchmark_runtime.py`

- [x] 图片测评 run 创建时写入完整 `pending` cell 矩阵。
- [x] 视频测评 run 创建时写入完整 `pending` cell 矩阵。
- [x] 图片/视频后台执行时先保存 `running` cell，再保存终态 cell。
- [x] 为图片/视频测评增加 per-run `asyncio.Lock`，增量保存时重新读取 run 并合并 cell。
- [x] 视频测评 `group_count` 每条输出完成 OSS 持久化后立即保存部分 `output_videos`。

### Task 2: 前端运行中展示

**Files:**
- Modify: `frontend/src/pages/ImageBenchmark/ImageBenchmarkPage.tsx`
- Modify: `frontend/src/pages/VideoBenchmark/VideoBenchmarkPage.tsx`

- [x] 图片测评与视频测评统计展示待运行、生成中、成功、失败/未支持。
- [x] 视频测评轮询频率改为约 3 秒。
- [x] 视频测评 running cell 展示已完成的部分输出视频。

### Task 3: 测试与文档

**Files:**
- Modify: `backend/tests/test_image_benchmark.py`
- Modify: `backend/tests/test_video_benchmark.py`
- Modify: `docs/API.md`
- Modify: `docs/BACKEND.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/MODELS.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/specs/2026-04-video-benchmark-i2v.md`

- [x] 测试 run 创建后立即返回 pending 矩阵。
- [x] 测试图片 cell 完成后在 run 仍 running 时已落盘。
- [x] 测试视频 `group_count` 单条输出完成后在 run 仍 running 时已落盘。
- [x] 测试后续视频失败时保留已完成输出。
- [x] 更新 API、后端、前端、模型文档、spec 与 changelog。

### Verification

- [x] `venv/bin/pytest backend/tests/test_image_benchmark.py backend/tests/test_video_benchmark.py backend/tests/test_video_studio_capabilities.py -q`
- [x] `cd frontend && npm run typecheck`
- [x] `git diff --check`
