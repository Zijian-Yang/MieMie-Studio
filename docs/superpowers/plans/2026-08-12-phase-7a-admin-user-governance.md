# Phase 7A Admin User Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PostgreSQL-backed administrator role, closed-by-default registration, safe platform-user CRUD, session revocation, audit logging, bootstrap tooling, and an administrator user-management UI.

**Architecture:** Extend the existing PostgreSQL `users` domain rather than adding a parallel identity store. Put authorization and invariants in focused backend services and dependencies; the React UI consumes typed admin APIs but is never the authorization boundary. Store the registration flag and audit rows in PostgreSQL, while host-level deployment actions remain outside the Web API.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy Core, Alembic, PostgreSQL, Redis sessions, React 18, TypeScript, Ant Design, Zustand, pytest, Playwright.

## Global Constraints

- Public registration defaults to disabled.
- Initial administrator creation is explicit and idempotent; no user becomes administrator based on registration order.
- After bootstrap there is always at least one active administrator.
- Administrators cannot disable, delete, or demote themselves.
- Disabling, deleting, password resetting, or security-role changes revoke all target sessions.
- User deletion is soft deletion and preserves business data.
- Every admin mutation writes a sanitized audit record.
- The Web API never executes Git, Docker, shell, restore, uninstall, or permanent-delete operations.

---

### Task 1: Identity Schema And Migration

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/db/schema/user_config.py`
- Create: `backend/app/db/schema/platform_admin.py`
- Modify: `backend/app/db/schema/__init__.py`
- Create: `backend/app/db/migrations/versions/20260812_0010_admin_governance.py`
- Test: `backend/tests/test_admin_schema.py`
- Test: `backend/tests/test_user_config_repository.py`

**Interfaces:**
- Produces: `User.role`, `User.status`, `User.must_change_password`, `User.updated_at`.
- Produces: `platform_settings` and `admin_audit_logs` SQLAlchemy tables.
- Produces migration revision `20260812_0010` after `20260617_0009`.

- [x] **Step 1: Write failing model, schema, and migration contract tests**
- [x] **Step 2: Run focused tests and confirm missing fields/tables fail**
- [x] **Step 3: Add enum-constrained Pydantic fields, SQL columns, indexes, platform settings, audit schema, and migration**
- [x] **Step 4: Update row mapping so snapshots and indexed security columns stay consistent**
- [x] **Step 5: Run focused tests and Alembic offline upgrade/downgrade SQL rehearsal**
  - Focused and compatibility regression: `82 passed`.
  - Live PostgreSQL upgrade/downgrade remains part of Task 7 staging verification.
- [x] **Step 6: Commit the schema slice** (`863fade`)

### Task 2: Administrator Repository And Invariants

**Files:**
- Modify: `backend/app/repositories/user_config.py`
- Modify: `backend/app/repositories/user_config_runtime.py`
- Create: `backend/app/repositories/platform_admin.py`
- Create: `backend/app/services/admin_user_service.py`
- Modify: `backend/app/services/user_service.py`
- Test: `backend/tests/test_admin_user_service.py`
- Test: `backend/tests/test_user_service.py`

**Interfaces:**
- Produces: `AdminUserService.list_users`, `create_user`, `update_user`, `reset_password`, and `delete_user`.
- Produces: `PlatformSettingsRepository.registration_enabled()` and `set_registration_enabled()`.
- Produces: `AdminAuditRepository.append()` and paginated `list()`.
- Consumes: existing session runtime deletion by user ID.

- [x] **Step 1: Write failing tests for CRUD, pagination, duplicate usernames, self-protection, last-admin protection, soft deletion, and session revocation**
- [x] **Step 2: Run focused tests and confirm service/repository absence fails**
- [x] **Step 3: Implement repository queries and transaction-safe active-admin checks**
  - Administrator mutations serialize on the singleton platform settings row before locking target users.
- [x] **Step 4: Implement service mutations and sanitized audit payloads**
- [x] **Step 5: Reject disabled/deleted users during login and token recovery**
- [x] **Step 6: Run focused and existing auth/user repository regression tests**
  - Backend full suite: `491 passed`.
- [x] **Step 7: Commit the service slice** (`bde44d5`)

### Task 3: Bootstrap, Registration Policy, And Admin Authorization

**Files:**
- Create: `backend/app/services/admin_bootstrap.py`
- Create: `backend/app/cli/admin.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/app/middleware/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_bootstrap.py`
- Test: `backend/tests/test_auth.py`
- Test: `backend/tests/test_admin_authorization.py`

**Interfaces:**
- Produces: `python -m app.cli.admin bootstrap|promote|reset-password`.
- Produces: `GET /api/bootstrap/status` public endpoint.
- Produces: `require_admin(request: Request) -> User` dependency.
- Consumes: `PlatformSettingsRepository` and `AdminUserService`.

- [x] **Step 1: Write failing tests for closed registration, bootstrap status, idempotent first admin, explicit legacy promotion, and member 403**
- [x] **Step 2: Run tests and confirm policy/CLI/dependency failures**
- [x] **Step 3: Implement public bootstrap status and registration gate with stable error code**
- [x] **Step 4: Implement request-state administrator dependency**
- [x] **Step 5: Implement secure CLI input and idempotent bootstrap/promote/reset commands**
  - Password input is interactive or supplied through `MIEMIE_ADMIN_PASSWORD`; no plaintext password CLI argument exists.
- [x] **Step 6: Run auth, middleware, CLI, and registration regressions**
  - Backend full suite: `505 passed`.
- [x] **Step 7: Commit the authorization slice** (`2c79b40`)

### Task 4: Admin User And Audit APIs

**Files:**
- Create: `backend/app/routers/admin_users.py`
- Create: `backend/app/routers/admin_platform.py`
- Create: `backend/app/models/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_users_api.py`
- Test: `backend/tests/test_admin_platform_api.py`

**Interfaces:**
- Produces: `/api/admin/users*`, `/api/admin/platform-settings`, and `/api/admin/audit-logs`.
- Produces paginated `{items,page,page_size,total}` responses.
- Consumes: `require_admin`, `AdminUserService`, and platform repositories.

- [x] **Step 1: Write failing router tests for every endpoint, validation error, permission denial, invariant conflict, and audit row**
- [x] **Step 2: Run tests and confirm missing routes fail**
- [x] **Step 3: Implement typed request/response models and stable error mapping**
- [x] **Step 4: Implement routers with admin dependency and focused rate limits**
- [x] **Step 5: Verify no password hash, session token, secret, or raw snapshot appears in responses/audits**
  - OpenAPI response-schema audit passed for all administrator routes.
- [x] **Step 6: Run focused API tests and backend full suite**
  - Backend full suite: `514 passed`.
- [x] **Step 7: Commit the API slice** (`0c57727`)

### Task 5: Typed Frontend Admin Boundary

**Files:**
- Create: `frontend/src/services/adminApi.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/authStore.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout/MainLayout.tsx`
- Modify: `frontend/src/pages/Login/LoginPage.tsx`
- Create: `frontend/src/components/AdminRoute.tsx`
- Test: `frontend/scripts/test-admin-route-policy.mjs`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces typed `adminApi` and bootstrap status client.
- Produces `AdminRoute` based on server-returned user role.
- Consumes new user response role/status/must-change-password fields.

- [x] **Step 1: Write failing static contract test for typed admin API, route guard, hidden navigation, and registration bootstrap behavior**
- [x] **Step 2: Run the test and confirm missing boundary fails**
- [x] **Step 3: Extend auth state and typed API contracts**
- [x] **Step 4: Add `/admin` lazy routes and backend-derived admin guard**
- [x] **Step 5: Hide registration form when bootstrap status disables it and preserve clear empty/error states**
- [x] **Step 6: Run typecheck, lint, and focused policy test**
  - Typecheck, lint, production build, chunk check, and admin route policy passed.
- [x] **Step 7: Commit the frontend boundary slice** (`6aec8d4`)

### Task 6: Administrator User Management UI

**Files:**
- Create: `frontend/src/pages/Admin/AdminLayout.tsx`
- Create: `frontend/src/pages/Admin/AdminUsersPage.tsx`
- Create: `frontend/src/pages/Admin/AdminUserDrawer.tsx`
- Create: `frontend/src/pages/Admin/AdminAuditPage.tsx`
- Create: `frontend/src/pages/Admin/adminUserModel.ts`
- Test: `frontend/scripts/test-admin-user-management.mjs`
- Modify: `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: typed `adminApi`.
- Produces: dense user table, filters, create/edit drawer, password reset, disable/enable, delete confirmation, and audit table.

