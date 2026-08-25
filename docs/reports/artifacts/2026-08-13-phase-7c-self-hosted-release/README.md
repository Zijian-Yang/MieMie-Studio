# Phase 7C Self-hosted Release Evidence

## Scope

This artifact directory records sanitized evidence for the self-hosted installer, operator CLI, lifecycle state machine, non-root Compose runtime, documentation, and staging qualification. It must not contain `compose.env`, credentials, tokens, database dumps, user data, or unredacted URLs with secrets.

## Local implementation commits

- `9e91dd1`: fixed non-root/read-only Compose runtime hardening.
- `af17ce3`: idempotent installer and operator CLI foundation.
- `04914ae`: backup-first update, rollback, restore, purge guards, and lifecycle documentation.
- `0def216`: administrator initialization working-directory fix and takeover rollback baseline.
- `6c9550a`: relocatable operator CLI and paired library installation.
- `901ebbd`: digest-pinned base images and production Python dependency lock.
- `cd4e7d2`: repeat-install preservation of the recorded rollback target.
- `e1c5dd2`: sanitized server qualification checkpoint used as the real update target.
- `b38e3c0`: health-gated full-stack `miemie start` command for preserved-data recovery.

## Local focused verification

- `python3 scripts/verify_miemie_lifecycle.py`: passed.
- `python3 scripts/verify_miemie_cli.py`: passed.
- `python3 scripts/verify_self_hosted_installer.py`: passed.
- `python3 scripts/verify_postgres_restore_rehearsal.py`: passed.
- `venv/bin/python scripts/verify_self_hosted_compose.py`: passed.
- `docker compose --env-file compose.env.example config -q`: passed.
- PostgreSQL backup/ops/OSS focused regression: `32 passed`.

## Local full gate

- Backend full pytest: `609 passed`.
- Alembic platform-operations and backup follow-up: `17 passed`, no deprecation warning after explicit path separator configuration.
- Frontend typecheck, lint, production build, Vite chunk contract, four video policy/layout contracts, and three admin contracts: passed.
- Playwright Chromium discovery helper: `2 passed`.
- Playwright browser E2E: `14 passed`.
- Markdown local links, fence balance, diff whitespace, tracked sensitive paths, changed-line secret patterns, and artifact prohibited-file scan: passed.

## Ubuntu 24.04 staging qualification checkpoint

On 2026-08-25, the existing `miemie-pre` deployment at `/opt/miemie-pre` was taken over by the production installer and advanced through the current release commits.

- Installer completed with source-built, commit-tagged images and retained the existing PostgreSQL, Redis, administrator, secrets, data binds, and loopback port `18100`.
- API, worker, video worker, operations worker, and scheduler all run as UID/GID `10001:10001` with read-only roots, all capabilities dropped, `no-new-privileges`, and no privileged mode.
- Local health and the Cloudflare public health endpoint returned `200`; Redis and PostgreSQL were healthy and response headers included request and deployment identifiers.
- `miemie status` and `miemie doctor` passed from the relocated `/opt/miemie-pre` install; CLI and its library were installed together under `/usr/local/bin`.
- Production image dependency validation returned `No broken requirements found`.
- Same-commit repeat install preserved the byte-identical `compose.env`, the recorded previous release, and exact row counts for users, projects, platform settings, and operation runs.
- `miemie backup` created a PostgreSQL custom dump and sidecar with mode `600`; SHA-256, `pg_restore --list`, and isolated temporary-database restore all passed.

No credential, token, environment value, database dump, username, or private row data is stored in this artifact.

## Final lifecycle qualification

- An injected image-build failure caused `miemie update --apply` to return non-zero after its pre-update backup; source, environment, image, health, and current release remained on the previous commit, while a `rolled_back` manifest was retained.
- The next normal `miemie update --apply` advanced to the intended commit, recorded its backup and previous release, ran migration, and passed API plus worker health gates.
- Explicit rollback completed a healthy round trip from the new release to the recorded previous image and back, with forward-only schema reporting.
- Default `miemie uninstall` stopped every service while preserving byte-identical environment/release files, backup contents, named volumes, and core row counts. `miemie start` restored the entire stack and passed health/worker gates.
- Full `miemie restore` passed checksum/list validation, temporary database restore, safety backup, writer stop, production replacement, migration, and post-restore health; user, project, and platform-setting row counts were unchanged.
- Final local S1 used `30 VU / 60s`: `1729` requests, `0` failed requests, `5187/5187` checks, P95 `82.78ms`, and P99 `124.52ms` against the `300ms` gate.
- Celery inspection found exactly three live queue roles: `studio`, `video_studio`, and `ops`; scheduler, API, PostgreSQL, Redis, and all workers were running with restart count `0` after the gate.
- Final runtime commit for this checkpoint was `b38e3c0875f8850011cbb1a0bdbdc7c599a6660c`; local and Cloudflare health returned `200` with matching deployment identifiers.

## Phase result

Phase 7C is complete. The remaining release-candidate work is phase 7D: clean supported-OS qualification, arm64 evidence or an explicit limitation, current-release provider/OSS smoke, and Cloudflare capacity gates.

Real Aliyun OSS, real provider generation, clean OS matrix, arm64, and current-release Cloudflare S4/W2 belong to phase 7D.
