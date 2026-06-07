# R29 Staging Connectivity Refresh

2026-06-07 refreshed the staging connectivity gates before attempting PostgreSQL live rollout.

## Summary

Server rollout is not safe to start from the current operator path.

- `pre-studio.miemie.co` still resolves to Clash/fake-IP `198.18.2.211`.
- Route to origin IP `47.79.99.190` still goes through `utun1024`.
- TCP port `22` is reachable.
- SSH command reaches the host but is closed by the remote side before a command can run.
- Public `/api/health` via `https://pre-studio.miemie.co/api/health` times out with no response body.

No server state was changed.

## Evidence

```bash
dig +short pre-studio.miemie.co A
```

```text
198.18.2.211
```

```bash
route -n get 47.79.99.190
```

```text
gateway: 198.18.0.1
interface: utun1024
```

```bash
nc -vz 47.79.99.190 22
```

```text
Connection to 47.79.99.190 port 22 [tcp/ssh] succeeded!
```

```bash
ssh -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'
```

```text
Connection closed by 47.79.99.190 port 22
```

```bash
curl --noproxy "*" -sS -D /tmp/pre-studio-r29-health.headers -o /tmp/pre-studio-r29-health.json --connect-timeout 10 --max-time 20 https://pre-studio.miemie.co/api/health
```

```text
curl: (28) Operation timed out after 20004 milliseconds with 0 bytes received
```

## Decision

- Do not run server migration, backfill, reconcile, Compose restart, or primary-write rollout from this path.
- Continue local database migration work that does not require staging access.
- Resume server rollout only after SSH command execution and public `/api/health` are both stable.

