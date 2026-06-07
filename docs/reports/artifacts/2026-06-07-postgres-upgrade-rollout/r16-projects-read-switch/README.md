# R16 Projects Read Switch + JSON Fallback

## Summary

2026-06-07 本地完成 `projects` PostgreSQL read-switch 与 JSON fallback。

- 默认运行态仍为 `file-only`，不读取 PostgreSQL。
- 只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_READ_DOMAINS=projects` 或 `MIEMIE_DATABASE_READ_MODE=postgres` 时，项目详情和项目列表才优先读取 PostgreSQL。
- `MIEMIE_DATABASE_JSON_FALLBACK_READ=true` 时，PostgreSQL miss、空列表或异常会回退现有 JSON 读取路径并记录 warning。
- 关闭 fallback 时 PostgreSQL 读异常会向上抛出，便于严格灰度门禁。
- 未修改公开 API 响应结构、路由、前端行为或服务器开关。

## Changed Files

- `backend/app/repositories/project_runtime.py`
- `backend/app/services/storage.py`
- `backend/tests/test_project_read_switch.py`

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_project_read_switch.py -q
4 passed

backend/.venv/bin/pytest backend/tests/test_project_read_switch.py backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_studio_task_read_switch.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_storage_service.py -q
26 passed

backend/.venv/bin/python -m py_compile backend/app/repositories/project_runtime.py backend/app/services/storage.py
passed

backend/.venv/bin/pytest backend/tests/test_project_read_switch.py backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_primary_write.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_migration.py backend/tests/test_database_health.py -q
48 passed

docker compose config
passed

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
297 passed
```

## Runtime State

- Local code: `projects` read-switch implemented.
- Default config: still JSON/file-only.
- Staging/live: not enabled in this slice.
- Next local slice: `projects` PostgreSQL primary-write + optional JSON archive mirror.
- Next server slice: resume R7/R1-R2 server health, live migration, backfill/reconcile, then dual-write/read-switch/primary-write gates.
