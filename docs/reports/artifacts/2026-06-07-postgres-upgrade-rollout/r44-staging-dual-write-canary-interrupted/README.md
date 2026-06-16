# R44 Staging Dual-Write Canary Interrupted

2026-06-16 attempted to start the first application-level PostgreSQL gate for `miemie-pre`, but did not reach the dual-write canary.

## Intended Scope

- Keep application traffic on JSON/file primary.
- Roll staging runtime from the old image to the current server repo commit.
- Keep `MIEMIE_DATABASE_ENABLED=false` during image rollout.
- After health passes on the new image, enable `video_studio_tasks` dual-write only.
- Run health, no-provider/preview smoke, and `video_studio_tasks` reconcile before any read switch.

## What Changed On Server

- Server `compose.env` was backed up to `compose.env.bak-r44-dual-write-canary-20260616`.
- `MIEMIE_RUNTIME_GIT_COMMIT` in `compose.env` was updated to `e73124527eeb858c4d12aa8990f19c6574bfb9d4`.
- `MIEMIE_DATABASE_ENABLED` was explicitly kept as `false`.
- No database read/write domain switch was enabled.
- No `docker compose up` or container restart completed in this attempt.

## Interruption

- A Docker build for `miemie-studio:pre-local` was started with `docker compose -f docker-compose.yml -f docker-compose.pre.override.yml build api`.
- The SSH session timed out during the build before completion was observed.
- A follow-up SSH audit could not run because SSH reached TCP connect but timed out during banner exchange.
- The local route to `47.79.99.190` was through `utun1024` / `198.18.0.1`, matching the earlier Clash TUN/fake-IP failure mode.
- Local DNS for `pre-studio.miemie.co` returned `198.18.2.63`.

## Safety Boundary

This was not a dual-write canary result. Treat the application runtime state as unknown until SSH is restored and the following read-only checks pass:

```bash
cd /opt/miemie-pre
docker image inspect miemie-studio:pre-local --format '{{.Id}} {{.Created}}'
docker compose --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml -p miemie-pre ps
docker compose --env-file compose.env -f docker-compose.yml -f docker-compose.pre.override.yml -p miemie-pre logs --tail=120 api
curl -sS -D - -o /tmp/r44-recovery-health.json http://127.0.0.1:18100/api/health
cat /tmp/r44-recovery-health.json
grep -E '^(MIEMIE_RUNTIME_GIT_COMMIT|MIEMIE_DATABASE_ENABLED|MIEMIE_DATABASE_WRITE_MODE|MIEMIE_DATABASE_READ_MODE|MIEMIE_DATABASE_DUAL_WRITE_DOMAINS|MIEMIE_DATABASE_READ_DOMAINS)' compose.env
```

Only after the image/build/container state is understood should R44 continue.

## Next Recovery Step

1. Restore direct SSH path, avoiding Clash TUN/fake-IP for `47.79.99.190`.
2. Audit whether the interrupted build produced a new `miemie-studio:pre-local` image.
3. If build did not complete, rebuild.
4. Roll API/worker/worker-video to the new image while `MIEMIE_DATABASE_ENABLED=false`.
5. Verify `/api/health` reports deployment version `e73124527eeb858c4d12aa8990f19c6574bfb9d4`.
6. Then enable `video_studio_tasks` dual-write and run the actual canary.
