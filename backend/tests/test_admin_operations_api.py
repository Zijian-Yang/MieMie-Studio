from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.dependencies import require_admin
from app.models.platform_operations import (
    MaskedPlatformOperationsSettings,
    OperationRun,
    OperationRunPage,
)
from app.models.user import User


def _settings():
    return MaskedPlatformOperationsSettings(
        registration_enabled=False,
        backup_enabled=True,
        backup_schedule="03:00",
        backup_retention_days=30,
        backup_min_keep=7,
        backup_local_subdirectory="postgres",
        backup_oss_enabled=True,
        backup_oss_endpoint="https://oss-cn-test.aliyuncs.com",
        backup_oss_bucket_name="platform-backups",
        backup_oss_prefix="miemie/backups",
        backup_oss_credentials_configured=True,
        backup_oss_access_key_id_masked="LTA********ey",
        webhook_enabled=True,
        webhook_configured=True,
        webhook_url_masked="htt************************te",
        webhook_timeout_seconds=10,
        webhook_retry_count=2,
        webhook_alert_on_warning=False,
    )


def _run(operation_type="backup", status="queued"):
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    return OperationRun(
        id=f"run-{operation_type}",
        operation_type=operation_type,
        status=status,
        trigger_source="manual",
        requested_by="admin-1",
        created_at=now,
        updated_at=now,
    )


class _OperationsService:
    def __init__(self):
        self.settings = _settings()
        self.patches = []
        self.queued = []
        self.list_calls = []
        self.claimed = []
        self.failed = []

    def get_settings(self):
        return self.settings

    def update_settings(self, *, actor, patch, request_id=None):
        self.patches.append((actor, patch, request_id))
        values = self.settings.model_dump()
        for name in patch.model_fields_set:
            if name in values and getattr(patch, name) is not None:
                values[name] = getattr(patch, name)
        self.settings = MaskedPlatformOperationsSettings(**values)
        return self.settings

    def queue_operation(
        self,
        *,
        operation_type,
        source,
        actor_id=None,
        idempotency_key=None,
    ):
        self.queued.append(
            {
                "operation_type": operation_type,
                "source": source,
                "actor_id": actor_id,
                "idempotency_key": idempotency_key,
            }
        )
        return _run(operation_type).model_copy(update={"requested_by": actor_id}), True

    def list_runs(self, **kwargs):
        self.list_calls.append(kwargs)
        return OperationRunPage(items=[_run(kwargs.get("operation_type") or "backup")], total=1)

    def claim_run(self, run_id):
        self.claimed.append(run_id)
        return _run().model_copy(update={"id": run_id, "status": "running"})

    def fail_run(self, run_id, *, error_category, **values):
        self.failed.append((run_id, error_category, values))
        return _run().model_copy(update={"id": run_id, "status": "failed"})


@pytest.fixture
def operations_api(client, monkeypatch):
    from app.services.user_service import get_user_service

    user_service = get_user_service()
    admin = user_service.register("ops-admin", "admin-pass-123")
    users = user_service._load_users()
    admin.role = "admin"
    user_service._save_user_record(users, admin)
    token, admin = user_service.login("ops-admin", "admin-pass-123")
    client.headers.update({"Authorization": f"Bearer {token}"})
    service = _OperationsService()
    dispatched = []
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: admin
    monkeypatch.setattr(
        "app.routers.admin_platform.build_platform_operations_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "app.routers.admin_platform.dispatch_ops_operation",
        lambda run: dispatched.append(run),
    )
    yield client, service, dispatched
    app.dependency_overrides.pop(require_admin, None)
    client.headers.pop("Authorization", None)


def test_get_settings_is_masked_and_never_exposes_secret_fields(operations_api):
    client, _, _ = operations_api

    response = client.get("/api/admin/platform-settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backup_oss_credentials_configured"] is True
    assert payload["webhook_configured"] is True
    serialized = str(payload).lower()
    for forbidden in (
        "access_key_secret",
        "webhook_url_encrypted",
        "backup_oss_access_key_id_encrypted",
        "private-token",
    ):
        assert forbidden not in serialized


