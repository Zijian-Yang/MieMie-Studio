# R17 Projects PostgreSQL Primary Write + JSON Archive Mirror

## Summary

2026-06-07 本地完成 `projects` PostgreSQL primary-write 与可选 JSON archive mirror。

- 默认运行态仍为 `file-only`，不写 PostgreSQL primary。
- 只有 `MIEMIE_DATABASE_ENABLED=true` 且 `MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS=projects` 或 `MIEMIE_DATABASE_WRITE_MODE=postgres/postgres_primary/primary` 时，项目保存和删除才以 PostgreSQL 为主。
- 主写成功后默认不再写 JSON；`MIEMIE_DATABASE_JSON_ARCHIVE_WRITES=true` 时保留临时 JSON archive mirror。
- PostgreSQL 主写失败会向上抛出，并且不会落 JSON mirror，避免切库期产生分叉状态。
- 未修改公开 API 响应结构、路由、前端行为或服务器开关。

## Changed Files

- `backend/app/repositories/project_runtime.py`
- `backend/app/services/storage.py`
- `backend/tests/test_project_primary_write.py`

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_project_primary_write.py -q
4 passed

backend/.venv/bin/pytest backend/tests/test_project_primary_write.py backend/tests/test_project_read_switch.py backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_storage_service.py -q
22 passed

backend/.venv/bin/python -m py_compile backend/app/repositories/project_runtime.py backend/app/services/storage.py
passed

backend/.venv/bin/pytest backend/tests/test_project_primary_write.py backend/tests/test_project_read_switch.py backend/tests/test_project_dual_write.py backend/tests/test_project_migration.py backend/tests/test_project_repository.py backend/tests/test_project_schema.py backend/tests/test_studio_task_read_switch.py backend/tests/test_studio_task_dual_write.py backend/tests/test_studio_task_primary_write.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_read_switch.py backend/tests/test_video_studio_task_dual_write.py backend/tests/test_video_studio_task_primary_write.py backend/tests/test_video_studio_task_migration.py backend/tests/test_database_health.py -q
52 passed

docker compose config
passed

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
301 passed
```

## Runtime State

- Local code: `projects` primary-write implemented.
- Default config: still JSON/file-only.
- Staging/live: not enabled in this slice.
- Project domain local migration state: schema, repository, backfill/reconcile, dual-write, read-switch, and primary-write are all implemented.
- Next local domain: media metadata, or resume server rollout first if SSH/public health are stable.
- Next server slice: resume R7/R1-R2 server health, live migration, backfill/reconcile, then dual-write/read-switch/primary-write gates.
