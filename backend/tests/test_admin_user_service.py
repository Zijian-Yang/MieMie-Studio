from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.user import User
from app.services.admin_user_service import (
    AdminUserConflict,
    AdminUserService,
    DuplicateUsername,
)


@dataclass
class _Page:
    items: list[User]
    total: int


class _AdminRepository:
    def __init__(self, *users: User):
        self.users = {user.id: user for user in users}
        self.events = []
        self.last_list_args = None
        self.conflict_code = None

    def list_users(self, **kwargs):
        self.last_list_args = kwargs
        return _Page(items=list(self.users.values()), total=len(self.users))

    def create_user(self, user, event):
        if any(current.username == user.username for current in self.users.values()):
            raise DuplicateUsername(user.username)
        self.users[user.id] = user
        self.events.append(event)
        return user

    def update_user(self, user_id, changes, event):
        if self.conflict_code:
            raise AdminUserConflict(self.conflict_code)
        user = self.users[user_id].model_copy(update=changes)
        self.users[user_id] = user
        self.events.append(event)
        return user

    def reset_password(self, user_id, password_hash, must_change_password, event):
        user = self.users[user_id].model_copy(
            update={
                "password": password_hash,
                "must_change_password": must_change_password,
            }
        )
        self.users[user_id] = user
        self.events.append(event)
        return user

    def soft_delete_user(self, user_id, event):
        self.events.append(event)
        return self.users.pop(user_id)


def _user(username: str, *, role: str = "member", status: str = "active") -> User:
    return User(username=username, password="stored-hash", role=role, status=status)


def _service(repo, revoked, ensured=None):
    ensured_target = ensured if ensured is not None else []
    return AdminUserService(
        repository=repo,
        password_hasher=lambda password: f"hashed:{password}",
        session_revoker=revoked.append,
        user_data_initializer=ensured_target.append,
    )


def test_list_users_passes_pagination_and_filters():
    admin = _user("admin", role="admin")
    repo = _AdminRepository(admin)
    service = _service(repo, [])

    page = service.list_users(page=2, page_size=25, query="ali", role="member", status="active")

    assert page.total == 1
    assert repo.last_list_args == {
        "page": 2,
        "page_size": 25,
        "query": "ali",
        "role": "member",
        "status": "active",
    }


def test_create_user_hashes_password_initializes_data_and_audits_without_secret():
    admin = _user("admin", role="admin")
    repo = _AdminRepository(admin)
    revoked = []
    ensured = []
    service = _service(repo, revoked, ensured)

    created = service.create_user(
        actor=admin,
        username="member",
        password="temporary-secret",
        display_name="Member",
        role="member",
        must_change_password=True,
        request_id="req-create",
    )

    assert created.password == "hashed:temporary-secret"
    assert created.must_change_password is True
    assert ensured == [created.id]
    assert revoked == []
    assert repo.events[0].action == "admin.user.create"
    assert repo.events[0].request_id == "req-create"
    assert "password" not in str(repo.events[0].changes).lower()
    assert "temporary-secret" not in str(repo.events[0].changes)


def test_create_user_maps_duplicate_username():
    admin = _user("admin", role="admin")
    repo = _AdminRepository(admin, _user("member"))
    service = _service(repo, [])

    with pytest.raises(DuplicateUsername):
        service.create_user(actor=admin, username="member", password="pass1234")


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"role": "member"}, "cannot_demote_self"),
        ({"status": "disabled"}, "cannot_disable_self"),
    ],
)
def test_update_rejects_self_security_changes(changes, code):
    admin = _user("admin", role="admin")
    repo = _AdminRepository(admin)
    service = _service(repo, [])

    with pytest.raises(AdminUserConflict, match=code):
        service.update_user(actor=admin, user_id=admin.id, **changes)

    assert repo.events == []


def test_update_propagates_transaction_safe_last_admin_conflict():
    admin = _user("admin", role="admin")
    repo = _AdminRepository(admin)
    repo.conflict_code = "last_active_admin"
    service = _service(repo, [])

    with pytest.raises(AdminUserConflict, match="last_active_admin"):
        service.update_user(actor=_user("other-admin", role="admin"), user_id=admin.id, role="member")


def test_security_update_revokes_sessions_and_audits_changed_fields_only():
    admin = _user("admin", role="admin")
    member = _user("member")
    repo = _AdminRepository(admin, member)
    revoked = []
    service = _service(repo, revoked)

    updated = service.update_user(
        actor=admin,
        user_id=member.id,
        display_name="Renamed",
        status="disabled",
        request_id="req-update",
    )

    assert updated.display_name == "Renamed"
    assert updated.status == "disabled"
    assert revoked == [member.id]
    assert set(repo.events[0].changes) == {"display_name", "status"}


def test_reset_password_is_sanitized_and_revokes_sessions():
    admin = _user("admin", role="admin")
    member = _user("member")
    repo = _AdminRepository(admin, member)
    revoked = []
    service = _service(repo, revoked)

    reset = service.reset_password(
        actor=admin,
        user_id=member.id,
        new_password="new-secret",
        must_change_password=True,
        request_id="req-reset",
    )

    assert reset.password == "hashed:new-secret"
    assert reset.must_change_password is True
    assert revoked == [member.id]
    event_text = str(repo.events[0].changes)
    assert "new-secret" not in event_text
    assert "hashed:" not in event_text
    assert "password" not in event_text.lower()


def test_delete_rejects_self_and_soft_deletes_target_with_session_revocation():
    admin = _user("admin", role="admin")
    member = _user("member")
    repo = _AdminRepository(admin, member)
    revoked = []
    service = _service(repo, revoked)

    with pytest.raises(AdminUserConflict, match="cannot_delete_self"):
        service.delete_user(actor=admin, user_id=admin.id)

    deleted = service.delete_user(actor=admin, user_id=member.id, request_id="req-delete")

    assert deleted.id == member.id
    assert member.id not in repo.users
    assert revoked == [member.id]
    assert repo.events[0].action == "admin.user.delete"
