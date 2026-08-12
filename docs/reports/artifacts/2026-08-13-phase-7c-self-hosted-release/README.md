# Phase 7C Self-hosted Release Evidence

## Scope

This artifact directory records sanitized evidence for the self-hosted installer, operator CLI, lifecycle state machine, non-root Compose runtime, documentation, and staging qualification. It must not contain `compose.env`, credentials, tokens, database dumps, user data, or unredacted URLs with secrets.

## Local implementation commits

- `9e91dd1`: fixed non-root/read-only Compose runtime hardening.
- `af17ce3`: idempotent installer and operator CLI foundation.
- `04914ae`: backup-first update, rollback, restore, purge guards, and lifecycle documentation.

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

## Pending evidence

- Staging upgrade to the current 7C commit, non-root identities, local/public health and workers.
- Real custom dump plus isolated restore on staging.
- Failure rollback, repeat install, and preserved-data uninstall simulation.
- S1 staging gate and sanitized final state.

Real Aliyun OSS, real provider generation, clean OS matrix, arm64, and current-release Cloudflare S4/W2 belong to phase 7D.
