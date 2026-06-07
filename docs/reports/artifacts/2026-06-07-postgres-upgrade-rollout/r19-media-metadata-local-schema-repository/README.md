# R19 Media Metadata Local Schema + Repository Boundary

## Summary

2026-06-07 本地完成 media metadata 的 PostgreSQL schema、Alembic migration 和 repository boundary。

- 新增 `media_assets` 表，覆盖图库图片、音频库和视频库 metadata。
- 新增 `text_items` 表，独立覆盖文本库内容和版本快照。
- 不迁文件本体；PostgreSQL 只保存 URL、归属、索引列、metadata 和完整 JSONB 快照。
- 新增 file/PostgreSQL repository boundary，但尚未接入 runtime dual-write/read-switch/primary-write。
- 默认运行态仍为 JSON/file-only，服务器未启用本域数据库路径。

## Changed Files

- `backend/app/db/schema/media_assets.py`
- `backend/app/db/schema/__init__.py`
- `backend/app/db/migrations/versions/20260607_0004_media_metadata.py`
- `backend/app/repositories/base.py`
- `backend/app/repositories/media_assets.py`
- `backend/tests/test_media_metadata_schema.py`
- `backend/tests/test_media_metadata_repository.py`

## Verification

```text
backend/.venv/bin/pytest backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py -q
9 passed

backend/.venv/bin/pytest backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_schema.py backend/tests/test_project_repository.py backend/tests/test_studio_task_schema.py backend/tests/test_video_studio_task_schema.py -q
22 passed

MIEMIE_DATABASE_URL=postgresql+psycopg://miemie:example@postgres:5432/miemie backend/.venv/bin/alembic -c backend/alembic.ini upgrade head --sql
generated SQL through 20260607_0004

backend/.venv/bin/python -m py_compile backend/app/db/schema/media_assets.py backend/app/repositories/media_assets.py backend/app/db/migrations/versions/20260607_0004_media_metadata.py backend/app/repositories/base.py
passed

backend/.venv/bin/pytest backend/tests/test_media_metadata_schema.py backend/tests/test_media_metadata_repository.py backend/tests/test_project_schema.py backend/tests/test_project_repository.py backend/tests/test_project_migration.py backend/tests/test_studio_task_schema.py backend/tests/test_studio_task_repository.py backend/tests/test_studio_task_migration.py backend/tests/test_video_studio_task_schema.py backend/tests/test_video_studio_task_repository.py backend/tests/test_video_studio_task_migration.py backend/tests/test_storage_service.py backend/tests/test_database_health.py -q
43 passed

docker compose config
passed

git diff --check
passed

backend/.venv/bin/pytest backend/tests -q
310 passed
```

## Runtime State

- Local code: media metadata schema/repository boundary implemented.
- Default config: still JSON/file-only.
- Staging/live: not enabled in this slice.
- Next local slice: media metadata backfill/reconcile tooling.
- Next server slice: resume R7/R1-R2 server health when SSH/public health recover.
