# Pre-studio Entrypoint Audit

Default mode is dry-run.

Run the read-only audit with:

```bash
CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT=run python3 scripts/pre_studio_entrypoint_audit.py
```

Optional server-side local origin check:

```bash
LOCAL_BASE_URL=http://127.0.0.1:18100 CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT=run python3 scripts/pre_studio_entrypoint_audit.py
```

The run mode checks:

- public `/api/health` is 200 and returns `status=ok`, `redis.ok=true`, and `database.ok=true` when present;
- public API headers include `X-Request-ID`, `X-Deployment-Version`, `Cache-Control: no-store`, and Cloudflare `DYNAMIC` cache status;
- public `/` is 200 HTML and references a hashed `/_static/*` asset;
- the hashed static asset has long immutable cache headers and reaches Cloudflare `HIT` on the second request;
- optional local origin `/api/health` is 200 when `LOCAL_BASE_URL` is provided.
