# pre-studio Nginx extension configuration

`pre-studio-cloudflare-origin-allowlist.conf` is a site-scoped aaPanel Nginx
extension. Install it at:

```text
/www/server/panel/vhost/nginx/extension/pre-studio.miemie.co/cloudflare-origin-allowlist.conf
```

It permits loopback traffic and Cloudflare's published proxy networks, then
denies all other direct requests to the `pre-studio.miemie.co` server block.
The existing `/.well-known` location in the aaPanel main vhost remains more
specific and continues to support certificate validation.

Before updating or reinstalling the file:

1. Compare the CIDRs with Cloudflare's current IPv4 and IPv6 lists.
2. Test the complete Nginx configuration.
3. Reload Nginx only after the test passes.
4. Verify public Cloudflare access returns `200`, direct origin access returns
   `403`, and a nonexistent `/.well-known/acme-challenge/*` path returns `404`
   rather than `403`.

Sources:

- <https://www.cloudflare.com/ips-v4>
- <https://www.cloudflare.com/ips-v6>
- <https://developers.cloudflare.com/fundamentals/concepts/cloudflare-ip-addresses/>
