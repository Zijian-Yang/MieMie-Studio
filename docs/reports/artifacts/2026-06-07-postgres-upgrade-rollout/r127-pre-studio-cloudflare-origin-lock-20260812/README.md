# R127 pre-studio Cloudflare origin lock

## Result

The aaPanel extension configuration now limits the `pre-studio.miemie.co`
origin server block to loopback and Cloudflare's published proxy networks.
This avoids exposing the application through its origin IP while preserving
the public Cloudflare path and certificate challenge location.

## Verification

- Public `https://pre-studio.miemie.co/api/health`: HTTP `200`, Cloudflare,
  `cf-cache-status=DYNAMIC`, `cache-control=no-store`.
- Direct origin HTTP health with the production Host header: HTTP `403`.
- Direct origin HTTPS health with forced origin resolution: HTTP `403`.
- Direct nonexistent ACME challenge probe: HTTP `404`, proving the existing
  `/.well-known` location remains reachable.
- aaPanel Nginx configuration test: passed.
- Repository and installed extension SHA256:
  `46a517a0c3fd8c8c2c62a18f7fab916015323d3a8ec209bb6f1a8b944ed3888a`.
- Temporary R126 proof cron file is absent from `/etc/cron.d`; only the formal
  `/etc/cron.d/miemie-postgres-ops` schedule remains.

Cloudflare still advertises HTTP/3 on the public response. That is an entry
transport observation, not a failure of the origin allowlist.
