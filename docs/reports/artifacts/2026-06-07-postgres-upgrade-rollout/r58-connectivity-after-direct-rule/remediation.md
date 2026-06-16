# Pre-studio Connectivity Remediation

- Run ID: `r58-after-direct-rule-20260617`
- State: `blocked`
- Host: `pre-studio.miemie.co`
- Origin IP: `47.79.99.190`
- SSH target: `root@47.79.99.190`

- Scope: `full`

## Results

check | state | detail
scope | passed | full
dns | blocked | fake-ip detected
route | blocked | TUN/fake-ip route detected
tcp_ssh | passed | tcp 22 reachable
ssh_banner | blocked | Connection timed out during banner exchange
public_health | failed | curl failed: curl: (28) Operation timed out after 20009 milliseconds with 0 bytes received

## Recommended Next Steps

- DNS is returning a Clash fake-IP (`198.18.0.0/15`). Disable TUN/fake-IP for this run, or configure `pre-studio.miemie.co` to bypass proxy DNS. Re-check with `dig +short pre-studio.miemie.co A` until it returns real Cloudflare A records instead of `198.18.*`.
- Route to the origin IP is still going through TUN/fake-IP. Add a direct route/bypass for `47.79.99.190` or temporarily disable Clash TUN, then re-check `route -n get 47.79.99.190` until the interface is the physical network interface, not `utun*`.
- TCP 22 is reachable but SSH banner did not complete. After DNS/route are clean, retry SSH. If it still blocks, check Alibaba Cloud security group, server firewall, sshd limits, and `/var/log/auth.log` on the origin host.
- Public health timed out or failed from this client. Once DNS/route are clean, retry `curl --noproxy "*" -k -sS -D - -o /tmp/pre-studio-health.json --connect-timeout 10 --max-time 20 https://pre-studio.miemie.co/api/health`. If only this local network fails, verify from a target-market VPS or the server itself before changing application code.

Do not run the remote PostgreSQL sequence until this preflight exits `0`.
