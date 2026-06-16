# R58 Connectivity After Direct Rule

## Summary

- Run ID: `r58-after-direct-rule-20260617`
- Scope: full connectivity preflight
- State: `blocked`
- Server state changed: no
- Database business flags changed: no

The user added another local DIRECT rule before this run. The command-line path is still not clean enough for a local-to-server PostgreSQL rollout:

- DNS still returned Clash fake-IP `198.18.0.100`.
- Route to origin IP `47.79.99.190` still used gateway `198.18.0.1` and interface `utun1024`.
- TCP 22 was reachable, but SSH banner exchange timed out.
- Public health timed out after 20 seconds from this client.

## Evidence

- `status.json`
- `results.tsv`
- `dns-a.txt`
- `route-origin.txt`
- `ssh-banner.err`
- `public-health-summary.txt`
- `remediation.md`

## Conclusion

The local Mac still cannot be used as the safe execution point for the staging PostgreSQL sequence. Continue through either:

1. a fully clean local route where network-scope and full preflight both pass, or
2. a server-terminal self-run sequence that executes from `/opt/miemie-pre` directly on the server.
