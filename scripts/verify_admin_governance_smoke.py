#!/usr/bin/env python3
"""Verify the provider-free administrator governance smoke contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "admin_governance_smoke.py"


class FakeGovernanceApi:
    def __init__(self):
        self.admin_token = "verify-admin-token"
        self.member_token = "verify-member-token"
        self.member_id = "verify-member-id"
        self.password = ""
        self.status = "missing"
        self.deleted = False
        self.audit_actions: list[str] = []

    def handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: object) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Request-ID", "verify-request-id")
                self.end_headers()
                self.wfile.write(body)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length) or b"{}")

            def _admin(self) -> bool:
                return self.headers.get("Authorization") == f"Bearer {api.admin_token}"

            def _member(self) -> bool:
                return self.headers.get("Authorization") == f"Bearer {api.member_token}"

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == "/api/health":
                    self._json(200, {"status": "ok", "redis": {"ok": True}})
                elif path == "/api/bootstrap/status":
                    self._json(200, {"admin_configured": True, "registration_enabled": False})
                elif path == "/api/auth/me" and self._admin():
                    self._json(200, {"id": "verify-admin-id", "role": "admin", "status": "active"})
                elif path == "/api/auth/me" and self._member() and api.status == "active" and not api.deleted:
                    self._json(200, {"id": api.member_id, "role": "member", "status": "active"})
                elif path == "/api/admin/users" and self._member():
                    self._json(403, {"detail": {"code": "admin_required"}})
                elif path == "/api/admin/audit-logs" and self._admin():
                    self._json(200, {
                        "items": [{"action": action} for action in api.audit_actions],
                        "page": 1,
                        "page_size": 100,
                        "total": len(api.audit_actions),
                    })
                else:
                    self._json(401, {"detail": "unauthorized"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                body = self._body()
                if path == "/api/admin/users" and self._admin():
                    api.member_id = "verify-member-id"
                    api.password = body["password"]
                    api.status = "active"
                    api.deleted = False
                    api.audit_actions.append("admin.user.create")
                    self._json(201, {"id": api.member_id, "role": "member", "status": "active"})
                elif path == "/api/auth/login":
                    if not api.deleted and api.status == "active" and body.get("password") == api.password:
                        self._json(200, {"token": api.member_token, "user": {"id": api.member_id}})
                    else:
                        self._json(401, {"detail": "invalid credentials"})
                elif path.endswith("/reset-password") and self._admin():
                    api.password = body["new_password"]
                    api.member_token = "verify-member-token-after-reset"
                    api.audit_actions.append("admin.user.reset_credential")
                    self._json(200, {"id": api.member_id, "role": "member", "status": api.status})
                else:
                    self._json(404, {"detail": "not found"})

            def do_PATCH(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                body = self._body()
                if path == "/api/admin/users/verify-admin-id" and self._admin():
                    self._json(409, {"detail": {"code": "cannot_disable_self"}})
                elif path == f"/api/admin/users/{api.member_id}" and self._admin():
                    api.status = body["status"]
                    api.member_token = f"verify-member-token-{api.status}"
                    api.audit_actions.append("admin.user.update")
                    self._json(200, {"id": api.member_id, "role": "member", "status": api.status})
                else:
                    self._json(404, {"detail": "not found"})

            def do_DELETE(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path == f"/api/admin/users/{api.member_id}" and self._admin():
                    api.deleted = True
                    api.member_token = "verify-member-token-deleted"
                    api.audit_actions.append("admin.user.delete")
                    self._json(200, {"id": api.member_id, "role": "member", "status": "disabled"})
                else:
                    self._json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        return Handler


def main() -> int:
    source = SCRIPT.read_text(encoding="utf-8")
    required = [
        "CONFIRM_ADMIN_GOVERNANCE_SMOKE",
        "MIEMIE_ADMIN_TOKEN",
        "admin_required",
        "cannot_disable_self",
        "admin.user.reset_credential",
        "admin.user.delete",
        "provider_calls",
        "secrets_persisted",
    ]
    for fragment in required:
        assert fragment in source, f"missing smoke contract fragment: {fragment}"
    forbidden = ["dashscope", "preview-payload", "/generate", "api_key"]
    lowered = source.lower()
    for fragment in forbidden:
        assert fragment not in lowered, f"provider operation leaked into smoke: {fragment}"

    api = FakeGovernanceApi()
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="miemie-admin-smoke-") as temp_dir:
            artifact = Path(temp_dir)
            result = subprocess.run(
                ["python3", str(SCRIPT)],
                cwd=ROOT,
                env={
                    **os.environ,
                    "CONFIRM_ADMIN_GOVERNANCE_SMOKE": "run",
                    "MIEMIE_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
                    "MIEMIE_ADMIN_TOKEN": api.admin_token,
                    "RUN_ID": "verify-admin-governance-smoke",
                    "ARTIFACT_DIR": str(artifact),
                },
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"smoke failed:\n{result.stdout}\n{result.stderr}"
            status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
            assert status["state"] == "passed"
            assert status["provider_calls"] == 0
            assert status["secrets_persisted"] is False
            assert status["temporary_user_soft_deleted"] is True
            assert status["member_admin_denied"] is True
            assert status["session_revocation_checks"] == 3
            evidence = "\n".join(
                path.read_text(encoding="utf-8")
                for path in artifact.rglob("*")
                if path.is_file()
            )
            for secret in (
                "verify-admin-token",
                "verify-member-token",
                "verify-member-id",
                api.password,
            ):
                assert secret not in evidence
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    print("admin governance smoke verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
