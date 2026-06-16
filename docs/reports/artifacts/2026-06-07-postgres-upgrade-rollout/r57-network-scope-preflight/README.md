# R57 Network-scope Preflight

2026-06-17 added a fast network-only scope to the staging connectivity preflight.

## Why

The full preflight waits for DNS, route, TCP 22, SSH banner, and public health. While the local macOS command path is still caught by Clash fake-IP/TUN, the expensive SSH and curl timeout windows slow down each recovery attempt.

`MIEMIE_PREFLIGHT_SCOPE=network` now checks only the two gates that must be clean before the full preflight is worth running:

- DNS for `pre-studio.miemie.co` must not return `198.18.0.0/15`.
- Route to `47.79.99.190` must not use `utun*` or gateway `198.18.*`.

When these pass, run the full preflight. Only when the full preflight exits `0` should the remote PostgreSQL sequence run.

## Command

```bash
MIEMIE_PREFLIGHT_SCOPE=network \
RUN_ID=r57-network-scope-live-20260617 \
ARTIFACT_DIR=/tmp/r57-network-scope-live-20260617 \
TMP_DIR=/tmp/r57-network-scope-live-20260617-tmp \
bash scripts/pre_studio_connectivity_preflight.sh
```

## Live Result

State: `blocked`.

- DNS: blocked, fake-IP detected (`198.18.0.100`).
- Route: blocked, route still uses gateway `198.18.0.1` and interface `utun1024`.
- TCP/SSH/public health: intentionally not executed in network scope.

The remote PostgreSQL sequence was not executed.

## Verification

- `bash -n scripts/pre_studio_connectivity_preflight.sh`: passed.
- `python3 scripts/verify_pre_studio_connectivity_preflight.py`: passed.
- Live network-only preflight wrote `status.json`, `results.tsv`, and `remediation.md`.
