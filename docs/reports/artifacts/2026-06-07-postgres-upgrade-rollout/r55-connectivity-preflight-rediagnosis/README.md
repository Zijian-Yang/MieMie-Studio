# R55 Connectivity Preflight Rediagnosis

2026-06-17 reran the PostgreSQL rollout connectivity gate after R54 deploy doctor was added.

## Result

State: `blocked`.

Local deploy doctor still passed with warnings only:

- passed: 19
- warnings: 2
- blocked: 0
- failed: 0

Warnings were expected for this local workspace:

- `compose.env` is missing because the local repo is not the Compose runtime host.
- Docker daemon probing is skipped unless `MIEMIE_DEPLOY_DOCTOR_RUN_DOCKER_INFO=true`.

The staging connectivity preflight remained blocked before any remote command could run.

## Live Preflight Summary

- DNS: blocked, fake-IP detected (`198.18.0.100`).
- Route: blocked, route uses gateway `198.18.0.1` and interface `utun1024`.
- TCP 22: passed.
- SSH banner: blocked, timed out during banner exchange.
- Public health: failed, curl timed out after 20 seconds with no bytes received.

An extra forced-interface probe was also attempted from the local Mac:

- `route -n get -ifscope en0 47.79.99.190` showed physical gateway `192.168.50.1` and interface `en0`.
- `ssh -o BindInterface=en0 root@47.79.99.190 echo ok` still timed out during banner exchange.
- `curl --interface en0 --resolve pre-studio.miemie.co:443:104.21.85.29 ... /api/health` still timed out.

This points to the operator network path still being unsuitable for running the remote database sequence. No server command, container restart, database switch, or provider call was executed.

## Script Improvement

`scripts/pre_studio_connectivity_preflight.sh` now writes `remediation.md` on dry-run, passed, and blocked runs. The remediation summary consolidates the exact next action for fake-IP DNS, TUN route, SSH banner stalls, and public health timeouts.

## Verification

- `bash -n scripts/pre_studio_connectivity_preflight.sh`: passed.
- `python3 scripts/verify_pre_studio_connectivity_preflight.py`: passed.
- `python3 -m py_compile scripts/verify_pre_studio_connectivity_preflight.py`: passed.
- Live preflight wrote `status.json`, `results.tsv`, and `remediation.md`.

## Next Gate

Do not run `CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh` until `scripts/pre_studio_connectivity_preflight.sh` exits `0`.
