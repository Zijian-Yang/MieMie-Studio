import json
from pathlib import Path

import pytest

from app.config import AppConfig, ConfigManager
from app.services.storage import set_current_user
from app.services.user_service import UserService


class _UserShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []

    def save(self, user):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append(user.model_copy(deep=True))


class _ConfigShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []

    def save(self, user_id, config):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append((user_id, config.model_copy(deep=True)))


def _user_service(tmp_path) -> UserService:
    return UserService(data_dir=Path(tmp_path))


def _enable_dual_write(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "user_config")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "false")


def test_user_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _UserShadowRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")

    assert user is not None
    assert shadow.saved == []
    assert json.loads((tmp_path / "users.json").read_text(encoding="utf-8"))[user.id]["username"] == "alice"


def test_user_dual_write_saves_after_register_login_and_change_password(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _UserShadowRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")
    login_result = service.login("alice", "pass123")
    changed, message = service.change_password(user.id, "pass123", "pass456")

    assert user is not None
    assert login_result is not None
    assert changed is True, message
    assert [saved.username for saved in shadow.saved] == ["alice", "alice", "alice"]
    assert shadow.saved[1].last_login is not None


def test_user_dual_write_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _UserShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)

    user = service.register("alice", "pass123")

    assert user is not None
    assert service.get_user_by_id(user.id).username == "alice"


def test_user_dual_write_strict_failure_propagates_after_json_write(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true")
    shadow = _UserShadowRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_shadow_repository",
        lambda: shadow,
    )
    service = _user_service(tmp_path)

    with pytest.raises(RuntimeError):
        service.register("alice", "pass123")

    users = json.loads((tmp_path / "users.json").read_text(encoding="utf-8"))
    assert [item["username"] for item in users.values()] == ["alice"]


def test_config_dual_write_saves_when_enabled_and_user_context_present(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ConfigShadowRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_shadow_repository",
        lambda: shadow,
    )
    manager = ConfigManager(str(tmp_path / "users" / "user-1"))

    try:
        set_current_user("user-1")
        manager.save(AppConfig(api_region="singapore", dashscope_api_key="sk-private"))
    finally:
        set_current_user(None)

    assert [(user_id, config.api_region) for user_id, config in shadow.saved] == [("user-1", "singapore")]
    persisted = json.loads((tmp_path / "users" / "user-1" / "config.json").read_text(encoding="utf-8"))
    assert persisted["dashscope_api_key"] == "sk-private"


def test_config_dual_write_is_disabled_without_user_context(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ConfigShadowRepository()
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_shadow_repository",
        lambda: shadow,
    )
    manager = ConfigManager(str(tmp_path / "global"))

    manager.save(AppConfig(api_region="singapore"))

    assert shadow.saved == []
