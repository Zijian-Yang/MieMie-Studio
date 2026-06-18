# HappyHorse 1.5 Video Studio Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HappyHorse 1.5 T2V/I2V/R2V models to Video Studio alongside existing HappyHorse 1.0 models.

**Architecture:** Reuse the existing `provider=happyhorse` adapter, DashScope `video-synthesis` submit/poll flow, OSS persistence, capability schema rendering, and developer-mode payload preview. Keep 1.5 as additional model IDs instead of replacing or aliasing 1.0.

**Tech Stack:** FastAPI, Pydantic, pytest, React/Vite schema-driven Video Studio UI, Ant Design.

---

### Task 1: Backend Regression Tests

**Files:**
- Modify: `backend/tests/test_video_studio_capabilities.py`

- [x] Add tests for 1.5 model exposure, default model stability, provider inference, task-kind mismatch rejection, payload model-id passthrough, 21:9/9:21 ratios, BMP image format, and absence of 1.5 video edit.
- [x] Run the focused backend test file and verify the new tests fail for missing 1.5 support. The pytest process was killed with exit 137 before assertion output, so the red phase is recorded as environment-blocked rather than assertion-confirmed.

### Task 2: Backend Capability And Adapter Implementation

**Files:**
- Modify: `backend/app/services/video_capabilities.py`
- Modify: `backend/app/services/video_adapters.py`

- [x] Add HappyHorse 1.5 T2V/I2V/R2V capability entries by sharing the existing HappyHorse profile builder.
- [x] Update HappyHorse shared constraints for `21:9`, `9:21`, and `BMP`.
- [x] Add a HappyHorse model/task-kind allow-list so 1.0 video edit remains the only edit model and unsupported task/model combinations are rejected.
- [x] Re-run focused backend tests until they pass.

### Task 3: Documentation Updates

**Files:**
- Modify: `docs/specs/2026-04-happyhorse-video-studio-integration.md`
- Modify: `docs/README.md`
- Modify: `docs/BACKEND.md`
- Modify: `docs/FRONTEND.md`
- Modify: `docs/CHANGELOG.md`

- [x] Update the platform spec with 1.5 model IDs, no 1.5 edit support, built-in audio behavior, and the revised HappyHorse constraints.
- [x] Update developer docs and changelog to keep the documented source of truth aligned with implementation.

### Task 4: Verification

**Files:**
- Inspect only as needed.

- [x] Run `venv/bin/pytest backend/tests/test_video_studio_capabilities.py backend/tests/test_provider_key_and_manifest.py -q`.
- [x] Run `cd frontend && npm run test:video-capability-limits`.
- [x] Run `cd frontend && npm run test:video-prompt-length-policy`.
- [x] Run `cd frontend && npm run test:video-reference-tokens`.
- [x] Run `cd frontend && npm run typecheck`.
- [x] Run `git diff --check`.
- [x] Record any skipped real DashScope smoke with the reason: skipped in this implementation pass because HappyHorse 1.5 requires whitelist access and uses real provider quota; run a 720P single-task T2V/I2V/R2V smoke when an approved key/profile is available.
