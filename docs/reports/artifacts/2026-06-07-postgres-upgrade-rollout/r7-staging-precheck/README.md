# R7 Staging Precheck

Date: 2026-06-07

Scope:

- Resume the PostgreSQL staging rollout after local R6 primary-write implementation.
- Verify whether the operator client can reach the staging SSH and public health endpoints before changing server state.

Result:

- Staging rollout did not advance.
- No server files, Compose settings, database flags, or containers were changed in this precheck.
- The local client network is currently unsuitable for reliable staging verification because DNS/route inspection shows Clash TUN/fake-ip interception.

Observed evidence:

- `ssh -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'` ended with `Connection closed by 47.79.99.190 port 22`.
- `ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new root@47.79.99.190 'echo ok'` ended with `Connection timed out during banner exchange`.
- `curl --noproxy "*" ... https://pre-studio.miemie.co/api/health` timed out after 20 seconds with no response body.
- `dig +short pre-studio.miemie.co A` returned `198.18.2.211`, which is a Clash fake-ip range.
- `route -n get 47.79.99.190` routed through `utun1024` via `198.18.0.1`.
- `nc -vz 47.79.99.190 22` succeeded at TCP level.
- `nc -vz pre-studio.miemie.co 443` succeeded at TCP level.
- Attempts to use visible local Clash ports as explicit SOCKS/HTTP proxy did not provide a working SSH/public-health path.

Interpretation:

- This precheck does not prove the staging server or app is down.
- It proves the current operator-side network path cannot provide the SSH and HTTPS application-layer evidence required by the rollout plan.
- The database rollout should resume only after a direct route, stable SSH banner exchange, and public `/api/health` response are available.

Next action:

1. Temporarily disable Clash TUN/fake-ip or add direct rules that affect both `pre-studio.miemie.co` and `47.79.99.190`.
2. Re-run staging precheck with short commands.
3. If SSH and health recover, pull `pre` to `94e8ae5` or newer on `/opt/miemie-pre`, then continue PostgreSQL container/health/backup/migration gates.
