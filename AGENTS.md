# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

MieMie-Studio is an AI-powered comic/short-drama video generation platform built on Alibaba Cloud's DashScope (Tongyi Wanxiang) API. It supports a full workflow from script creation to video generation.

**Language**: The codebase and UI are in Chinese. Commit messages use Chinese with conventional commit prefixes (feat/fix/docs/refactor).

## Commands

### Quick Start
```bash
./run.sh start      # Start both frontend and backend (auto-installs deps on first run)
./run.sh stop       # Stop all services
./run.sh restart    # Restart all services
./run.sh status     # Check service status
./run.sh test       # Run backend pytest suite
./run.sh port       # Show/change service ports
```

### Backend (FastAPI)
```bash
source venv/bin/activate
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Dev server on port 3000
npm run build        # Production build to frontend/dist/
npm run typecheck    # TypeScript type checking (tsc --noEmit)
npm run lint         # ESLint
```

### Python Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Tech Stack
- **Backend**: Python FastAPI + Pydantic + DashScope SDK + Aliyun OSS + bcrypt + slowapi
- **Frontend**: React 18 + TypeScript + Ant Design 5.x (dark theme) + Zustand + Vite
- **Storage**: JSON files per user in `backend/data/users/{user_id}/`, with optional Aliyun OSS for generated assets
- **Auth**: Token-based via pure ASGI middleware (`backend/app/middleware/auth.py`), passwords bcrypt-hashed, sessions stored in JSON
- **Testing**: pytest with TestClient (`backend/tests/`), covering auth, CORS, middleware, storage, image benchmark, image/video studio capabilities, and rate limiting

### Request Flow
```
Browser → Vite proxy (port 3000) → /api/* → FastAPI (port 8000) → DashScope API
                                                    ↓
                                              OSS storage ← generated assets
```

In production mode (`MIEMIE_SERVE_FRONTEND=true`), FastAPI serves the built frontend from `frontend/dist/` as an SPA.

### Backend Structure (`backend/app/`)

- **`main.py`** — FastAPI app entry, registers all routers under `/api/*`, sets up CORS (env-driven), pure ASGI auth middleware, rate limiting (slowapi), and static file serving.
- **`config.py`** — Central configuration. Contains all model definitions (IMAGE_MODELS, VIDEO_MODELS, TEXT_TO_VIDEO_MODELS, etc.) with detailed parameter constraints. `ConfigManagerProxy` auto-routes to per-user config via `contextvars`. Uses atomic file writes.
- **`routers/`** — One router per domain: `scripts`, `characters`, `scenes`, `props`, `frames`, `videos`, `styles`, `gallery`, `studio`, `audio`, `video_library`, `text_library`, `video_studio`, `audio_studio`, `image_benchmark`, `models`, `auth`, `settings`.
- **`services/dashscope/`** — DashScope API wrappers: `text_to_image`, `image_to_image`, `image_to_video`, `text_to_video`, `reference_to_video`, `keyframe_to_video`, `llm`, `digital_human`.
- **`services/storage.py`** — JSON file storage with file locking (`fcntl`), atomic writes, and per-user data isolation via `contextvars`.
- **`services/user_service.py`** — User registration/login with bcrypt password hashing, progressive migration from plaintext, thread-safe singleton.
- **`services/oss.py`** — Aliyun OSS upload/download. OSS uploads must happen in the service layer, never in routers.
- **`services/image_benchmark_runtime.py`** — 图片测评运行时复用层。负责数据集导出、单元执行、限流指数退避自动重试和 Markdown 报告渲染。
- **`middleware/auth.py`** — Pure ASGI auth middleware (not BaseHTTPMiddleware). Sets contextvars for user isolation, clears in finally block.
- **`models/`** — Pydantic data models for all entities (project, character, scene, prop, frame, video, style, gallery, media, audio_studio, image_benchmark).
- **`models_registry/`** — Pluggable model registration system. `ModelRegistry` is a singleton. To add a new AI model: create a file under `models_registry/{image,video,llm}/`, inherit `BaseModelService`, and call `registry.register()`.

### Frontend Structure (`frontend/src/`)

