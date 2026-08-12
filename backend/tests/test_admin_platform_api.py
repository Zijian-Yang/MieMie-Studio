from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.dependencies import require_admin
from app.models.user import User
from app.models.platform_operations import MaskedPlatformOperationsSettings


@dataclass
class _AuditPage:
    items: list[dict]
    total: int


class _SettingsRepository:
    def __init__(self):
        self.enabled = False
        self.events = []

    def registration_enabled(self):
        return self.enabled

    def set_registration_enabled(self, enabled, event):
        self.enabled = enabled
        self.events.append(event)
        return enabled


class _OperationsService:
    def __init__(self, settings):
        self.settings = settings

    def get_settings(self):
        return MaskedPlatformOperationsSettings(
            registration_enabled=self.settings.enabled,
            backup_enabled=False,
            backup_schedule="03:00",
            backup_retention_days=30,
            backup_min_keep=7,
            backup_local_subdirectory="postgres",
            backup_oss_enabled=False,
            backup_oss_prefix="miemie/backups",
            backup_oss_credentials_configured=False,
            webhook_enabled=False,
            webhook_configured=False,
            webhook_timeout_seconds=10,
            webhook_retry_count=2,
            webhook_alert_on_warning=False,
        )


class _AuditRepository:
    def list(self, **kwargs):
        return _AuditPage(
            items=[
                {
                    "id": "audit-1",
                    "actor_user_id": "admin-1",
                    "action": "admin.user.update",
                    "target_type": "user",
                    "target_id": "member-1",
                    "request_id": "req-1",
                    "result": "success",
                    "changes": {"status": "disabled"},
                    "created_at": datetime(2026, 8, 12, tzinfo=timezone.utc),
                }
            ],
            total=1,
        )


@pytest.fixture
def platform_api(client, monkeypatch):
    from app.services.user_service import get_user_service

    user_service = get_user_service()
    admin = user_service.register("owner", "admin-pass-123")
    users = user_service._load_users()
    admin.role = "admin"
    user_service._save_user_record(users, admin)
    token, admin = user_service.login("owner", "admin-pass-123")
    client.headers.update({"Authorization": f"Bearer {token}"})
    settings = _SettingsRepository()
    audit = _AuditRepository()
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: admin
    monkeypatch.setattr(
        "app.routers.admin_platform.build_platform_settings_repository",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.routers.admin_platform.build_platform_operations_service",
        lambda: _OperationsService(settings),
    )
    monkeypatch.setattr(
        "app.routers.admin_platform.build_admin_audit_repository",
        lambda: audit,
    )
    yield client, settings
    app.dependency_overrides.pop(require_admin, None)
    client.headers.pop("Authorization", None)


def test_get_and_update_registration_setting_are_typed_and_audited(platform_api):
    client, settings = platform_api

    before = client.get("/api/admin/platform-settings")
    updated = client.put(
        "/api/admin/platform-settings",
        headers={"X-Request-ID": "req-setting"},
        json={"registration_enabled": True},
    )

    assert before.json()["registration_enabled"] is False
    assert before.json()["backup_enabled"] is False
    assert updated.json() == {"registration_enabled": True}
    assert settings.events[0].request_id == "req-setting"
    assert settings.events[0].changes == {"registration_enabled": True}


def test_audit_log_response_is_paginated_and_secret_free(platform_api):
    client, _ = platform_api

    response = client.get("/api/admin/audit-logs?page=1&page_size=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["changes"] == {"status": "disabled"}
    assert "password" not in str(payload).lower()
    assert "token" not in str(payload).lower()
