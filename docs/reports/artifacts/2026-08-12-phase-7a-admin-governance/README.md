# Phase 7A Admin Governance Evidence

## Scope

This directory records sanitized evidence for administrator and platform-user governance. The smoke is provider-free: it does not submit image, video, audio, LLM, or other supplier jobs.

## Local Gate

- Backend full suite: `517 passed`.
- Frontend: typecheck, lint, production build, Vite chunk contract, admin route policy, and admin user-management contract passed.
- Compose: syntax, PostgreSQL-only defaults, shared image tag, migration-before-application dependency, and loopback bind contracts passed.
- Smoke verifier: full synthetic lifecycle passed against an in-process fake API; artifact scanning found no administrator token, member token, password, username, or user identifier.

## Server Gate

Passed on the `miemie-pre` server on 2026-08-12:

- release `9666111` was backed up and fast-forwarded to `8ed4d10`;
- the pre-upgrade PostgreSQL backup was non-empty and recorded with SHA-256;
- Alembic upgraded from `20260617_0009` to `20260812_0010` before application containers started;
- local `127.0.0.1:18100` and public Cloudflare health passed on the same release;
- Redis, PostgreSQL, studio worker, and video worker remained healthy;
- provider-free administrator governance smoke passed every lifecycle, authorization, revocation, self-protection, and audit check;
- S1 at `30 VU / 60s` completed 1744 requests with 0 failures and P95 `65.099ms`.

Sanitized server evidence is under `server-20260812/`.

Raw credentials, tokens, PostgreSQL URLs, usernames, user identifiers, and request bodies must not be committed here.