def test_patch_settings_preserves_omitted_secrets_and_carries_request_id(operations_api):
    client, service, _ = operations_api

    response = client.patch(
        "/api/admin/platform-settings",
        headers={"X-Request-ID": "req-ops-settings"},
        json={
            "registration_enabled": True,
            "backup_schedule": "04:30",
            "backup_retention_days": 45,
        },
    )

    assert response.status_code == 200
    assert response.json()["registration_enabled"] is True
    _, patch, request_id = service.patches[0]
    assert patch.model_fields_set == {
        "registration_enabled",
        "backup_schedule",
        "backup_retention_days",
    }
    assert request_id == "req-ops-settings"


@pytest.mark.parametrize(
    "path,operation_type",
    (
        ("/api/admin/backups", "backup"),
        ("/api/admin/backups/test-oss", "oss_test"),
        ("/api/admin/alerts/test", "webhook_test"),
    ),
)
def test_manual_operations_commit_run_then_only_enqueue(operations_api, path, operation_type):
    client, service, dispatched = operations_api

    response = client.post(path)

    assert response.status_code == 202
    assert response.json()["operation_type"] == operation_type
    assert service.queued[-1] == {
        "operation_type": operation_type,
        "source": "manual",
        "actor_id": response.json()["requested_by"],
        "idempotency_key": None,
    }
    assert dispatched[-1].id == f"run-{operation_type}"


def test_operation_history_is_paginated_and_filterable(operations_api):
    client, service, _ = operations_api

    response = client.get(
        "/api/admin/backups?page=2&page_size=10&operation_type=webhook_test&status=failed"
    )

    assert response.status_code == 200
    assert response.json()["page"] == 2
    assert response.json()["total"] == 1
    assert service.list_calls == [
        {
            "page": 2,
            "page_size": 10,
            "operation_type": "webhook_test",
            "status": "failed",
        }
    ]


def test_invalid_patch_is_rejected_without_service_call(operations_api):
    client, service, _ = operations_api

    response = client.patch(
        "/api/admin/platform-settings",
        json={"backup_schedule": "3:00"},
    )

    assert response.status_code == 422
    assert service.patches == []


def test_queue_dispatch_failure_marks_run_failed_and_returns_stable_error(
    operations_api, monkeypatch
):
    client, service, _ = operations_api
    monkeypatch.setattr(
        "app.routers.admin_platform.dispatch_ops_operation",
        lambda run: (_ for _ in ()).throw(RuntimeError("private broker failure")),
    )

    response = client.post("/api/admin/backups")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ops_queue_unavailable"
    assert service.claimed == ["run-backup"]
    assert service.failed == [
        (
            "run-backup",
            "ops_queue_dispatch_failed",
            {"local_status": "skipped", "oss_status": "skipped"},
        )
    ]
    assert "private broker" not in response.text


def test_member_cannot_read_or_trigger_platform_operations(client):
    from app.services.user_service import get_user_service

    service = get_user_service()
    service.register("ops-member", "member-pass-123")
    token, _ = service.login("ops-member", "member-pass-123")
    headers = {"Authorization": f"Bearer {token}"}

    for method, path in (
        ("get", "/api/admin/platform-settings"),
        ("patch", "/api/admin/platform-settings"),
        ("get", "/api/admin/backups"),
        ("post", "/api/admin/backups"),
        ("post", "/api/admin/backups/test-oss"),
        ("post", "/api/admin/alerts/test"),
    ):
        kwargs = {"headers": headers}
        if method == "patch":
            kwargs["json"] = {"backup_enabled": True}
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "admin_required"


def test_openapi_has_no_database_restore_endpoint_and_no_secret_response_fields(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/admin/backups" in paths
    assert "/api/admin/backups/test-oss" in paths
    assert "/api/admin/alerts/test" in paths
    assert all(
        "restore" not in path
        for path in paths
        if path.startswith("/api/admin/")
    )
    serialized = str(schema["components"]["schemas"])
    assert "backup_oss_access_key_secret_encrypted" not in serialized
    assert "webhook_url_encrypted" not in serialized
