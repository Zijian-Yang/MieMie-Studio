#!/usr/bin/env python3
"""Verify PostgreSQL ops alert self-test contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_ops_alert_selftest.py"


def run_selftest(artifact: Path, confirm: str = "dry-run") -> tuple[subprocess.CompletedProcess[str], dict]:
    env = {
        **os.environ,
        "RUN_ID": f"verify-postgres-ops-alert-selftest-{confirm}",
        "ARTIFACT_DIR": str(artifact),
        "CONFIRM_POSTGRES_OPS_ALERT_SELFTEST": confirm,
    }
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
    return result, status


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="miemie-alert-selftest-") as temp_dir:
        temp = Path(temp_dir)

        dry_result, dry_status = run_selftest(temp / "dry-run")
        if dry_result.returncode != 0:
            raise AssertionError(f"dry-run failed: {dry_result.returncode}\n{dry_result.stdout}\n{dry_result.stderr}")
        assert dry_status["state"] == "dry_run"
        plan = (temp / "dry-run" / "postgres-ops-alert-selftest-plan.md").read_text(encoding="utf-8")
        assert "127.0.0.1 mock webhook" in plan

        run_result, run_status = run_selftest(temp / "run", "run")
        if run_result.returncode != 0:
            raise AssertionError(f"run failed: {run_result.returncode}\n{run_result.stdout}\n{run_result.stderr}")
        assert run_status["state"] == "passed"
        assert run_status["cases"]["mock_webhook"] == "passed"

        no_webhook = (temp / "run" / "no-webhook" / "alerts.tsv").read_text(encoding="utf-8")
        assert "skipped\tno_webhook" in no_webhook

        dry_run = (temp / "run" / "dry-run" / "alerts.tsv").read_text(encoding="utf-8")
        assert "skipped\tdry_run" in dry_run
        assert "example.invalid" not in dry_run

        mock_alerts = (temp / "run" / "mock-webhook" / "alerts.tsv").read_text(encoding="utf-8")
        assert "sent\twebhook" in mock_alerts
        payload = json.loads((temp / "run" / "mock-webhook" / "received-payload.json").read_text(encoding="utf-8"))
        assert payload["label"] == "postgres_ops_alert_selftest"
        assert payload["run_id"] == "verify-postgres-ops-alert-selftest-run"

    content = SCRIPT.read_text(encoding="utf-8")
    required = [
        "ThreadingHTTPServer((\"127.0.0.1\", 0)",
        "MIEMIE_OPS_ALERT_WEBHOOK_URL",
        "MIEMIE_OPS_ALERT_DRY_RUN",
        "received-payload.json",
        "skipped\\tno_webhook",
        "skipped\\tdry_run",
        "sent\\twebhook",
    ]
    for fragment in required:
        if fragment not in content:
            raise AssertionError(f"missing contract fragment: {fragment}")

    required_no_leak_fragments = [
        "dry_run_url in dry_run",
        "\"MIEMIE_OPS_ALERT_WEBHOOK_URL\": dry_run_url",
    ]
    for fragment in required_no_leak_fragments:
        if fragment not in content:
            raise AssertionError(f"missing no-leak/self-test fragment: {fragment}")

    print("postgres ops alert self-test verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
