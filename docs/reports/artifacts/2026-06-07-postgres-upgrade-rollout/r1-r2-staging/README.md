# PostgreSQL R1/R2 Staging Rollout

Run date: 2026-06-07

Scope:

- Pull R1/R2 implementation to `/opt/miemie-pre`.
- Prepare non-committed `compose.env` PostgreSQL settings.
- Build and start `postgres`, `api`, `worker`, and `worker-video`.
- Verify `pg_isready`, `/api/health.database`, backup, and restore rehearsal.

## Progress

- Server precheck before rollout passed:
  - branch `pre`
  - previous runtime commit `00091f21f5ee207f78a1092e7e5e164ab4567c7f`
  - `/api/health` returned `200`
  - `api`, `redis`, `worker`, and `worker-video` were running
- Server fast-forwarded to `cb2d4ff0f5e00d2eb7fbb84a6b411408014107f0`.
- Server `compose.env` was updated without printing secrets:
  - `MIEMIE_RUNTIME_GIT_COMMIT=cb2d4ff0f5e00d2eb7fbb84a6b411408014107f0`
  - PostgreSQL database/user set to `miemie`
  - PostgreSQL strong password generated/stored only in server `compose.env`
  - `MIEMIE_DATABASE_ENABLED=false`
  - `MIEMIE_DATABASE_WRITE_MODE=file`
  - `MIEMIE_DATABASE_READ_MODE=file`
  - `MIEMIE_DATABASE_JSON_FALLBACK_READ=true`
- Server `docker compose config` passed.
- `docker compose up -d --build postgres api worker worker-video` started, but the SSH session was closed by the remote host during image build.

## Current Verification State

Staging verification is not complete yet.

After the SSH disconnect:

- SSH banner exchange timed out from this client.
- Source TCP ports were intermittently reachable by `nc`.
- HTTP health from this client did not return a complete response.
- Local Mac route to the server IP was observed through Clash TUN (`utun1024`), and later direct/bound attempts were rejected by the local network layer with `Operation not permitted`.

Because the server-side final state could not be inspected, this rollout is marked `in_progress`, not passed.

## Required Next Checks

When SSH access is reliable again, run:

```bash
cd /opt/miemie-pre
docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml ps
docker compose -p miemie-pre --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml exec -T postgres pg_isready -U miemie -d miemie
curl -sS -D - -o /tmp/miemie-health-r1r2.json --connect-timeout 5 --max-time 15 http://127.0.0.1:18100/api/health
cat /tmp/miemie-health-r1r2.json
bash scripts/postgres_backup.sh
bash scripts/postgres_restore_rehearsal.sh <latest-backup.sql>
docker stats --no-stream
```

Expected:

- `postgres`, `api`, `redis`, `worker`, and `worker-video` running.
- `pg_isready` reports accepting connections.
- `/api/health` returns `200`, includes `database.configured=false`, `database.ok=null` while DB dependency is disabled.
- Backup and restore rehearsal pass.
- No API/worker restart loop.

## Sensitive Data

No raw key, token, PostgreSQL password, or private user data was written to this artifact.
