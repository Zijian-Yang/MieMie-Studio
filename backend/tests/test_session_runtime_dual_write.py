import json
from pathlib import Path

import pytest

from app.services.user_service import UserService


class _SessionShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []
        self.deleted_users = []

    def save(self, token, record):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append((token, record))

    def delete(self, token):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append(token)

    def delete_user_sessions(self, user_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted_users.append(user_id)
        return 1


def _user_service(tmp_path) -> UserService:
    service = UserService(data_dir=Path(tmp_path))
    service._redis_sessions = None
    return service


def _enable_dual_write(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "sessions")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "false")


def _read_sessions(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_session_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _SessionShadowRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, user = service.login("alice", "pass123")
    logged_out = service.logout(token)

    assert user.username == "alice"
    assert logged_out is True
    assert shadow.saved == []
    assert shadow.deleted == []


def test_session_dual_write_saves_login_and_deletes_logout(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _SessionShadowRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, user = service.login("alice", "pass123")
    logged_out = service.logout(token)

    assert logged_out is True
    assert [(saved_token, record.user_id) for saved_token, record in shadow.saved] == [(token, user.id)]
    assert shadow.deleted == [token]


def test_session_dual_write_deletes_user_sessions_on_password_change(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _SessionShadowRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)
    user = service.register("alice", "pass123")
    service.login("alice", "pass123")
    service.login("alice", "pass123")

    changed, message = service.change_password(user.id, "pass123", "pass456")

    assert changed is True, message
    assert len(shadow.saved) == 2
    assert shadow.deleted_users == [user.id]


def test_session_dual_write_failure_does_not_break_file_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _SessionShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, _ = service.login("alice", "pass123")

    assert token in _read_sessions(tmp_path / "sessions.json")


def test_session_dual_write_strict_failure_propagates_after_file_write(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true")
    shadow = _SessionShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    with pytest.raises(RuntimeError):
        service.login("alice", "pass123")

    saved_sessions = _read_sessions(tmp_path / "sessions.json")
    assert len(saved_sessions) == 1
