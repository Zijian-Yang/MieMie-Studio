import json
from pathlib import Path

import pytest

from app.services.user_service import UserService


class _SessionPrimaryRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.records = {}
        self.saved = []
        self.deleted = []
        self.deleted_users = []

    def save(self, token, record):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.records[token] = record
        self.saved.append((token, record))

    def get(self, token):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        return self.records.get(token)

    def delete(self, token):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted.append(token)
        self.records.pop(token, None)

    def delete_user_sessions(self, user_id):
        if self.fail:
            raise RuntimeError("postgres primary unavailable")
        self.deleted_users.append(user_id)
        tokens = [token for token, record in self.records.items() if record.user_id == user_id]
        for token in tokens:
            self.records.pop(token, None)
        return len(tokens)


def _user_service(tmp_path) -> UserService:
    service = UserService()
    service.data_dir = Path(tmp_path)
    service.users_file = service.data_dir / "users.json"
    service.sessions = {}
    service._redis_sessions = None
    service._ensure_data_dir()
    return service


def _enable_primary(monkeypatch, *, archive: bool = False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "sessions")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def _read_sessions(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_session_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, _ = service.login("alice", "pass123")

    assert primary.saved == []
    assert _read_sessions(tmp_path / "sessions.json")[token]["user_id"]


def test_session_primary_write_saves_postgres_without_json_by_default(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, user = service.login("alice", "pass123")

    assert [(saved_token, record.user_id) for saved_token, record in primary.saved] == [(token, user.id)]
    assert primary.get(token).user_id == user.id
    assert not (tmp_path / "sessions.json").exists()


def test_session_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary(monkeypatch, archive=True)
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    token, user = service.login("alice", "pass123")

    assert [(saved_token, record.user_id) for saved_token, record in primary.saved] == [(token, user.id)]
    assert _read_sessions(tmp_path / "sessions.json")[token]["user_id"] == user.id


def test_session_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary(monkeypatch, archive=True)
    primary = _SessionPrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")

    with pytest.raises(RuntimeError, match="postgres primary unavailable"):
        service.login("alice", "pass123")

    assert not (tmp_path / "sessions.json").exists()


def test_session_primary_write_reads_postgres_without_explicit_read_switch(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")
    token, user = service.login("alice", "pass123")
    service.sessions = {}

    result = service.get_user_by_token(token)

    assert result.id == user.id


def test_session_primary_write_logout_deletes_postgres_after_restart(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    service.register("alice", "pass123")
    token, _ = service.login("alice", "pass123")
    restarted = _user_service(tmp_path)

    logged_out = restarted.logout(token)

    assert logged_out is True
    assert primary.deleted == [token]
    assert primary.get(token) is None


def test_session_primary_write_deletes_user_sessions_on_password_change(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _SessionPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    user = service.register("alice", "pass123")
    service.login("alice", "pass123")
    service.login("alice", "pass123")

    changed, message = service.change_password(user.id, "pass123", "pass456")

    assert changed is True, message
    assert primary.deleted_users == [user.id]
    assert primary.records == {}
