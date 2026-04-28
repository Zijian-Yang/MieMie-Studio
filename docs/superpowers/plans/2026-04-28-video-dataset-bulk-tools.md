# 视频数据集批量能力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让视频数据集页对标图片数据集的批量编辑工作流，并允许缺首帧样例暂存。

**Architecture:** 后端保留现有 video benchmark dataset API，但将首帧校验从保存阶段移动到 preview/run 阶段。前端在视频数据集页增加本地 draft 批量操作，所有批量结果继续通过现有 dataset update 保存。

**Tech Stack:** FastAPI, Pydantic, JSON storage, React 18, TypeScript, Ant Design.

---

### Task 1: 后端缺首帧暂存与运行阻断

**Files:**
- Modify: `backend/app/routers/video_benchmark.py`
- Test: `backend/tests/test_video_benchmark.py`

- [x] 将“缺首帧保存失败”测试改为“可保存并返回 blocking issue”。
- [x] 新增 run suite 缺首帧阻断测试。
- [x] 新增 preview-cell 缺首帧阻断测试。
- [x] 实现 `_analyze_dataset()` 并接入 dataset response、run suite、preview-cell。
- [x] 运行 `venv/bin/pytest backend/tests/test_video_benchmark.py -q`。

### Task 2: 前端视频数据集批量工具

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/VideoBenchmarkDatasets/VideoBenchmarkDatasetsPage.tsx`

- [x] 新增 `VideoBenchmarkDatasetIssue` 类型。
- [x] 新增行多选、选中排序、删除选中。
- [x] 新增批量首帧建样例、批量填充首帧。
- [x] 新增批量编辑样例名、Prompt、负向提示词、标签、首帧、音频、样例时长。
- [x] 对缺首帧样例展示 warning，并允许保存 draft。
- [x] 运行 `cd frontend && npm run typecheck`。

### Task 3: 文档与最终验证

**Files:**
- Modify: `docs/specs/2026-04-video-benchmark-i2v.md`
- Modify: `docs/API.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/CHANGELOG.md`

- [x] 更新视频测评 spec、API、前端文档和 changelog。
- [x] 运行 `venv/bin/pytest backend/tests/test_video_benchmark.py backend/tests/test_video_studio_capabilities.py -q`。
- [x] 运行 `cd frontend && npm run typecheck`。
- [x] 运行 `git diff --check`。
