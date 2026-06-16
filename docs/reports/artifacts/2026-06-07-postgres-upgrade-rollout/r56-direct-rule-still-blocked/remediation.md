# R56 Remediation

The DIRECT rules have not taken effect for the command-line path yet.

Required local evidence before continuing:

- `dig +short pre-studio.miemie.co A` must return Cloudflare real A records such as `104.21.*` or `172.67.*`, not `198.18.*`.
- `route -n get 47.79.99.190` must show a physical network interface such as `en0`, not `utun*`.
- `ssh -o BatchMode=yes -o ConnectTimeout=12 root@47.79.99.190 echo ok` must return `ok`.
- `curl --noproxy "*" -k -sS -D - -o /tmp/pre-studio-health.json --connect-timeout 10 --max-time 20 https://pre-studio.miemie.co/api/health` must return HTTP 200 with `x-request-id` and `x-deployment-version`.

Do not run the remote PostgreSQL sequence until `scripts/pre_studio_connectivity_preflight.sh` exits `0`.
