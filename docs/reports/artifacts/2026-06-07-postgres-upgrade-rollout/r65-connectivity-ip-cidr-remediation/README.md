# R65 Connectivity IP-CIDR Remediation

Date: 2026-06-17

## Summary

After adding another local direct rule, the operator Mac command-line path is still not clean enough to run remote PostgreSQL automation.

- DNS still returns Clash fake-IP `198.18.0.124`.
- Route to `47.79.99.190` still goes through `gateway 198.18.0.1` and `interface utun1024`.
- The route detail shows the wide TUN catch-all range `32.0.0.0/3`, so the host-specific source IP route is not winning.
- `remediation.md` now gives the exact Clash rule to try: `IP-CIDR,47.79.99.190/32,DIRECT,no-resolve`, placed before broad proxy/fake-IP rules and Rule Providers.

## Decision

Do not run the local remote wrapper until `MIEMIE_PREFLIGHT_SCOPE=network scripts/pre_studio_connectivity_preflight.sh` exits `0`.

Use the server fallback from `/opt/miemie-pre` if local TUN/fake-IP remains active.
