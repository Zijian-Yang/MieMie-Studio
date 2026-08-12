#!/usr/bin/env python3
"""Verify the platform operations smoke without provider or external OSS calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/platform_ops_smoke.py"


class FakePlatformOpsApi:
    admin_token = "verify-admin-token"
    member_token = "verify-member-token"

    def __init__(self, *, failed_operation: str | None = None):
        self.failed_operation = failed_operation
        self.settings = {
            "registration_enabled": False,
            "backup_enabled": False,
            "backup_schedule": "03:00",
            "backup_retention_days": 30,
            "backup_min_keep": 7,
            "backup_local_subdirectory": "postgres",
            "backup_oss_enabled": False,
            "backup_oss_endpoint": None,
            "backup_oss_bucket_name": None,
            "backup_oss_prefix": "miemie/backups",
            "backup_oss_credentials_configured": False,
            "backup_oss_access_key_id_masked": "",
            "webhook_enabled": False,
            "webhook_configured": False,
            "webhook_url_masked": "",
            "webhook_timeout_seconds": 10,
            "webhook_retry_count": 2,
            "webhook_alert_on_warning": False,
        }
        self.runs = []

    def handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _admin(self):
                return self.headers.get("Authorization") == f"Bearer {api.admin_token}"

            def _member(self):
                return self.headers.get("Authorization") == f"Bearer {api.member_token}"

            def _body(self):
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length) or b"{}")

            def do_GET(self):  # noqa: N802
                path = urlparse(self.path).path
                if path == "/api/health":
                    self._json(200, {"status": "ok", "redis": {"ok": True}, "database": {"ok": True}})
                elif path == "/api/admin/platform-settings" and self._member():
                    self._json(403, {"detail": {"code": "admin_required"}})
                elif path == "/api/admin/platform-settings" and self._admin():
                    self._json(200, api.settings)
                elif path == "/api/admin/backups" and self._admin():
                    self._json(200, {"items": api.runs, "page": 1, "page_size": 100, "total": len(api.runs)})
                else:
                    self._json(401, {"detail": "unauthorized"})

            def do_PATCH(self):  # noqa: N802
                if urlparse(self.path).path == "/api/admin/platform-settings" and self._admin():
                    api.settings.update(self._body())
                    self._json(200, api.settings)
                else:
                    self._json(401, {"detail": "unauthorized"})

            def do_POST(self):  # noqa: N802
                path = urlparse(self.path).path
                operation_type = {
                    "/api/admin/backups": "backup",
                    "/api/admin/backups/test-oss": "oss_test",
                    "/api/admin/alerts/test": "webhook_test",
                }.get(path)
                if not operation_type or not self._admin():
                    self._json(401, {"detail": "unauthorized"})
                    return
                run = {
                    "id": f"verify-{operation_type}",
                    "operation_type": operation_type,
                    "status": "queued",
                    "trigger_source": "manual",
                    "local_status": "pending",
                    "oss_status": "pending",
                    "summary": {},
                    "created_at": "2026-08-12T00:00:00Z",
                    "updated_at": "2026-08-12T00:00:00Z",
                }
                failed = operation_type == api.failed_operation
                api.runs.append({
                    **run,
                    "status": "failed" if failed else "succeeded",
                    "local_status": "failed" if failed else ("succeeded" if operation_type == "backup" else "skipped"),
                    "oss_status": "failed" if failed else ("succeeded" if operation_type == "oss_test" else "skipped"),
                    "error_category": "verify_operation_failed" if failed else None,
                    "sha256": "a" * 64 if operation_type == "backup" else None,
                    "size_bytes": 1024 if operation_type == "backup" else None,
                })
                self._json(202, run)

            def log_message(self, format, *args):  # noqa: A002
                return

        return Handler


def main() -> int:
    source = SCRIPT.read_text(encoding="utf-8")
    for required in (
        "CONFIRM_PLATFORM_OPS_SMOKE",
        "MIEMIE_ADMIN_TOKEN",
        "MIEMIE_MEMBER_TOKEN",
        "settings_masked",
        "provider_calls",
        "secrets_persisted",
    ):
        assert required in source
    lowered = source.lower()
    for forbidden in ("dashscope", "preview-payload", "api_key"):
        assert forbidden not in lowered

    api = FakePlatformOpsApi()
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="miemie-platform-ops-smoke-") as temp_dir:
            artifact = Path(temp_dir)
            result = subprocess.run(
                ["python3", str(SCRIPT)],
                cwd=ROOT,
                env={
                    **os.environ,
                    "CONFIRM_PLATFORM_OPS_SMOKE": "run",
                    "MIEMIE_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
                    "MIEMIE_ADMIN_TOKEN": api.admin_token,
                    "MIEMIE_MEMBER_TOKEN": api.member_token,
                    "PLATFORM_OPS_RUN_BACKUP": "true",
                    "PLATFORM_OPS_RUN_OSS_TEST": "true",
                    "PLATFORM_OPS_RUN_WEBHOOK_TEST": "true",
                    "RUN_ID": "verify-platform-ops-smoke",
                    "ARTIFACT_DIR": str(artifact),
                },
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
            status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
            assert status["state"] == "passed"
            assert status["member_admin_denied"] is True
            assert len(status["operations"]) == 3
            assert status["provider_calls"] == 0
            assert status["secrets_persisted"] is False
            evidence = "\n".join(
                path.read_text(encoding="utf-8")
                for path in artifact.rglob("*")
                if path.is_file()
            )
            for secret in (api.admin_token, api.member_token):
                assert secret not in evidence
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    failed_api = FakePlatformOpsApi(failed_operation="webhook_test")
    failed_server = ThreadingHTTPServer(("127.0.0.1", 0), failed_api.handler())
    failed_thread = threading.Thread(target=failed_server.serve_forever, daemon=True)
    failed_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="miemie-platform-ops-smoke-failure-") as temp_dir:
            artifact = Path(temp_dir)
            result = subprocess.run(
                ["python3", str(SCRIPT)],
                cwd=ROOT,
                env={
                    **os.environ,
                    "CONFIRM_PLATFORM_OPS_SMOKE": "run",
                    "MIEMIE_BASE_URL": f"http://127.0.0.1:{failed_server.server_address[1]}",
                    "MIEMIE_ADMIN_TOKEN": failed_api.admin_token,
                    "PLATFORM_OPS_RUN_WEBHOOK_TEST": "true",
                    "RUN_ID": "verify-platform-ops-smoke-failure",
                    "ARTIFACT_DIR": str(artifact),
                },
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 1
            status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
            assert status["state"] == "failed"
            assert status["reason"] == "webhook_test_failed:verify_operation_failed"
    finally:
        failed_server.shutdown()
        failed_thread.join(timeout=5)
        failed_server.server_close()

    print("platform operations smoke verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
