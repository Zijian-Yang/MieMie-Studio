import json
from pathlib import Path

import pytest

from app.config import AppConfig, ConfigManager
from app.models.user import User
from app.services.storage import set_current_user
from app.services.user_service import UserService


class _UserPrimaryRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.users = {}
        self.saved = []

    def save(self, user):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.users[user.id] = user.model_copy(deep=True)
        self.saved.append(user.id)

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_username(self, username):
        return next((user for user in self.users.values() if user.username == username), None)


class _ConfigPrimaryRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.configs = {}
        self.saved = []

    def save(self, user_id, config):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.configs[user_id] = config.model_copy(deep=True)
        self.saved.append(user_id)

    def get(self, user_id):
        return self.configs.get(user_id)


def _user_service(tmp_path) -> UserService:
    return UserService(data_dir=Path(tmp_path))


def _enable_primary(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "user_config")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")


def _read_users(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_user_service_binds_custom_data_dir_before_initialization(tmp_path):
    service = UserService(data_dir=tmp_path)

    assert service.data_dir == tmp_path
    assert service.users_file == tmp_path / "users.json"
    assert service.users_file.exists()


def test_user_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    primary = _UserPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")

    assert user is not None
    assert primary.saved == []
    assert _read_users(tmp_path / "users.json")[user.id]["username"] == "alice"


def test_user_primary_write_registers_to_postgres_without_json_by_default(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _UserPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")

    assert user is not None
    assert primary.saved == [user.id]
    assert primary.get_by_id(user.id).username == "alice"
    assert not (tmp_path / "users.json").exists()


def test_user_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true")
    primary = _UserPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")

    assert primary.saved == [user.id]
    assert _read_users(tmp_path / "users.json")[user.id]["username"] == "alice"


def test_user_primary_write_login_reads_and_updates_postgres_user(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _UserPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_primary_repository",
        lambda: primary,
    )
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)
    user = service.register("alice", "pass123")

    login_result = service.login("alice", "pass123")

    assert login_result is not None
    token, logged_in = login_result
    assert token
    assert logged_in.id == user.id
    assert primary.get_by_id(user.id).last_login is not None
    assert primary.saved == [user.id, user.id]
    assert not (tmp_path / "users.json").exists()


def test_user_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _UserPrimaryRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_primary_repository",
        lambda: primary,
    )
    service = _user_service(tmp_path)

    with pytest.raises(RuntimeError):
        service.register("alice", "pass123")

    assert not (tmp_path / "users.json").exists()


def test_config_primary_write_saves_to_postgres_without_json_by_default(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    primary = _ConfigPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_primary_repository",
        lambda: primary,
    )
    manager = ConfigManager(str(tmp_path / "users" / "user-1"))

    try:
        set_current_user("user-1")
        manager.save(AppConfig(api_region="singapore"))
    finally:
        set_current_user(None)

    assert primary.saved == ["user-1"]
    assert primary.get("user-1").api_region == "singapore"
    assert not manager.config_file.exists()


def test_config_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true")
    primary = _ConfigPrimaryRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_primary_repository",
        lambda: primary,
    )
    manager = ConfigManager(str(tmp_path / "users" / "user-1"))

    try:
        set_current_user("user-1")
        manager.save(AppConfig(api_region="singapore"))
    finally:
        set_current_user(None)

    assert primary.saved == ["user-1"]
    assert json.loads(manager.config_file.read_text(encoding="utf-8"))["api_region"] == "singapore"
