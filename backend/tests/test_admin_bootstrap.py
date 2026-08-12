from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.user import User
from app.services.admin_bootstrap import (
    AdminAlreadyConfigured,
    AdminBootstrapService,
)


@dataclass
class _Status:
    active_admin_count: int
    registration_enabled: bool


class _BootstrapRepository:
    def __init__(self):
        self.users = {}
        self.registration = False
        self.events = []

    def bootstrap_status(self):
        return _Status(
            active_admin_count=sum(
                user.role == "admin" and user.status == "active"
                for user in self.users.values()
            ),
            registration_enabled=self.registration,
        )

    def bootstrap_admin(self, user, event):
        if self.bootstrap_status().active_admin_count:
            existing = self.users.get(user.username)
            if existing and existing.role == "admin":
                return existing, False
            raise AdminAlreadyConfigured("admin_already_configured")
        self.users[user.username] = user
        self.events.append(event)
        return user, True

    def promote_user(self, username, event):
        user = self.users.get(username)
        if user is None:
            return None
        promoted = user.model_copy(update={"role": "admin", "status": "active"})
        self.users[username] = promoted
        self.events.append(event(promoted.id))
        return promoted

    def reset_admin_password(self, username, password_hash, event):
        user = self.users.get(username)
        if user is None or user.role != "admin":
            return None
        reset = user.model_copy(
            update={"password": password_hash, "must_change_password": True}
        )
        self.users[username] = reset
        self.events.append(event(reset.id))
        return reset


def _service(repo, initialized, revoked):
    return AdminBootstrapService(
        repository=repo,
        password_hasher=lambda password: f"hashed:{password}",
        user_data_initializer=initialized.append,
        session_revoker=revoked.append,
    )


def test_bootstrap_status_reports_configuration_and_registration():
    repo = _BootstrapRepository()
    service = _service(repo, [], [])

    assert service.status() == {
        "admin_configured": False,
        "registration_enabled": False,
    }


def test_first_admin_bootstrap_is_explicit_and_idempotent_for_same_username():
    repo = _BootstrapRepository()
    initialized = []
    service = _service(repo, initialized, [])

    first, created = service.bootstrap(
        username="owner",
        password="secure-pass",
        display_name="Owner",
        request_id="cli-bootstrap",
    )
    again, created_again = service.bootstrap(
        username="owner",
        password="different-pass",
        display_name="Owner",
        request_id="cli-bootstrap",
    )

    assert created is True
    assert created_again is False
    assert first.id == again.id
    assert first.role == "admin"
    assert initialized == [first.id]
    assert repo.events[0].actor_user_id == first.id
    assert "secure-pass" not in str(repo.events[0].changes)


def test_bootstrap_rejects_different_admin_after_configuration():
    repo = _BootstrapRepository()
    service = _service(repo, [], [])
    service.bootstrap(username="owner", password="secure-pass")

    with pytest.raises(AdminAlreadyConfigured):
        service.bootstrap(username="other", password="secure-pass")


def test_explicit_legacy_promotion_and_admin_password_reset_revoke_sessions():
    repo = _BootstrapRepository()
    legacy = User(username="legacy", password="old-hash")
    repo.users[legacy.username] = legacy
    revoked = []
    service = _service(repo, [], revoked)

    promoted = service.promote("legacy")
    reset = service.reset_password("legacy", "new-secret")

    assert promoted.role == "admin"
    assert reset.password == "hashed:new-secret"
    assert reset.must_change_password is True
    assert revoked == [legacy.id, legacy.id]
    assert "new-secret" not in str(repo.events[-1].changes)
