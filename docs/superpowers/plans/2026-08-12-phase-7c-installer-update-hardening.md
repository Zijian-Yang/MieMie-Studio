# Phase 7C Installer, Update, And Runtime Hardening Plan

> **Execution rule:** Implement every task test-first, keep this checklist current, and preserve the Web/host privilege boundary from ADR-0004.

**Goal:** Turn the `pre` source tree into a repeatable one-server self-hosted release with an idempotent installer, one stable `miemie` operator command, pre-update backup, commit-pinned local builds, health-guarded rollback, isolated restore validation, and non-root application containers.

**Architecture:** `install.sh` is the only production bootstrap entry. It validates a supported Linux host, installs only missing prerequisites through Docker's official repository when explicitly allowed, creates a root-owned installation and release state, generates a mode-600 `compose.env`, builds the current Git commit, starts PostgreSQL/Redis/migration/application services, bootstraps the first administrator, and installs `scripts/miemie` as `/usr/local/bin/miemie`. The CLI resolves the install root from `/etc/miemie/miemie.conf`, always supplies the env file and Compose project, and performs privileged lifecycle operations outside the Web API. Update state records old/new commits and immutable local image tags; schema remains forward-only unless the operator explicitly restores a validated pre-update database backup.

**Safety boundaries:**

- Production API listens on `127.0.0.1:<port>` by default; PostgreSQL and Redis publish no host ports.
- API/worker/scheduler/migrate containers run as a fixed non-root UID/GID. Only `worker-ops` can write the host backup bind mount; none receive Docker socket, Git credentials, or host root paths.
- Install/update never overwrite an existing encryption key, database password, administrator, named volume, or backup.
- Administrator passwords are accepted only from a hidden prompt or `MIEMIE_ADMIN_PASSWORD` environment variable; they never appear in argv, logs, state, or artifacts.
- `update --apply` requires a clean tracked worktree, creates and validates a PostgreSQL backup, fetches `origin/pre`, accepts only a fast-forward commit, builds a commit-tagged image, migrates, switches services, and restores the previous image/commit on health failure.
- Automatic application rollback does not downgrade PostgreSQL schema. CLI clearly reports schema compatibility and points to the explicit restore workflow.
- Restore requires two confirmations, validates the dump in a temporary database first, creates a safety backup, stops application writers, replaces the production database, reruns migration, starts services, and verifies health.
- `uninstall` stops services and preserves env, source, named volumes, and backups by default. Destructive removal requires the exact phrase `DELETE MIEMIE DATA` and is never exposed through Web APIs.
- All commands emit stable stage/state/reason output and redact secrets.

---

## Task 1: Release Compose And Non-root Runtime

**Files:** `Dockerfile`, `docker-compose.yml`, `compose.env.example`, `scripts/verify_self_hosted_compose.py`

- [x] Write a verifier for fixed UID/GID, non-root services, writable bind ownership contract, log rotation, stop grace periods, loopback-only API, no DB/Redis ports, no Docker socket, and PostgreSQL-only defaults.
- [x] Create runtime user/group and pre-create writable directories in the image.
- [x] Apply non-root user/read-only filesystem/tmpfs/capability policies that remain compatible with ffmpeg, Celery, migration, static serving, data/log binds, and backup writes.
- [x] Add Compose logging/stop settings and explicit health/dependency contracts.
- [x] Run Dockerfile/Compose static verifier, `docker compose config`, backend focused tests, and production frontend build.
  - `verify_self_hosted_compose.py` passed, Docker runtime regression `7 passed`, and rendered Compose config is valid.
  - Installer/update must chown legacy bind directories to `10001:10001` before switching existing deployments.
- [x] Commit the runtime hardening slice (`9e91dd1`).

## Task 2: Idempotent Production Installer

**Files:** `install.sh`, `scripts/install_lib.sh`, `scripts/verify_self_hosted_installer.py`, `docs/reports/artifacts/2026-08-12-phase-7c-self-hosted-release/README.md`

- [x] Write dry-run and fake-command tests for supported OS/arch, root check, resources, prerequisites, port collision, install root, mode-600 env generation, key preservation, commit image tag, staged failure, and repeat install.
- [x] Implement structured stage logging to `/var/log/miemie/install.log` without secret values.
- [x] Implement opt-in prerequisite installation for Ubuntu 22.04/24.04 and Debian 12 using Docker's official repository; default tests remain offline.
- [x] Generate secure instance id, PostgreSQL password, platform encryption key, release state, Compose project, and loopback port.
- [x] Build/start/migrate/bootstrap/health in safe order; support hidden administrator prompt and automation-only environment input.
- [x] Install `/etc/miemie/miemie.conf` and `/usr/local/bin/miemie` atomically; repeat install must converge without data reset.
- [x] Run installer verifier and isolated temporary-root rehearsal.
  - Offline dry-run verifier passes and confirms no install-root mutation; real clean-host Compose execution remains in Task 5/7D.
