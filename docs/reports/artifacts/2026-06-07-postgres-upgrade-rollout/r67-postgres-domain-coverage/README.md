# R67 PostgreSQL Domain Coverage

Date: 2026-06-17

## Summary

R67 adds a repeatable PostgreSQL domain coverage audit.

- New script: `scripts/postgres_domain_coverage.py`.
- New verifier: `scripts/verify_postgres_domain_coverage.py`.
- Generated report: `domain-coverage.md`.
- Machine-readable summary: `domain-coverage.summary.json`.
- Current migrated domains covered by local schema/repository/backfill/reconcile/runtime gates: `video_studio_tasks`, `studio_tasks`, `projects`, `media_metadata`, `project_entities`, `benchmark_records`, `user_config`, and `sessions`.
- Next recommended migration domain: `audio_studio`.

## Findings

`audio_studio` is the remaining clear JSON-only business-state domain. It currently stores audio studio tasks in `audio_studio/*.json` and voice profiles in `voices/*.json` through direct `StorageService` file methods.

Project scripts and shots are not a separate immediate migration domain in this audit because they are already preserved by `projects.raw_project_snapshot`.

## Verification

- RED: `python3 scripts/verify_postgres_domain_coverage.py` failed before implementation because `scripts/postgres_domain_coverage.py` did not exist.
- `python3 scripts/verify_postgres_domain_coverage.py` -> passed.
- `python3 scripts/postgres_domain_coverage.py --artifact-dir docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r67-postgres-domain-coverage --run-id r67-postgres-domain-coverage-20260617` -> passed.

## Server State

No server command was executed by this artifact. Application runtime remains JSON/file-primary, and PostgreSQL business read/write switches remain disabled until the staging sequence can run.
