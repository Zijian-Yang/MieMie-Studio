# PostgreSQL Ops Alert Self-Test

Default mode is dry-run.

Run local-only webhook delivery self-test with:

```bash
CONFIRM_POSTGRES_OPS_ALERT_SELFTEST=run python3 scripts/postgres_ops_alert_selftest.py
```

The run mode:

- checks no-webhook behavior writes `skipped/no_webhook`;
- checks dry-run behavior writes `skipped/dry_run` and does not leak the webhook URL;
- starts a 127.0.0.1 mock webhook and verifies a real curl POST is sent;
- stores only the received synthetic payload and alerts.tsv summaries.