- [x] Commit the installer slice (`af17ce3`, shared with the CLI foundation).

## Task 3: Operator CLI Foundations

**Files:** `scripts/miemie`, `scripts/miemie_lib.sh`, `scripts/verify_miemie_cli.py`

- [x] Write fake-Compose tests for `status`, `logs`, `doctor`, `restart`, `backup --wait`, `backups`, administrator bootstrap/promote/reset-password, and preserved-data uninstall.
- [x] Implement safe config discovery, root/permission checks, one canonical Compose command, stable exit codes, locking, and redacted log helpers.
- [x] Implement status/version/health/worker/database/backup-root checks and actionable doctor warnings for CPU/RAM/disk/time/ports.
- [x] Implement operations API-independent backup enqueue/wait through application services in an ephemeral container; list sanitized backup history.
- [x] Implement administrator commands using hidden prompt/environment secrets, never plaintext argv.
- [x] Implement start/restart/logs and preserved-data uninstall.
- [x] Run CLI verifier, shell syntax, ShellCheck when available, and Compose contract tests.
  - Fake Docker/curl execution proves canonical env/project flags, service validation, lock use, preserved-data stop, and secret-safe administrator invocation.
- [x] Commit the CLI foundation slice (`af17ce3`).

## Task 4: Transactional Update, Rollback, Restore, And Destructive Uninstall

**Files:** `scripts/miemie`, `scripts/miemie_lib.sh`, `scripts/verify_miemie_lifecycle.py`, `docs/playbooks/SELF_HOSTED_UPGRADE_ROLLBACK.md`, `docs/playbooks/SELF_HOSTED_BACKUP_RESTORE.md`

- [x] Write state-machine tests for update check, dirty-tree block, non-fast-forward block, backup failure, build failure, migration failure, health failure image rollback, explicit release rollback, restore confirmation, isolated validation failure, safety backup, and destructive confirmation.
- [x] Implement release manifests under root-only `/var/lib/miemie/releases/` with commit, image, migration head, backup id, timestamp, state, and previous release.
- [x] Implement update check/apply with fetch timeout, commit pin, pre-update dump, build, migration, service switch, health/worker gates, and application rollback.
- [x] Implement rollback to a recorded local image/source commit without automatic schema downgrade; report when database restore is required.
- [x] Implement restore with checksum/list validation, temporary database rehearsal, safety backup, writer stop, production replacement, migration, health, and failure instructions.
- [x] Implement destructive uninstall only with exact confirmation and explicit removal of volumes/config/source/backups.
- [x] Run lifecycle verifier and isolated Compose update/failure/restore rehearsals.
  - Offline lifecycle state machine and real server backup, injected update failure rollback, explicit rollback round trip, isolated restore, and full restore all passed.
- [x] Commit the lifecycle slice (`04914ae`, with server-discovered fixes through `b38e3c0`).

## Task 5: Production Documentation And Server Qualification

**Files:** `README.md`, `README.pre.md`, `docs/playbooks/SELF_HOSTED_INSTALL.md`, `docs/playbooks/SELF_HOSTED_ADMIN.md`, `docs/playbooks/SELF_HOSTED_REVERSE_PROXY.md`, `docs/README.md`, `docs/CHANGELOG.md`, `docs/ISSUES.md`, roadmap and this plan.

- [x] Make production install the first README quick start and keep developer `run.sh` in a separate section.
- [x] Document supported hosts, resource floor, local port output, reverse-proxy boundary, first admin, update/rollback, backup/restore, and uninstall.
- [x] Run backend full suite; frontend typecheck/lint/build/chunk/contracts/E2E; installer/CLI/lifecycle verifiers; secret scan.
  - Backend `609 passed`; frontend static/build/contracts passed; Playwright helper `2 passed`, browser E2E `14 passed`; installer/CLI/lifecycle/Compose/restore verifiers and secret/artifact scans passed.
- [x] Run current staging upgrade through the new CLI, confirm non-root application services, local/public health, all worker pings, S1, backup and isolated restore.
- [x] Run repeat-install, failed-update rollback, preserved-data uninstall simulation, and release-state evidence without losing production data.
- [x] Archive sanitized evidence and mark 7C complete; clean-OS matrix work moves explicitly to 7D.
- [x] Commit and push completed 7C.

## Completion Evidence

- One documented install command produces a PostgreSQL-only service bound to loopback with an administrator and healthy queues.
- Re-running install preserves secrets, administrator state, data volumes, backups, and service port.
- Application services are non-root and have no Docker socket or host-management capability.
- Update is commit-pinned, backup-first, fast-forward-only, health-gated, and application-rollback capable.
- Restore validates in isolation and requires two explicit confirmations before production replacement.
- Default uninstall preserves data; destructive removal cannot happen accidentally.
- Logs, release state, artifacts, API, browser state, and Git contain no credentials.
