# HappyHorse Hidden Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HappyHorse task-panel switches for prompt rewrite and DashScope data-inspection disabling.

**Architecture:** Keep the frontend schema-driven by exposing two HappyHorse-only advanced boolean parameters from video capabilities. Map those normalized params inside `HappyHorseVideoAdapter`: `prompt_extend=false` becomes a provider payload parameter, while `disable_data_inspection=true` becomes an extra DashScope header that is visible in developer preview and submit metadata without exposing credentials.

**Tech Stack:** Python FastAPI, pytest, React + TypeScript + Ant Design, Vite scripts.

---

## Task 1: Backend Contract Tests

**Files:**
- Modify: `backend/tests/test_video_studio_capabilities.py`

- [x] Add capability assertions for HappyHorse `prompt_extend` and `disable_data_inspection` on all four task profiles.
- [x] Add provider payload assertions that `prompt_extend=false` is sent and `prompt_extend=true` is omitted.
- [x] Add provider header assertions for preview and submit when `disable_data_inspection=true`.
- [x] Run targeted pytest and confirm the new tests fail before implementation.

## Task 2: Backend Implementation

**Files:**
- Modify: `backend/app/services/video_capabilities.py`
- Modify: `backend/app/services/video_adapters.py`
- Modify: `backend/app/routers/video_studio.py`

- [x] Add HappyHorse advanced boolean params to the capability schema.
- [x] Add safe provider-header support to generic DashScope video submission.
- [x] Add default `build_provider_headers()` to adapters and HappyHorse-specific data-inspection header mapping.
- [x] Add HappyHorse prompt rewrite payload mapping: only send `prompt_extend=false`.
- [x] Include safe provider headers in preview response and submit success/error metadata.
- [x] Run targeted pytest and confirm backend tests pass.

## Task 3: Frontend Developer Preview

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/VideoStudio/CapabilityCreateModal.tsx`

- [x] Add `provider_headers` to video preview payload response types.
- [x] Show provider headers in Video Studio developer mode.
- [x] Run TypeScript verification.

## Task 4: Docs and Changelog

**Files:**
- Modify: `docs/specs/2026-04-happyhorse-video-studio-integration.md`
- Modify: `docs/BACKEND.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-05-13-happyhorse-hidden-controls.md`

- [x] Document HappyHorse hidden prompt rewrite and data-inspection controls.
- [x] Document preview/provider metadata behavior.
- [x] Record the change in the changelog.
- [x] Mark this plan complete.

## Verification

- [x] `venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_video_benchmark.py -q`
- [x] `cd frontend && npm run test:video-capability-limits`
- [x] `cd frontend && npm run typecheck`
