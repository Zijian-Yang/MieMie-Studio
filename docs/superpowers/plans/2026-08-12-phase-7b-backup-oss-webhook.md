# Phase 7B Backup, OSS, And Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add administrator-configurable PostgreSQL backups, Aliyun OSS off-site copies, generic Webhook notifications, low-privilege operations workers, scheduling, history, and management pages without giving the Web API host or Docker privileges.

**Architecture:** Extend the single PostgreSQL `platform_settings` row with operational policy and authenticated-encrypted secret columns, and add immutable `operation_runs` records with an idempotency key. The API validates and stores settings or enqueues work; a dedicated Celery `ops` queue performs dumps, validation, retention, OSS upload, and Webhook delivery. A scheduler process claims one daily backup key per local schedule date. Database restore remains host CLI-only.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy Core, Alembic, PostgreSQL 16 client tools, AES-GCM from `cryptography`, Celery/Redis, Aliyun `oss2`, `httpx`, React 18, TypeScript, Ant Design, pytest, Playwright.

## Global Constraints

- The service continues to expose only `${MIEMIE_HOST_BIND:-127.0.0.1}:${MIEMIE_HOST_PORT:-8000}`; no PostgreSQL or Redis host port is published.
- Platform backup OSS credentials are separate from per-user asset OSS configuration.
- `MIEMIE_PLATFORM_ENCRYPTION_KEY` is required to save or use operational secrets and is never returned, logged, audited, or committed.
- API responses expose only secret configured flags and masked endpoint/bucket/prefix metadata; never encrypted blobs or raw secret values.
- Backup paths are relative descendants of `/var/lib/miemie/backups`; absolute paths, `..`, symlinks escaping the root, and empty normalized names are rejected.
- Web API may enqueue backup and test operations, but it cannot restore databases, execute Git, access Docker, or run arbitrary commands.
- Backup scheduling accepts only one daily `HH:MM` in `Asia/Shanghai`; no arbitrary cron expressions.
- `schedule_date + operation_type` produces a unique idempotency key.
- Backup files are written to a unique temporary file, fsynced, validated, checksummed, and atomically renamed.
- Local backup success and OSS upload success are separate states in operation history.
- Webhook payloads contain platform event metadata only, never user content, credentials, prompts, provider payloads, database URLs, or private asset URLs.
- Existing host cron stays active until two scheduler-produced successful runs prove parity; the cutover must prevent duplicate schedules.
- Every task uses tests first and updates this plan immediately after completion.

---