- [x] **Step 1: Write failing UI contract and Playwright fixtures for admin/member roles**
- [x] **Step 2: Run focused test and confirm missing pages/actions fail**
- [x] **Step 3: Implement admin layout and stable responsive table dimensions**
- [x] **Step 4: Implement create/edit forms and invariant-aware action states**
- [x] **Step 5: Implement reset, disable/enable, delete confirmation, pagination, errors, and audit view**
- [x] **Step 6: Run focused tests, typecheck, lint, build, chunk and Playwright E2E**
  - Full E2E passed `12/12`; focused admin desktop/member/mobile E2E was reconfirmed `3/3` after Chromium helper validation.
- [ ] **Step 7: Commit the admin UI slice**

### Task 7: Compose Migration And Staging Verification

**Files:**
- Modify: `docker-compose.yml`
- Modify: `compose.env.example`
- Create: `scripts/admin_governance_smoke.py`
- Create: `scripts/verify_admin_governance_smoke.py`
- Create: `docs/reports/artifacts/2026-08-12-phase-7a-admin-governance/README.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/ISSUES.md`

**Interfaces:**
- Produces a provider-free server smoke that creates a temporary member, exercises lifecycle and audit, and cleans sessions/data safely.
- Consumes migration `20260812_0010` and all 7A APIs.

- [ ] **Step 1: Write failing verifier for smoke privacy, cleanup, and invariant coverage**
- [ ] **Step 2: Implement provider-free smoke and sanitized artifact output**
- [ ] **Step 3: Run local full backend/frontend gates**
- [ ] **Step 4: Back up staging, deploy migration and current commit, and bootstrap the approved existing administrator explicitly**
- [ ] **Step 5: Run local/public health, admin smoke, member-denial smoke, session revocation, Compose status, database snapshot, and S1 gate**
- [ ] **Step 6: Archive sanitized evidence and update docs/status**
- [ ] **Step 7: Commit and push the completed 7A stage**

## Phase 7A Completion Evidence

- Alembic database/code head is `20260812_0010`.
- Backend full suite passes.
- Frontend typecheck, lint, build, chunk, admin policy tests and E2E pass.
- Staging admin can CRUD users; ordinary users receive 403 for all admin APIs.
- Registration is disabled by default and can be changed only by an administrator.
- Disabling/resetting/deleting a user immediately invalidates existing sessions.
- Self/last-admin protections are proven by API and service tests.
- Audit records are complete and sanitized.
- Local/public health, PostgreSQL, Redis and workers stay healthy after deployment.
