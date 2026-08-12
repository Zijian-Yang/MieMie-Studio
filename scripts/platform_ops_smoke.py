#!/usr/bin/env python3
"""Run a secret-safe platform operations smoke against a deployed API."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = os.getenv("RUN_ID", f"platform-ops-smoke-{time.strftime('%Y%m%d%H%M%S')}")
ARTIFACT_DIR = Path(
    os.getenv(
        "ARTIFACT_DIR",
        str(ROOT / "docs/reports/artifacts/2026-08-12-phase-7b-platform-operations/local-smoke"),
    )
)
BASE_URL = os.getenv("MIEMIE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("MIEMIE_ADMIN_TOKEN", "").strip()
MEMBER_TOKEN = os.getenv("MIEMIE_MEMBER_TOKEN", "").strip()
CONFIRM = os.getenv("CONFIRM_PLATFORM_OPS_SMOKE", "dry-run")
RUN_OSS_TEST = os.getenv("PLATFORM_OPS_RUN_OSS_TEST", "false").lower() == "true"
RUN_WEBHOOK_TEST = os.getenv("PLATFORM_OPS_RUN_WEBHOOK_TEST", "false").lower() == "true"
RUN_BACKUP = os.getenv("PLATFORM_OPS_RUN_BACKUP", "false").lower() == "true"


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
    headers = {"Accept": "application/json", "X-Request-ID": f"{RUN_ID}-{secrets.token_hex(4)}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - operator-selected URL
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {}
    except URLError as exc:
        raise SmokeFailure("endpoint_unreachable") from exc


def expect_status(actual: int, expected: int, stage: str) -> None:
    if actual != expected:
        raise SmokeFailure(f"{stage}_unexpected_status")


def detail_code(payload: Any) -> str:
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return str(detail.get("code", "")) if isinstance(detail, dict) else ""


def wait_for_run(run_id: str, timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status, history = request_json(
            "GET",
            "/api/admin/backups",
            token=ADMIN_TOKEN,
            query={"page": 1, "page_size": 100},
        )
        expect_status(status, 200, "operation_history")
        for item in history.get("items", []):
            if isinstance(item, dict) and item.get("id") == run_id:
                if item.get("status") in {"succeeded", "failed"}:
                    return item
                break
        time.sleep(2)
    raise SmokeFailure("operation_timeout")


def safe_run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation_type": run.get("operation_type"),
        "status": run.get("status"),
        "local_status": run.get("local_status"),
        "oss_status": run.get("oss_status"),
        "error_category": run.get("error_category"),
        "has_checksum": bool(run.get("sha256")),
        "size_bytes": run.get("size_bytes"),
    }


def run_smoke() -> dict[str, Any]:
    if not ADMIN_TOKEN:
        raise SmokeFailure("admin_token_missing")

    status, health = request_json("GET", "/api/health")
    expect_status(status, 200, "health")
    if health.get("status") != "ok" or health.get("redis", {}).get("ok") is not True:
        raise SmokeFailure("health_not_ok")
    if health.get("database", {}).get("ok") is not True:
        raise SmokeFailure("database_not_ok")

    status, settings = request_json("GET", "/api/admin/platform-settings", token=ADMIN_TOKEN)
    expect_status(status, 200, "settings_get")
    serialized = json.dumps(settings, ensure_ascii=False).lower()
    for forbidden in (
        "access_key_secret_encrypted",
        "webhook_url_encrypted",
        "platform_encryption_key",
    ):
        if forbidden in serialized:
            raise SmokeFailure("settings_secret_field_exposed")

    status, updated = request_json(
        "PATCH",
        "/api/admin/platform-settings",
        token=ADMIN_TOKEN,
        payload={
            "backup_schedule": settings.get("backup_schedule", "03:00"),
            "backup_retention_days": settings.get("backup_retention_days", 30),
            "backup_min_keep": settings.get("backup_min_keep", 7),
        },
    )
    expect_status(status, 200, "settings_patch")
    if updated.get("backup_schedule") != settings.get("backup_schedule"):
        raise SmokeFailure("settings_round_trip_mismatch")

    member_denied = None
    if MEMBER_TOKEN:
        status, denied = request_json("GET", "/api/admin/platform-settings", token=MEMBER_TOKEN)
        member_denied = status == 403 and detail_code(denied) == "admin_required"
        if not member_denied:
            raise SmokeFailure("member_admin_denial_missing")

    operations: list[dict[str, Any]] = []
    for enabled, path, expected_type in (
        (RUN_WEBHOOK_TEST, "/api/admin/alerts/test", "webhook_test"),
        (RUN_OSS_TEST, "/api/admin/backups/test-oss", "oss_test"),
        (RUN_BACKUP, "/api/admin/backups", "backup"),
    ):
        if not enabled:
            continue
        status, queued = request_json("POST", path, token=ADMIN_TOKEN)
        expect_status(status, 202, f"{expected_type}_queue")
        if queued.get("operation_type") != expected_type or queued.get("status") != "queued":
            raise SmokeFailure(f"{expected_type}_queued_payload_invalid")
        completed = wait_for_run(str(queued["id"]))
        operations.append(safe_run_summary(completed))
        if completed.get("status") != "succeeded":
            category = str(completed.get("error_category") or "operation_failed")
            raise SmokeFailure(f"{expected_type}_failed:{category}")

    return {
        "state": "passed",
        "stage": "complete",
        "health_ok": True,
        "database_ok": True,
        "redis_ok": True,
        "settings_masked": True,
        "settings_round_trip": True,
        "member_admin_denied": member_denied,
        "operations": operations,
        "provider_calls": 0,
        "secrets_persisted": False,
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "plan.md").write_text(
        "# Platform Operations Smoke\n\n"
        "Provider-free health, authorization, masked settings, queue, backup, OSS, and Webhook checks.\n"
        "Tokens, credentials, Webhook URLs, and OSS endpoints are never written to evidence.\n",
        encoding="utf-8",
    )
    if CONFIRM != "run":
        write_json(ARTIFACT_DIR / "status.json", {
            "run_id": RUN_ID,
            "state": "dry_run",
            "stage": "planned",
            "provider_calls": 0,
            "secrets_persisted": False,
        })
        return 0
    try:
        result = run_smoke()
    except SmokeFailure as exc:
        write_json(ARTIFACT_DIR / "status.json", {
            "run_id": RUN_ID,
            "state": "failed",
            "stage": "smoke",
            "reason": str(exc),
            "provider_calls": 0,
            "secrets_persisted": False,
        })
        print(f"platform operations smoke failed: {exc}", file=sys.stderr)
        return 1
    write_json(ARTIFACT_DIR / "status.json", {
        "run_id": RUN_ID,
        **result,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    print(f"platform operations smoke passed; sanitized evidence: {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
