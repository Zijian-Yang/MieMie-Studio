from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.dependencies import require_admin
from app.models.user import User
from app.repositories.platform_admin import AdminUserNotFound, DuplicateUsername
from app.services.admin_user_service import AdminUserConflict


@dataclass
class _Page:
    items: list[User]
    total: int


class _AdminService:
    def __init__(self, admin):
        self.admin = admin
        self.member = User(username="member", password="private-hash")
        self.calls = []
        self.error = None

    def _raise(self):
        if self.error:
            raise self.error

    def list_users(self, **kwargs):
        self.calls.append(("list", kwargs))
        return _Page([self.admin, self.member], 2)

    def create_user(self, **kwargs):
        self._raise()
        self.calls.append(("create", kwargs))
        return self.member

    def update_user(self, **kwargs):
        self._raise()
        self.calls.append(("update", kwargs))
        return self.member.model_copy(update={"display_name": kwargs.get("display_name")})

    def reset_password(self, **kwargs):
        self._raise()
        self.calls.append(("reset", kwargs))
        return self.member.model_copy(update={"must_change_password": True})

    def delete_user(self, **kwargs):
        self._raise()
        self.calls.append(("delete", kwargs))
        return self.member


@pytest.fixture
def admin_api(client, monkeypatch):
    from app.services.user_service import get_user_service

    user_service = get_user_service()
    admin = user_service.register("owner", "admin-pass-123")
    users = user_service._load_users()
    admin.role = "admin"
    user_service._save_user_record(users, admin)
    token, admin = user_service.login("owner", "admin-pass-123")
    client.headers.update({"Authorization": f"Bearer {token}"})
    service = _AdminService(admin)
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: admin
    monkeypatch.setattr("app.routers.admin_users.build_admin_user_service", lambda: service)
    yield client, service, admin
    app.dependency_overrides.pop(require_admin, None)
    client.headers.pop("Authorization", None)


def test_user_list_is_paginated_and_never_exposes_password(admin_api):
    client, service, _ = admin_api

    response = client.get(
        "/api/admin/users?page=2&page_size=25&query=mem&role=member&status=active"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 25
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert all("password" not in item for item in payload["items"])
    assert "admin-private-hash" not in str(payload)
    assert "private-hash" not in str(payload)
    assert service.calls[0][1]["query"] == "mem"


def test_create_update_reset_and_delete_use_actor_and_request_id(admin_api):
    client, service, admin = admin_api

    create = client.post(
        "/api/admin/users",
        headers={"X-Request-ID": "req-create"},
        json={"username": "member", "password": "temporary-pass", "role": "member"},
    )
    update = client.patch(
        f"/api/admin/users/{service.member.id}",
        headers={"X-Request-ID": "req-update"},
        json={"display_name": "Renamed"},
    )
    reset = client.post(
        f"/api/admin/users/{service.member.id}/reset-password",
        headers={"X-Request-ID": "req-reset"},
        json={"new_password": "replacement-pass", "must_change_password": True},
    )
    delete = client.delete(
        f"/api/admin/users/{service.member.id}",
        headers={"X-Request-ID": "req-delete"},
    )

    assert [response.status_code for response in (create, update, reset, delete)] == [
        201,
        200,
        200,
        200,
    ]
    assert all(call[1]["actor"].id == admin.id for call in service.calls)
    assert [call[1]["request_id"] for call in service.calls] == [
        "req-create",
        "req-update",
        "req-reset",
        "req-delete",
    ]
    assert "private-hash" not in str([create.json(), update.json(), reset.json(), delete.json()])


@pytest.mark.parametrize(
    "error,status,code",
    [
        (DuplicateUsername("member"), 409, "duplicate_username"),
        (AdminUserConflict("last_active_admin"), 409, "last_active_admin"),
        (AdminUserNotFound("missing"), 404, "user_not_found"),
    ],
)
def test_mutation_errors_have_stable_codes(admin_api, error, status, code):
    client, service, _ = admin_api
    service.error = error

    response = client.patch(f"/api/admin/users/{service.member.id}", json={"status": "disabled"})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_unauthenticated_request_cannot_access_admin_api(client):
    assert client.get("/api/admin/users").status_code == 401


def test_authenticated_member_receives_admin_required(client):
    from app.services.user_service import get_user_service

    service = get_user_service()
    service.register("ordinary-member", "member-pass-123")
    token, _ = service.login("ordinary-member", "member-pass-123")

    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_required"