### Task 1: Operational Schema And Secret Cryptography

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app/db/schema/platform_admin.py`
- Modify: `backend/app/db/schema/__init__.py`
- Create: `backend/app/db/migrations/versions/20260812_0011_platform_operations.py`
- Create: `backend/app/services/platform_crypto.py`
- Test: `backend/tests/test_platform_operations_schema.py`
- Test: `backend/tests/test_platform_crypto.py`

**Interfaces:**
- Produces `PlatformSecretCipher.encrypt(str) -> str`, `decrypt(str) -> str`, `mask(str) -> str`, and `build_platform_secret_cipher()`.
- Produces `operation_runs` and operational columns on `platform_settings`.

- [x] **Step 1: Write schema tests for every operational setting, operation status field, indexes, constraints, and unique idempotency key**
- [x] **Step 2: Run focused schema tests and confirm the missing migration/schema fails**
- [x] **Step 3: Add `cryptography>=42,<46`, AES-256-GCM envelope versioning, strict URL-safe base64 key parsing, and secret-free errors**
- [x] **Step 4: Add migration `20260812_0011` with safe defaults and compile upgrade/downgrade SQL**
- [x] **Step 5: Run crypto/schema/migration tests and secret-value leak assertions**
  - Focused schema/crypto/admin regression: `12 passed`.
  - Alembic offline upgrade and `20260812_0011 -> 20260812_0010` downgrade SQL compiled successfully.
- [x] **Step 6: Commit the schema and crypto slice**
  - Schema/crypto slice: `404c516`; review hardening: `40cdc8b`.
  - Strict canonical URL-safe Base64 key parsing and executable offline migration upgrade/downgrade coverage now pass.

### Task 2: Settings And Operation Repositories

**Files:**
- Modify: `backend/app/repositories/platform_admin.py`
- Modify: `backend/app/repositories/user_config_runtime.py`
- Create: `backend/app/models/platform_operations.py`
- Create: `backend/app/services/platform_operations.py`
- Test: `backend/tests/test_platform_operations_repository.py`
- Test: `backend/tests/test_platform_operations_service.py`

**Interfaces:**
- Produces `PlatformOperationsSettings`, `MaskedPlatformOperationsSettings`, and `OperationRun` models.
- Produces `PlatformOperationsService.get_settings()`, `update_settings(actor, patch, request_id)`, `queue_operation(type, source, actor_id, idempotency_key)`, `claim_run(id)`, `complete_run(...)`, `fail_run(...)`, and paginated history.

- [x] **Step 1: Write repository tests for encrypted round-trip, partial secret preservation, clear-secret flags, pagination, state transitions, and idempotency conflicts**
- [x] **Step 2: Run focused tests and confirm missing repository/service contracts fail**
- [x] **Step 3: Implement path, schedule, retention, timeout, retry, endpoint, prefix, and configuration completeness validation**
- [x] **Step 4: Implement transactional settings/audit updates and operation state transitions without plaintext secrets in audit rows**
- [x] **Step 5: Run focused tests including wrong/missing encryption key and concurrent idempotency behavior**
  - Focused operations model/repository/service/schema/crypto suite covers encrypted preservation/replacement/clear, secret-free audit flags, wrong-key failure, conditional state transitions, pagination, and unique-key conflict recovery.
- [x] **Step 6: Commit the repository and service slice**
  - Repository/service slice: `8f626cd`.
  - Focused suite: `32 passed`; includes encrypted tri-state updates, secret-free audit, state transitions, pagination, and idempotency conflict recovery.

### Task 3: Generic Webhook Delivery

**Files:**
- Create: `backend/app/services/ops_webhook.py`
- Test: `backend/tests/test_ops_webhook.py`

**Interfaces:**
- Produces `OpsWebhookEvent` and `WebhookDeliveryResult`.
- Produces `OpsWebhookClient.send(event, config)`, with bounded timeout and retry count and stable failure categories.

- [x] **Step 1: Write local mock HTTP tests for fixed payload, disabled behavior, timeout, retry, 4xx no-retry, 5xx retry, and redaction**
- [x] **Step 2: Run tests and confirm missing client fails**
- [x] **Step 3: Implement a synchronous `httpx.Client` sender with maximum 30-second timeout and maximum 3 retries**
- [x] **Step 4: Ensure logs/errors contain host-independent categories, not URL, response body, or event private data**
- [x] **Step 5: Run focused tests and payload secret scan**
  - Focused Webhook suite: `9 passed`; fixed schema forbids extra private fields and all delivery results exclude target URL and response body.
- [ ] **Step 6: Commit the Webhook slice**

### Task 4: PostgreSQL Backup, Retention, And Aliyun OSS

**Files:**
- Create: `backend/app/services/postgres_backup.py`
- Create: `backend/app/services/backup_oss.py`
- Test: `backend/tests/test_postgres_backup.py`
- Test: `backend/tests/test_backup_oss.py`

**Interfaces:**
- Produces `PostgresBackupExecutor.run(run_id, settings) -> BackupResult`.
- Produces `BackupOSSClient.test(settings)` and `upload(local_path, object_key, settings) -> OSSUploadResult`.

- [ ] **Step 1: Write fake-binary tests for pg_dump arguments/env privacy, temporary-file cleanup, fsync/rename, pg_restore validation, SHA-256, retention minimum, and path traversal**
- [ ] **Step 2: Write fake OSS tests for dedicated credentials, deterministic object key, ETag, test object cleanup, and secret-free failures**
- [ ] **Step 3: Run tests and confirm both services are absent**
- [ ] **Step 4: Implement custom-format dump through `pg_dump`, validation through `pg_restore --list`, and deterministic retention**
- [ ] **Step 5: Implement dedicated `oss2` client and test/upload paths without reusing per-user config context**
- [ ] **Step 6: Run focused tests and commit the backup engine slice**

### Task 5: Ops Celery Worker And Daily Scheduler

**Files:**
- Modify: `backend/app/celery_app.py`
- Modify: `backend/app/worker_tasks.py`
- Create: `backend/app/services/ops_runner.py`
- Create: `backend/app/ops_scheduler.py`
- Test: `backend/tests/test_ops_runner.py`
- Test: `backend/tests/test_ops_scheduler.py`

**Interfaces:**
- Produces Celery tasks `ops.backup`, `ops.test_oss`, and `ops.test_webhook` routed only to queue `ops`.
- Produces one scheduler tick that queues `scheduled-backup:<YYYY-MM-DD>` once after the configured `HH:MM`.

- [ ] **Step 1: Write task-route and runner orchestration tests for success, local-only success, OSS failure, backup failure, alert failure, and operation state updates**
- [ ] **Step 2: Write scheduler tests for disabled, before due, due, restart duplication, timezone, and next-day behavior**
- [ ] **Step 3: Run tests and confirm missing runner/scheduler fails**
- [ ] **Step 4: Implement worker orchestration and stable error classes without provider calls**
- [ ] **Step 5: Implement a signal-aware minute loop and transactional idempotent scheduling**
- [ ] **Step 6: Run focused tests and commit worker/scheduler slice**

### Task 6: Administrator Operations APIs

**Files:**
- Modify: `backend/app/models/admin.py`
- Modify: `backend/app/routers/admin_platform.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/src/services/adminApi.ts`
- Test: `backend/tests/test_admin_operations_api.py`
- Modify: `backend/tests/test_openapi_contract.py`

**Interfaces:**
- `GET/PATCH /api/admin/platform-settings` returns/updates masked settings.
- `POST/GET /api/admin/backups`, `POST /api/admin/backups/test-oss`, and `POST /api/admin/alerts/test` enqueue or list runs.

- [ ] **Step 1: Write API tests for admin-only access, masked response, validation errors, enqueue-only behavior, rate limits, pagination, and no restore endpoint**
- [ ] **Step 2: Run focused tests and confirm missing routes fail**
- [ ] **Step 3: Implement typed request/response models and stable error codes**
- [ ] **Step 4: Implement APIs with transactional audit and queue-after-commit behavior**
- [ ] **Step 5: Run API/OpenAPI tests and scan schema for secret response fields**
- [ ] **Step 6: Commit the API slice**

### Task 7: Administrator Overview, Backup, And Alert UI

**Files:**
- Modify: `frontend/src/pages/Admin/AdminLayout.tsx`
- Create: `frontend/src/pages/Admin/AdminOverviewPage.tsx`
- Create: `frontend/src/pages/Admin/AdminBackupsPage.tsx`
- Create: `frontend/src/pages/Admin/AdminAlertsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/scripts/test-admin-user-management.mjs`
- Create: `frontend/scripts/test-admin-operations.mjs`
- Modify: `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes typed `adminApi`; secrets use replace-or-preserve fields and never render stored values.
- Produces compact operational navigation and responsive history tables.

