# Manual TCP/SSH Check

时间：2026-06-17

## Commands

```bash
nc -vz 47.79.99.190 22
ssh -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'
ssh -vvv -o BatchMode=yes -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'
```

## Observed

- TCP connect to `47.79.99.190:22` succeeded.
- SSH echo timed out during banner exchange.
- verbose SSH reached `Connection established` and printed the local version string, then timed out waiting for the remote banner.

## Interpretation

本轮证明问题已经不是单纯端口不可达。TCP 22 可达，但 SSH 命令执行仍不可用，因此不能进入远程 PostgreSQL sequence。
