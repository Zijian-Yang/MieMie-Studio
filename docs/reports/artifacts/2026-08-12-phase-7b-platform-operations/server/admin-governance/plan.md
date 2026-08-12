# Admin Governance Smoke

This provider-free smoke uses only health, auth, administrator user, settings, and audit APIs.
It creates one synthetic member, proves authorization and session revocation, then soft-deletes it.
Credentials, tokens, usernames, user identifiers, and request bodies are never written to artifacts.

Execution requires `CONFIRM_ADMIN_GOVERNANCE_SMOKE=run` and an in-memory `MIEMIE_ADMIN_TOKEN`.