- **`pages/`** — One folder per page, matching the workflow steps: Script, Characters, Scenes, Props, Frames, Videos, plus Studio, Gallery, Settings, etc.
- **`stores/`** — Zustand stores: `projectStore`, `scriptStore`, `generationStore`, `authStore`, `modelRegistryStore`, `themeStore`.
- **`services/api.ts`** — Axios-based API client. Auto-attaches auth token from localStorage. 401 responses redirect to login.
- **`components/ModelConfig/`** — Reusable model selection and dynamic parameter forms (`DynamicModelForm`, `ModelSelector`, `SizeSelector`).
- **`hooks/useModelRegistry.ts`** — Hook to fetch and cache model registry data from the backend.

### Key Design Patterns

- **Multi-user isolation**: Both `StorageService` and `ConfigManager` use `contextvars` to route to per-user data directories. The auth middleware sets the user context per request.
- **Model registry**: Decoupled model definitions from service implementations. Models self-register on import. Frontend fetches the registry from `/api/models` and dynamically renders parameter forms.
- **OSS integration**: Optional. When enabled, services download DashScope outputs and re-upload to user's OSS bucket. The `project_id` param is always passed through for path organization.
- **Async generation**: Most DashScope calls are async (submit task → poll for result). The backend handles polling internally.
- **Image benchmark snapshots**: 图片测评运行会冻结数据集快照与模型配置快照，便于后续复现；失败单元支持自动重试与一键重试失败项。

## Important Conventions

- **OSS uploads in service layer only** — routers must not duplicate upload logic.
- **All generation services must accept `project_id`** — used for organizing files in storage/OSS.
- **No hardcoded colors in frontend** — always use `theme.useToken()` from Ant Design. Card components should not override background/border.
- **Model selectors display format**: `"模型名称 模型ID"`.
- **Size selectors include orientation**: e.g., `"1920×1080 横向"`.
- **Use `Form.useWatch`** for reactive form field dependencies, not `form.getFieldValue()`.
- **Atomic file writes** — all JSON writes must use temp→fsync→os.replace pattern. Never write directly to the target file.
- **slowapi parameter naming** — in rate-limited endpoints, the `starlette.requests.Request` param must be named `request`. Pydantic body params should be named `data` to avoid conflicts.
- **Passwords are bcrypt-hashed** — never store plaintext. Use `_hash_password()` / `_verify_password()` from UserService.
- **Pure ASGI middleware** — do not use `BaseHTTPMiddleware` for anything that touches contextvars.

## Spec-Driven Delivery

### Source of Truth Order

When multiple documents mention the same topic, use this priority:

1. `AGENTS.md`
2. `docs/README.md`
3. The active spec under `docs/specs/`
4. The relevant ADR under `docs/adr/`
5. The relevant checklist/playbook under `docs/checklists/` or `docs/playbooks/`
6. Legacy descriptive docs such as `docs/BACKEND.md`, `docs/FRONTEND.md`, `docs/DASHSCOPE.md`

Vendor mirror documents under `docs/阿里云模型api文档/` are **raw reference material**, not the platform's source of truth.

### Required Change Package

For any non-trivial feature, refactor, or model integration, deliver all of:

- A spec or spec update
- Code changes
- Verification evidence (tests/typecheck/build/manual steps as applicable)
- Documentation updates

For architecture-affecting changes, also add or update an ADR.

### Mandatory Review Questions

Before you finish a change, verify:

- Is there only one effective source of truth for the changed behavior?
- Does the frontend render from schema/capabilities where possible instead of hardcoded model branches?
- Are error states, retries, and developer-mode observability covered?
- Did you update the relevant spec/ADR/checklist/docs entrypoints?
- Did you avoid introducing new hardcoded theme colors?

## Testing

```bash
./run.sh test                              # Run all tests
cd backend && python -m pytest tests/ -v   # Run directly
```

Tests use `starlette.testclient.TestClient` with isolated temp directories per test. The `conftest.py` resets the UserService singleton and slowapi rate limiters between tests.

## Sensitive Files (never commit)

- `backend/data/config.json` — contains DashScope API keys, OSS credentials
- `backend/data/users.json`, `backend/data/sessions.json` — user credentials and sessions
- `backend/data/users/` — per-user private data
