# R40 staging connectivity after user/config local gates

Date: 2026-06-07

## Scope

Read-only connectivity refresh after local user/config database gates completed.

No server state was changed.

## Results

- SSH command execution: failed.
  - Command: `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=12 root@47.79.99.190 '...'`
  - Result: `Connection timed out during banner exchange`
- Public health: failed.
  - Command: `curl --noproxy "*" ... https://pre-studio.miemie.co/api/health`
  - Result: curl timeout after 20 seconds with no response body.
- DNS:
  - `pre-studio.miemie.co A` resolved to `198.18.2.211`, indicating the current local operator path is still using a fake-IP/TUN route.
- Route:
  - Route to `47.79.99.190` used gateway `198.18.0.1` and interface `utun1024`.
- TCP:
  - `nc -vz 47.79.99.190 22` succeeded, so port 22 is reachable but SSH command execution is not usable from this path.

## Conclusion

The local development and documentation gates can continue, but server rollout should not be attempted from the current operator network path. Before live rollout, verify:

- DNS for `pre-studio.miemie.co` returns real Cloudflare or expected direct IPs, not `198.18.*`.
- Route to `47.79.99.190` uses a normal physical interface instead of `utun*`.
- SSH command execution returns a prompt or `echo ok`, not only TCP reachability.
- Public `/api/health` returns HTTP 200.
