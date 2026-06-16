# R57 Network-scope Remediation

This was a fast DNS/route-only check. It intentionally did not run TCP, SSH, or public health checks.

Required local evidence before running the full preflight:

- `dig +short pre-studio.miemie.co A` must return real Cloudflare A records, not `198.18.*`.
- `route -n get 47.79.99.190` must show a physical interface such as `en0`, not `utun*`.

Once both are clean, run:

```bash
bash scripts/pre_studio_connectivity_preflight.sh
```

Only after the full preflight exits `0`, run:

```bash
CONFIRM_REMOTE_SEQUENCE=run scripts/pre_studio_remote_postgres_sequence.sh
```
