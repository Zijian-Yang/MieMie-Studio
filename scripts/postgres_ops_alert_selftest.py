#!/usr/bin/env python3
"""Run a local-only PostgreSQL ops alert webhook self-test."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
ALERT_HELPER = ROOT_DIR / "scripts" / "postgres_ops_alert.sh"


def env_value(name: str, default: str) -> str:
    return os.environ.get(name, default)


RUN_ID = env_value("RUN_ID", f"postgres-ops-alert-selftest-{time.strftime('%Y%m%d%H%M%S')}")
ARTIFACT_DIR = Path(env_value("ARTIFACT_DIR", str(ROOT_DIR / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r124-postgres-ops-alert-selftest")))
CONFIRM = env_value("CONFIRM_POSTGRES_OPS_ALERT_SELFTEST", "dry-run")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_plan() -> None:
    plan = ARTIFACT_DIR / "postgres-ops-alert-selftest-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "\n".join(
            [
                "# PostgreSQL Ops Alert Self-Test",
                "",
                "Default mode is dry-run.",
                "",
                "Run local-only webhook delivery self-test with:",
                "",
                "```bash",
                "CONFIRM_POSTGRES_OPS_ALERT_SELFTEST=run python3 scripts/postgres_ops_alert_selftest.py",
                "```",
                "",
                "The run mode:",
                "",
                "- checks no-webhook behavior writes `skipped/no_webhook`;",
                "- checks dry-run behavior writes `skipped/dry_run` and does not leak the webhook URL;",
                "- starts a 127.0.0.1 mock webhook and verifies a real curl POST is sent;",
                "- stores only the received synthetic payload and alerts.tsv summaries.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_status(state: str, stage: str, reason: str = "", extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "run_id": RUN_ID,
        "state": state,
        "stage": stage,
        "reason": reason,
        "artifact_dir": str(ARTIFACT_DIR),
        "confirm": CONFIRM,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        payload.update(extra)
    write_json(ARTIFACT_DIR / "status.json", payload)


def run_alert_case(case: str, extra_env: dict[str, str]) -> str:
    case_dir = ARTIFACT_DIR / case
    case_dir.mkdir(parents=True, exist_ok=True)
    shell = (
        f"source {shlex.quote(str(ALERT_HELPER))}; "
        "postgres_ops_send_alert critical postgres_ops_alert_selftest blocked "
        "'synthetic alert self-test' \"$ARTIFACT_DIR\""
    )
    env = {
        **os.environ,
        "RUN_ID": RUN_ID,
        "ARTIFACT_DIR": str(case_dir),
        **extra_env,
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
        raise RuntimeError(f"alert case {case} failed: {result.returncode}\n{result.stdout}\n{result.stderr}")
    alerts_path = case_dir / "alerts.tsv"
    if not alerts_path.exists():
        raise RuntimeError(f"alert case {case} did not write {alerts_path}")
    return alerts_path.read_text(encoding="utf-8")


def run_mock_webhook_case() -> dict[str, Any]:
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received.append(json.loads(body.decode("utf-8")))
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/alert"
        alerts = run_alert_case(
            "mock-webhook",
            {
                "MIEMIE_OPS_ALERT_WEBHOOK_URL": url,
                "MIEMIE_OPS_ALERT_DRY_RUN": "false",
            },
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    if "sent\twebhook" not in alerts:
        raise RuntimeError("mock webhook case did not record sent/webhook")
    if len(received) != 1:
        raise RuntimeError(f"expected one mock webhook payload, got {len(received)}")
    payload = received[0]
    required = {
        "run_id": RUN_ID,
        "label": "postgres_ops_alert_selftest",
        "severity": "critical",
        "state": "blocked",
        "reason": "synthetic alert self-test",
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"mock payload {key} mismatch: expected {expected!r}, got {payload.get(key)!r}")
    write_json(ARTIFACT_DIR / "mock-webhook" / "received-payload.json", payload)
    return payload


def run_selftest() -> None:
    write_plan()
    if CONFIRM != "run":
        write_status("dry_run", "planned", "set CONFIRM_POSTGRES_OPS_ALERT_SELFTEST=run to execute local-only alert self-test")
        print(f"dry-run alert self-test plan written to {ARTIFACT_DIR / 'postgres-ops-alert-selftest-plan.md'}")
        return

    no_webhook = run_alert_case("no-webhook", {})
    if "skipped\tno_webhook" not in no_webhook:
        raise RuntimeError("no-webhook case did not record skipped/no_webhook")

    dry_run_url = "https://example.invalid/postgres-ops-alert-selftest"
    dry_run = run_alert_case(
        "dry-run",
        {
            "MIEMIE_OPS_ALERT_WEBHOOK_URL": dry_run_url,
            "MIEMIE_OPS_ALERT_DRY_RUN": "true",
        },
    )
    if "skipped\tdry_run" not in dry_run:
        raise RuntimeError("dry-run case did not record skipped/dry_run")
    if dry_run_url in dry_run:
        raise RuntimeError("dry-run alerts.tsv leaked webhook URL")

    payload = run_mock_webhook_case()
    write_status(
        "passed",
        "done",
        "",
        {
            "cases": {
                "no_webhook": "passed",
                "dry_run": "passed",
                "mock_webhook": "passed",
            },
            "mock_payload_keys": sorted(payload.keys()),
        },
    )
    print(json.dumps(json.loads((ARTIFACT_DIR / "status.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2))


def main() -> int:
    try:
        run_selftest()
        return 0
    except Exception as exc:  # noqa: BLE001
        write_status("blocked", "failed", str(exc))
        print(f"postgres ops alert self-test blocked: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
