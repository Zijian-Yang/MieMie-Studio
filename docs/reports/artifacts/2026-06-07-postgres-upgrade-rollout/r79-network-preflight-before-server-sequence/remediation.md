# Pre-studio Connectivity Remediation

- Run ID: `r79-network-preflight-before-server-sequence-20260618`
- State: `blocked`
- Host: `pre-studio.miemie.co`
- Origin IP: `47.79.99.190`
- SSH target: `root@47.79.99.190`

- Scope: `network`

## Results

check | state | detail
scope | passed | network
dns | blocked | fake-ip detected
route | blocked | TUN/fake-ip route detected

## Recommended Next Steps

- DNS is returning a Clash fake-IP (`198.18.0.0/15`). Disable TUN/fake-IP for this run, or configure `pre-studio.miemie.co` to bypass proxy DNS. Re-check with `dig +short pre-studio.miemie.co A` until it returns real Cloudflare A records instead of `198.18.*`.
- Route to the origin IP is still going through TUN/fake-IP. Add a direct route/bypass for `47.79.99.190` or temporarily disable Clash TUN, then re-check `route -n get 47.79.99.190` until the interface is the physical network interface, not `utun*`.
- Recommended Clash rule: `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve`. Put it before broad proxy/fake-IP rules and before any Rule Providers that may catch `32.0.0.0/3` or other large IP ranges.
- This was a network-only check. It intentionally stopped before TCP/SSH/public-health validation; run full preflight after DNS and route are clean.

Do not run the remote PostgreSQL sequence until this preflight exits `0`.