- [ ] **Step 1: Write failing UI contract and Playwright admin/member fixtures**
- [ ] **Step 2: Implement overview status rows, backup schedule/retention/local path/OSS form, immediate backup, and run history**
- [ ] **Step 3: Implement Webhook enable/config/test form and recent result list**
- [ ] **Step 4: Add loading, empty, queued, partial-success, failed, and secret-preservation states**
- [ ] **Step 5: Run typecheck, lint, production build, chunk contracts, focused UI test, and Playwright**
- [ ] **Step 6: Commit the UI slice**

### Task 8: Compose, Staging Cutover, And Evidence

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `compose.env.example`
- Create: `scripts/platform_ops_smoke.py`
- Create: `scripts/verify_platform_ops_smoke.py`
- Create: `docs/reports/artifacts/2026-08-12-phase-7b-platform-operations/README.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/ISSUES.md`
- Modify: `docs/plans/2026-08-12-self-hosted-release-roadmap.md`

**Interfaces:**
- Adds `worker-ops` and `scheduler`, PostgreSQL client tools, fixed backup mount, encryption key, and ops queue.
- Produces provider-free local/server smoke and real OSS/Webhook evidence when credentials are already available.

- [ ] **Step 1: Write Compose tests for no Docker socket, no database/Redis host ports, fixed backup root, shared image, ops queue, scheduler, and secret placeholder rejection**
- [ ] **Step 2: Implement Compose/Docker changes and provider-free smoke/verifier**
- [ ] **Step 3: Run backend full suite and all frontend gates**
- [ ] **Step 4: Back up staging, generate root-only encryption key, deploy migration/services, and run local/public health plus operations smoke**
- [ ] **Step 5: Configure temporary real Webhook and approved Aliyun OSS credentials if available, upload one backup, isolate-restore it, and clean test objects/secrets**
- [ ] **Step 6: Observe two scheduler-produced daily successes before disabling legacy host cron; prove no duplicate backup key**
- [ ] **Step 7: Archive sanitized evidence, update docs, commit, and push completed 7B**

## Phase 7B Completion Evidence

- Alembic database/code head is `20260812_0011`.
- Backend full suite and frontend static/E2E gates pass.
- Operational credentials are authenticated-encrypted and absent from Git, logs, artifacts, audit rows, OpenAPI responses, and browser state.
- Immediate and scheduled backups produce valid custom-format dumps, checksums, deterministic retention, and separate local/OSS status.
- Real Aliyun OSS upload and isolated restore pass, or the stage remains incomplete with an explicit credential blocker.
- Real generic Webhook receives test and synthetic failure events with no user/private content.
- `worker-ops` and scheduler run without Docker socket and API never executes restore or host commands.
- Two scheduler days prove parity before legacy cron is disabled, with no duplicate idempotency key.
- Local/public health, PostgreSQL, Redis, all workers, and S1 stay healthy after deployment.
