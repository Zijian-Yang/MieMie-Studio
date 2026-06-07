# R18 Staging Connectivity Refresh

## Summary

2026-06-07 在本地完成一次只读服务器连通性刷新检查。本轮未修改服务器文件、Compose env、数据库开关或容器状态。

## Results

| Check | Result | Notes |
|---|---|---|
| SSH command | blocked | `Connection closed by 47.79.99.190 port 22` |
| DNS `pre-studio.miemie.co` | blocked for operator route | resolved to `198.18.2.211`, indicating local fake-IP/TUN interception |
| Route to origin IP | blocked for operator route | `47.79.99.190` routes through `utun1024` via `198.18.0.1` |
| TCP 22 | reachable | `nc -vz 47.79.99.190 22` succeeded |
| Public `/api/health` | blocked from current client path | `curl --noproxy "*"` timed out after 20s with 0 bytes received |

## Interpretation

- TCP reachability alone is not enough for server rollout automation; SSH command execution is still unavailable from the current operator path.
- The local client still appears to be using Clash TUN/fake-IP routing for this domain/origin path.
- Because SSH is blocked, this run cannot verify remote Compose state, `postgres` container health, server-local `/api/health`, live migration, backfill/reconcile, or backup/restore rehearsal.

## Next Gate

Before server-side database rollout can resume, one of these must be true:

- SSH command execution to `root@47.79.99.190` succeeds from this environment, and public `/api/health` is reachable; or
- the rollout is executed from a confirmed direct network path or server console, with artifacts copied back afterward.

Local development can continue on the next domain while this operator-route issue is unresolved.
