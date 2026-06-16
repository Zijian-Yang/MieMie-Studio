# R42 Staging PostgreSQL Live Resume

2026-06-16 resumed the server-side PostgreSQL rollout path for `miemie-pre`.

## Scope

- Resume from R40/R41 after local and SSH paths were previously blocked.
- Verify staging SSH, Compose, app health, and public health.
- Fast-forward the staging repository to the latest `origin/pre`.
- Start the staging `postgres` service and verify `pg_isready`.
- Begin building the latest `api` image for one-off Alembic/backfill/reconcile execution.

## Completed Evidence

- SSH command execution initially worked.
- Server repo before update: `cb2d4ff0f5e00d2eb7fbb84a6b411408014107f0`.
- Server repo after fast-forward: `e73124527eeb858c4d12aa8990f19c6574bfb9d4`.
- Existing runtime stayed on `x-deployment-version: 00091f21f5ee207f78a1092e7e5e164ab4567c7f`.
- Server-local health before and after starting PostgreSQL returned `HTTP 200`.
- Server-side public Cloudflare health returned `HTTP 200`, `cf-cache-status: DYNAMIC`, and `server: cloudflare`.
- `postgres` service was created and started.
- `pg_isready` returned `accepting connections`.

## Current Blocker

During `docker compose build api`, the SSH session stopped responding:

```text
Timeout, server 47.79.99.190 not responding.
Connection timed out during banner exchange
```

Follow-up SSH checks still timed out during banner exchange. TCP connect checks from the local machine reported port 22/443/18100 as reachable, but local routing still uses the Clash/TUN path and DNS for `pre-studio.miemie.co` resolved to a `198.18.*` fake IP, so local client checks are not authoritative.

## State Boundary

- PostgreSQL container was started.
- The server repository was updated.
- No Alembic migration was executed.
- No backfill or reconcile script was executed.
- No `MIEMIE_DATABASE_*` app traffic switch was enabled.
- API, worker, and worker-video containers were not intentionally restarted after the repository update.
- Latest API image build completion is unknown until SSH recovers.

## Next Recovery Step

When SSH command execution recovers, run a read-only recovery check first:

```bash
cd /opt/miemie-pre
git rev-parse HEAD
docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}' | head
curl -sS -D - -o /tmp/miemie-health-recover.json --connect-timeout 5 --max-time 15 http://127.0.0.1:18100/api/health
cat /tmp/miemie-health-recover.json
```

Only after the server is confirmed healthy should the one-off migration/backfill/reconcile commands continue.
