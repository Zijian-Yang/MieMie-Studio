# R52 Connectivity Preflight

2026-06-17 added a local preflight gate for the `pre-studio` staging command path. The goal is to decide whether it is safe to run the R51 PostgreSQL staging sequence before touching server containers or database feature flags.

## New Script

Added `scripts/pre_studio_connectivity_preflight.sh`.

Default target values:

- host: `pre-studio.miemie.co`
- origin IP: `47.79.99.190`
- SSH target: `root@47.79.99.190`
- public health: `https://pre-studio.miemie.co/api/health`

The script checks:

- sanitized proxy-env presence;
- DNS A records and fake-IP detection for `198.18.0.0/15`;
- route to the origin IP and TUN/fake-IP route detection;
- TCP reachability on SSH port 22;
- SSH command path with `BatchMode=yes` and a short connect timeout;
- public `/api/health` with `--noproxy "*"` plus required response headers.

It writes `status.json`, `results.tsv`, and per-check logs to the configured artifact directory. It exits `0` only when all gates pass; exits `2` when the path is blocked.

## Current Live Result

The live preflight was run outside the sandbox because the sandboxed network path returned DNS and permission errors.

Result: blocked.

Summary:

- DNS: blocked, fake-IP detected (`198.18.0.80`).
- Route: blocked, route uses gateway `198.18.0.1` and interface `utun1024`.
- TCP 22: passed.
- SSH banner: blocked, `Connection closed by 47.79.99.190 port 22`.
- Public health: failed, `curl: (16) Error in the HTTP2 framing layer`.

No server command, container restart, database switch, or provider call was executed.

## Verification

- `bash -n scripts/pre_studio_connectivity_preflight.sh`: passed.
- `python3 scripts/verify_pre_studio_connectivity_preflight.py`: passed.
- `python3 scripts/verify_postgres_staging_canary_sequence.py`: passed.
- Live preflight wrote a controlled blocked status.

## Next Gate

Before running:

```bash
CONFIRM_STAGING_SEQUENCE=run scripts/postgres_staging_video_task_sequence.sh
```

first rerun:

```bash
scripts/pre_studio_connectivity_preflight.sh
```

Only continue to the staging sequence when the preflight exits `0`.
