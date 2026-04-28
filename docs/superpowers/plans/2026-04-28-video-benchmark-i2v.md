# 视频测评首帧生视频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在图片测评下方新增独立的视频数据集与视频测评模块，v1 支持首帧生视频横向测评。

**Architecture:** 后端新增独立 video_benchmark 模型、存储、router 与 runtime，runtime 复用视频工作室 capability 和 adapter。前端新增两个页面与 API 类型，复用图片测评的矩阵和详情思路，但输出以视频播放和 URL 报告为核心。

**Tech Stack:** FastAPI, Pydantic, JSON storage, React 18, TypeScript, Ant Design, Vite.

---

### Task 1: 后端测评闭环

**Files:**
- Create: `backend/app/models/video_benchmark.py`
- Create: `backend/app/services/video_benchmark_runtime.py`
- Create: `backend/app/routers/video_benchmark.py`
- Modify: `backend/app/services/storage.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/routers/projects.py`
- Test: `backend/tests/test_video_benchmark.py`

- [x] 写失败测试覆盖 capabilities、数据集 duration、preview、mock run、unsupported、retry、报告导出。
- [x] 新增独立数据模型与存储目录。
- [x] 新增 runtime，复用视频工作室 capability 和 adapter。
- [x] 新增 `/api/video-benchmark/*` router。
- [x] 项目删除时清理视频测评数据。

### Task 2: 前端页面与 API

**Files:**
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/pages/VideoBenchmarkDatasets/VideoBenchmarkDatasetsPage.tsx`
- Create: `frontend/src/pages/VideoBenchmark/VideoBenchmarkPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout/MainLayout.tsx`

- [x] 新增视频测评 TypeScript 类型和 API client。
- [x] 新增视频数据集页，支持首帧、可选音频、可选时长、JSON 导入导出和批量 Prompt。
- [x] 新增视频测评页，支持模型选择、参数覆盖、payload preview、运行矩阵、详情和报告导出。
- [x] 在侧边栏和路由中新增 `视频数据集` / `视频测评`。

### Task 3: 文档与验证

**Files:**
- Create: `docs/specs/2026-04-video-benchmark-i2v.md`
- Modify: `docs/API.md`
- Modify: `docs/BACKEND.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/MODELS.md`
- Modify: `docs/CHANGELOG.md`

- [x] 补平台 spec 和实现计划文件。
- [x] 更新 API、后端、前端、模型文档和 changelog。
- [x] 运行 `venv/bin/pytest backend/tests/test_video_benchmark.py backend/tests/test_video_studio_capabilities.py -q`。
- [x] 运行 `cd frontend && npm run typecheck`。
- [x] 运行 `git diff --check`。
