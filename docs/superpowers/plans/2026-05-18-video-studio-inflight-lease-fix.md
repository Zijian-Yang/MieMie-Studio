# Video Studio Inflight Lease Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复视频工作室异步提交期间的 inflight lease 泄漏、删除/重生成竞态，以及 `processing` 但无厂商 ID 的陈旧任务无法自愈问题。

**Architecture:** 给 `VideoStudioTask` 增加提交生命周期字段，将后台提交 attempt 显式持久化。视频工作室 router 负责本地后台任务、厂商 task_id、模型 inflight lease 的映射清理，并在保存提交结果前校验任务仍存在且 attempt 未过期。读取/list/status 入口统一对陈旧无 ID 提交任务做失败化 reconciliation。

**Tech Stack:** FastAPI router、Pydantic model、pytest/TestClient、现有 JSON storage 与模型限流器。

---

## Tasks

- [x] 在 `backend/tests/test_video_studio_capabilities.py` 新增回归测试：删除任务释放 lease、删除后后台提交不复活任务、重生成释放旧 lease 并生成新 attempt、陈旧无 ID 任务 status 自愈、提交取消释放已获取 lease。
- [x] 运行新增测试，确认当前实现红灯。
- [x] 在 `backend/app/models/media.py` 为 `VideoStudioTask` 增加 `submit_state`、`submit_started_at`、`submit_attempt_id`，旧 JSON 默认兼容。
- [x] 在 `backend/app/routers/video_studio.py` 增加后台提交任务注册、attempt 校验、按本地任务释放 lease、删除/批量删除/重生成清理、陈旧提交失败化逻辑。
- [x] 更新 `docs/ISSUES.md` 的问题状态与修复进展。
- [x] 运行指定 pytest：`tests/test_video_studio_capabilities.py`、`tests/test_model_rate_limits.py`、`tests/test_video_studio_vace.py`；时间允许则运行 `./run.sh test`。

## Notes

- 本地实现不连接生产、不修改线上任务数据。
- 删除或重生成后释放本地 lease 是有意行为：应用已经放弃旧厂商任务的轮询，继续占用本地并发槽只会造成永久卡死。
- 当前工作区已有排查文档未提交改动，执行时保留并避免回滚。

## Verification Log

- 2026-05-18：新增 5 个回归测试后，使用 `venv/bin/python -m pytest ...` 定向运行，确认 5 项均失败，失败点分别覆盖未释放 lease、删除后复活任务、重生成未释放旧 lease、陈旧无 ID 未失败化、`CancelledError` 未释放 lease。
- 2026-05-18：实现后运行 `venv/bin/python -m pytest backend/tests/test_video_studio_capabilities.py -v`，63 项通过。
- 2026-05-18：运行 `venv/bin/python -m pytest backend/tests/test_model_rate_limits.py backend/tests/test_video_studio_vace.py -v`，12 项通过。
- 2026-05-18：运行 `./run.sh test`，225 项通过。
