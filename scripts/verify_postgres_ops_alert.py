#!/usr/bin/env python3
"""Verify PostgreSQL operational alert helper without sending network traffic."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_ops_alert.sh"


def run_alert(temp: Path, extra_env: dict[str, str] | None = None) -> str:
    artifact = temp / f"artifact-{len(list(temp.iterdir()))}"
    shell = (
        f"source {SCRIPT}; "
        "postgres_ops_send_alert critical verify_alert blocked 'synthetic failure' \"$ARTIFACT_DIR\""
    )
    env = {
        **os.environ,
        "RUN_ID": "verify-alert",
        "ARTIFACT_DIR": str(artifact),
        **(extra_env or {}),
    }
    result = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"alert helper failed: {result.returncode}\n{result.stdout}\n{result.stderr}")
    return (artifact / "alerts.tsv").read_text(encoding="utf-8")


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-postgres-alert-") as temp_dir:
        temp = Path(temp_dir)
        no_webhook = run_alert(temp)
        assert "verify_alert" in no_webhook
        assert "skipped\tno_webhook" in no_webhook

        dry_run = run_alert(
            temp,
            {
                "MIEMIE_OPS_ALERT_WEBHOOK_URL": "https://example.invalid/webhook",
                "MIEMIE_OPS_ALERT_DRY_RUN": "true",
            },
        )
        assert "skipped\tdry_run" in dry_run
        assert "example.invalid" not in dry_run

    print("postgres ops alert verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
