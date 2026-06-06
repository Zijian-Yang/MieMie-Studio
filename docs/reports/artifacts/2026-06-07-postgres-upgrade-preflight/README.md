# PostgreSQL Upgrade Preflight

Run date: 2026-06-07

Purpose: verify that the local workspace, staging server, public entry, and required runtime tools are ready before starting the Compose PostgreSQL platform upgrade.

## Result

State: ready

The upgrade can enter Task R1 from `docs/superpowers/plans/2026-06-07-postgres-platform-upgrade-execution.md`.

## Local Checks

- Branch: `pre`
- Local commit: `2284582a8b0855cdda7a4d0997c450ea55f19694`
- Docker: `28.3.3`
- Docker Compose: `v2.39.2-desktop.1`
- Python: `3.12.12`
- pytest: `9.0.3`
- Node: `v25.9.0`
- npm: `11.12.1`
- k6: `v2.0.0`
- `docker compose config`: passed
- `backend/.venv/bin/pytest backend/tests/test_runtime_observability.py backend/tests/test_storage_service.py -q`: `4 passed`
- `cd frontend && npm run typecheck`: passed
- `cd frontend && npm run test:vite-chunks`: passed

## Staging Checks

- SSH target: `root@47.79.99.190`
- App path: `/opt/miemie-pre`
- Hostname: `iZt4n2nvjul89t6xx5ivfaZ`
- Server commit: `00091f21f5ee207f78a1092e7e5e164ab4567c7f`
- Required files: `compose.env`, `docker-compose.yml`, and `docker-compose.pre.override.yml` exist.
- Compose project: `miemie-pre`
- Running services: `api`, `redis`, `worker`, `worker-video`
- Local server health: `HTTP/1.1 200 OK`
- Health body: `status=ok`, `redis.ok=true`, `run_mode=prod`, `serve_frontend=true`
- Docker Compose config on server: passed
- Server Docker: `29.1.3`
- Server Docker Compose: `2.40.3`
- Server k6: `v2.0.0-rc1`
- Disk: `/dev/vda3` has `28G` available, `41%` used.
- Memory: `3.4GiB` total, `994MiB` available, no swap.

## Public Entry

- URL: `https://pre-studio.miemie.co/api/health`
- Status: `HTTP/2 200`
- Headers present: `server: cloudflare`, `x-request-id`, `x-deployment-version`, `cf-cache-status: DYNAMIC`
- Public health body matches server runtime commit `00091f21f5ee207f78a1092e7e5e164ab4567c7f`.
- Local Mac route during this preflight still resolved through Clash TUN/fake-ip (`198.18.2.211`, `utun1024`), so local client Cloudflare latency remains a client-route variable and not a staging rollout blocker.

## PostgreSQL Image Readiness

- Existing `postgres` Compose service: not present yet.
- `postgres:16-alpine` was missing before preflight.
- `docker pull postgres:16-alpine`: succeeded.
- Pulled digest: `sha256:16bc17c64a573ef34162af9298258d1aec548232985b33ed7b1eac33ba35c229`
- `docker run --rm postgres:16-alpine postgres --version`: `postgres (PostgreSQL) 16.14`

## Notes

- Server has no swap and less than 1GiB available memory at idle. R1/R2 should use conservative PostgreSQL settings and watch `docker stats`.
- A separate non-`miemie-pre` container named `miemie-studio-ha-lab-api-1` was visible in `docker stats`; it was not part of the `miemie-pre` Compose project and was not modified.
- No raw key, token, password, or private user data was written to this artifact.
