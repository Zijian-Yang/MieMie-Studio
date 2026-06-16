# R56 Direct Rule Preflight

2026-06-17 reran the staging connectivity preflight after the local Clash configuration was updated with DIRECT rules for `pre-studio.miemie.co` and the origin IP.

## Result

State: `blocked`.

Local deploy doctor still passed with expected local warnings only:

- passed: 19
- warnings: 2
- blocked: 0
- failed: 0

Warnings:

- local `compose.env` is missing;
- Docker daemon probing is skipped by default.

The PostgreSQL remote sequence was **not** executed.

## Live Preflight Summary

- DNS: blocked, fake-IP still detected (`198.18.0.100`).
- Route: blocked, origin route still uses gateway `198.18.0.1` and interface `utun1024`.
- TCP 22: passed.
- SSH banner: blocked, timed out during banner exchange.
- Public health: failed, curl timed out after 20 seconds with no bytes received.

This means the Clash DIRECT rule did not take effect at the macOS DNS/route layer used by the preflight command path. Running the remote database sequence remains unsafe because the operator path still cannot prove stable SSH and public health.

## Next Operator Check

Before rerunning the remote wrapper, the local machine should show both:

```bash
dig +short pre-studio.miemie.co A
```

returning real Cloudflare A records, not `198.18.*`, and:

```bash
route -n get 47.79.99.190
```

returning a physical network interface such as `en0`, not `utun*`.

Only then rerun:

```bash
RUN_ID=r57-preflight-after-network-clean \
ARTIFACT_DIR=/tmp/r57-preflight-after-network-clean \
TMP_DIR=/tmp/r57-preflight-after-network-clean-tmp \
bash scripts/pre_studio_connectivity_preflight.sh
```
