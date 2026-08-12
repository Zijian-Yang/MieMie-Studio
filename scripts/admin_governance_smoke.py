#!/usr/bin/env python3
"""Run a provider-free administrator and member lifecycle smoke."""

from __future__ import annotations

import json
import os
import secrets
import string
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = os.getenv("RUN_ID", f"admin-governance-smoke-{time.strftime('%Y%m%d%H%M%S')}")
ARTIFACT_DIR = Path(
    os.getenv(
        "ARTIFACT_DIR",
        str(ROOT / "docs/reports/artifacts/2026-08-12-phase-7a-admin-governance/local-smoke"),
    )
)
BASE_URL = os.getenv("MIEMIE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("MIEMIE_ADMIN_TOKEN", "").strip()
CONFIRM = os.getenv("CONFIRM_ADMIN_GOVERNANCE_SMOKE", "dry-run")


class SmokeFailure(RuntimeError):
    pass


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "X-Request-ID": f"{RUN_ID}-{secrets.token_hex(4)}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - operator-selected URL
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read()
        try:
            response_body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            response_body = {}
        return exc.code, response_body
    except URLError as exc:
        raise SmokeFailure("endpoint_unreachable") from exc


def expect_status(actual: int, expected: int, stage: str) -> None:
    if actual != expected:
        raise SmokeFailure(f"{stage}_unexpected_status")


def detail_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    detail = payload.get("detail")
    return detail.get("code", "") if isinstance(detail, dict) else ""


def random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "G7!" + "".join(secrets.choice(alphabet) for _ in range(21))


def write_plan() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "plan.md").write_text(
        "\n".join(
            [
                "# Admin Governance Smoke",
                "",
                "This provider-free smoke uses only health, auth, administrator user, settings, and audit APIs.",
                "It creates one synthetic member, proves authorization and session revocation, then soft-deletes it.",
                "Credentials, tokens, usernames, user identifiers, and request bodies are never written to artifacts.",
                "",
                "Execution requires `CONFIRM_ADMIN_GOVERNANCE_SMOKE=run` and an in-memory `MIEMIE_ADMIN_TOKEN`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_smoke() -> dict[str, Any]:
    if not ADMIN_TOKEN:
        raise SmokeFailure("admin_token_missing")

    status, health = request_json("GET", "/api/health")
    expect_status(status, 200, "health")
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise SmokeFailure("health_not_ok")

    status, bootstrap = request_json("GET", "/api/bootstrap/status")
    expect_status(status, 200, "bootstrap_status")
    if not isinstance(bootstrap, dict) or not bootstrap.get("admin_configured"):
        raise SmokeFailure("administrator_not_configured")

    status, administrator = request_json("GET", "/api/auth/me", token=ADMIN_TOKEN)
    expect_status(status, 200, "administrator_session")
    if not isinstance(administrator, dict) or administrator.get("role") != "admin":
        raise SmokeFailure("administrator_role_missing")
    administrator_id = str(administrator["id"])

    suffix = secrets.token_hex(6)
    username = f"admin_smoke_{suffix}"
    first_password = random_password()
    second_password = random_password()

    status, member = request_json(
        "POST",
        "/api/admin/users",
        token=ADMIN_TOKEN,
        payload={
            "username": username,
            "password": first_password,
            "display_name": "Admin governance smoke",
            "role": "member",
            "must_change_password": False,
        },
    )
    expect_status(status, 201, "create_member")
    if not isinstance(member, dict) or member.get("role") != "member":
        raise SmokeFailure("created_member_invalid")
    member_id = str(member["id"])

    status, login = request_json(
        "POST", "/api/auth/login", payload={"username": username, "password": first_password}
    )
    expect_status(status, 200, "member_login")
    member_token = str(login["token"])

    status, denied = request_json("GET", "/api/admin/users", token=member_token)
    if status != 403 or detail_code(denied) != "admin_required":
        raise SmokeFailure("member_admin_denial_missing")

    status, _ = request_json(
        "POST",
        f"/api/admin/users/{member_id}/reset-password",
        token=ADMIN_TOKEN,
        payload={"new_password": second_password, "must_change_password": False},
    )
    expect_status(status, 200, "reset_member_password")
    status, _ = request_json("GET", "/api/auth/me", token=member_token)
    expect_status(status, 401, "reset_session_revocation")

    status, login = request_json(
        "POST", "/api/auth/login", payload={"username": username, "password": second_password}
    )
    expect_status(status, 200, "member_relogin")
    member_token = str(login["token"])

    status, _ = request_json(
        "PATCH",
        f"/api/admin/users/{member_id}",
        token=ADMIN_TOKEN,
        payload={"status": "disabled"},
    )
    expect_status(status, 200, "disable_member")
    status, _ = request_json("GET", "/api/auth/me", token=member_token)
    expect_status(status, 401, "disable_session_revocation")
    status, _ = request_json(
        "POST", "/api/auth/login", payload={"username": username, "password": second_password}
    )
    expect_status(status, 401, "disabled_login_denial")

    status, _ = request_json(
        "PATCH",
        f"/api/admin/users/{member_id}",
        token=ADMIN_TOKEN,
        payload={"status": "active"},
    )
    expect_status(status, 200, "enable_member")
    status, login = request_json(
        "POST", "/api/auth/login", payload={"username": username, "password": second_password}
    )
    expect_status(status, 200, "enabled_member_login")
    member_token = str(login["token"])

    status, _ = request_json(
        "DELETE", f"/api/admin/users/{member_id}", token=ADMIN_TOKEN
    )
    expect_status(status, 200, "delete_member")
    status, _ = request_json("GET", "/api/auth/me", token=member_token)
    expect_status(status, 401, "delete_session_revocation")
    status, _ = request_json(
        "POST", "/api/auth/login", payload={"username": username, "password": second_password}
    )
    expect_status(status, 401, "deleted_login_denial")

    status, conflict = request_json(
        "PATCH",
        f"/api/admin/users/{administrator_id}",
        token=ADMIN_TOKEN,
        payload={"status": "disabled"},
    )
    if status != 409 or detail_code(conflict) != "cannot_disable_self":
        raise SmokeFailure("self_disable_protection_missing")

    status, audit = request_json(
        "GET",
        "/api/admin/audit-logs",
        token=ADMIN_TOKEN,
        query={"page": 1, "page_size": 100},
    )
    expect_status(status, 200, "audit_list")
    actions = {
        str(item.get("action"))
        for item in audit.get("items", [])
        if isinstance(item, dict)
    }
    required_actions = {
        "admin.user.create",
        "admin.user.update",
        "admin.user.reset_credential",
        "admin.user.delete",
    }
    if not required_actions.issubset(actions):
        raise SmokeFailure("audit_actions_incomplete")

    return {
        "state": "passed",
        "stage": "complete",
        "health_ok": True,
        "admin_configured": True,
        "registration_enabled": bool(bootstrap.get("registration_enabled")),
        "member_admin_denied": True,
        "session_revocation_checks": 3,
        "disabled_login_denied": True,
        "deleted_login_denied": True,
        "self_disable_protected": True,
        "audit_action_types_verified": len(required_actions),
        "temporary_user_soft_deleted": True,
        "business_data_preserved_by_policy": True,
        "provider_calls": 0,
        "secrets_persisted": False,
    }


def main() -> int:
    write_plan()
    if CONFIRM != "run":
        write_json(
            ARTIFACT_DIR / "status.json",
            {
                "run_id": RUN_ID,
                "state": "dry_run",
                "stage": "planned",
                "provider_calls": 0,
                "secrets_persisted": False,
            },
        )
        print(f"admin governance smoke plan written to {ARTIFACT_DIR}")
        return 0

    try:
        result = run_smoke()
    except SmokeFailure as exc:
        write_json(
            ARTIFACT_DIR / "status.json",
            {
                "run_id": RUN_ID,
                "state": "failed",
                "stage": "smoke",
                "reason": str(exc),
                "provider_calls": 0,
                "secrets_persisted": False,
            },
        )
        print(f"admin governance smoke failed: {exc}", file=sys.stderr)
        return 1

    write_json(
        ARTIFACT_DIR / "status.json",
        {
            "run_id": RUN_ID,
            **result,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    (ARTIFACT_DIR / "summary.md").write_text(
        "\n".join(
            [
                "# Admin Governance Smoke Result",
                "",
                "- Result: passed",
                "- Temporary member: soft-deleted",
                "- Member administrator access: denied",
                "- Session revocation checks: 3/3",
                "- Self-disable protection: passed",
                "- Audit action types: 4/4",
                "- Provider calls: 0",
                "- Persisted secrets: no",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"admin governance smoke passed; sanitized evidence: {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
