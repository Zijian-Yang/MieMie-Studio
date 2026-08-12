import json
from datetime import datetime
from pathlib import Path

from app.config import AppConfig, ConfigManager
from app.models.user import User
from app.services.storage import set_current_user
from app.services.user_service import UserService


class _UserReadRepository:
    def __init__(self, *, user=None, users=None, fail: bool = False):
        self.user = user
        self.users = users if users is not None else ([user] if user is not None else [])
        self.fail = fail
        self.seen_ids = []
        self.listed = False

    def get_by_id(self, user_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.seen_ids.append(user_id)
        return self.user

    def list_all(self):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.listed = True
        return list(self.users)


class _ConfigReadRepository:
    def __init__(self, *, config=None, fail: bool = False):
        self.config = config
        self.fail = fail
        self.seen_ids = []

    def get(self, user_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.seen_ids.append(user_id)
        return self.config


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _user_service(tmp_path, user: User) -> UserService:
    service = UserService(data_dir=Path(tmp_path))
    _write_json(service.users_file, {user.id: user.model_dump(mode="json")})
    return service


def _user(user_id: str = "user-1", username: str = "json-user") -> User:
    return User(
        id=user_id,
        username=username,
        password="$2b$12$hash-placeholder",
        display_name=username,
        created_at="2026-06-07T08:00:00+00:00",
    )


def _enable_read(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "user_config")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")


def test_user_read_switch_is_disabled_by_default(tmp_path, monkeypatch):
    json_user = _user(username="json-user")
    postgres_user = _user(username="postgres-user")
    repo = _UserReadRepository(user=postgres_user)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)

    result = service.get_user_by_id("user-1")

    assert result.username == "json-user"
    assert repo.seen_ids == []


def test_user_read_switch_prefers_postgres_when_enabled(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    json_user = _user(username="json-user")
    postgres_user = _user(username="postgres-user")
    repo = _UserReadRepository(user=postgres_user)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)

    result = service.get_user_by_id("user-1")

    assert result.username == "postgres-user"
    assert repo.seen_ids == ["user-1"]


def test_user_read_switch_falls_back_to_json_on_miss_or_error(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true")
    json_user = _user(username="json-user")
    service = _user_service(tmp_path, json_user)

    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: _UserReadRepository(user=None),
    )
    assert service.get_user_by_id("user-1").username == "json-user"

    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: _UserReadRepository(fail=True),
    )
    assert service.get_user_by_id("user-1").username == "json-user"


def test_token_user_read_switch_prefers_postgres_user(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    json_user = _user(username="json-user")
    postgres_user = _user(username="postgres-user")
    repo = _UserReadRepository(user=postgres_user)
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)
    service.sessions["token"] = {
        "user_id": "user-1",
        "created_at": datetime.now().isoformat(),
    }
    _write_json(tmp_path / "sessions.json", service.sessions)

    result = service.get_user_by_token("token")

    assert result.username == "postgres-user"
    assert repo.seen_ids == ["user-1"]


def test_user_id_listing_prefers_postgres_when_user_config_read_enabled(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    json_user = _user(user_id="json-user", username="json-user")
    postgres_user = _user(user_id="postgres-user", username="postgres-user")
    repo = _UserReadRepository(users=[postgres_user])
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)

    result = service.list_user_ids()

    assert result == ["postgres-user"]
    assert repo.listed is True


def test_config_read_switch_prefers_postgres_when_enabled(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    repo = _ConfigReadRepository(config=AppConfig(api_region="singapore"))
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_read_repository",
        lambda: repo,
    )
    manager = ConfigManager(str(tmp_path / "users" / "user-1"))
    _write_json(manager.config_file, AppConfig(api_region="beijing").model_dump(mode="json"))

    try:
        set_current_user("user-1")
        config = manager.load()
    finally:
        set_current_user(None)

    assert config.api_region == "singapore"
    assert repo.seen_ids == ["user-1"]


def test_config_read_switch_falls_back_to_json_on_miss_or_error(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true")
    manager = ConfigManager(str(tmp_path / "users" / "user-1"))
    _write_json(manager.config_file, AppConfig(api_region="beijing").model_dump(mode="json"))

    try:
        set_current_user("user-1")
        monkeypatch.setattr(
            "app.repositories.user_config_runtime.build_user_config_read_repository",
            lambda: _ConfigReadRepository(config=None),
        )
        assert manager.load().api_region == "beijing"

        monkeypatch.setattr(
            "app.repositories.user_config_runtime.build_user_config_read_repository",
            lambda: _ConfigReadRepository(fail=True),
        )
        assert manager.load().api_region == "beijing"
    finally:
        set_current_user(None)


def test_config_read_switch_is_disabled_without_user_context(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    repo = _ConfigReadRepository(config=AppConfig(api_region="singapore"))
    monkeypatch.setattr(
        "app.repositories.user_config_runtime.build_user_config_read_repository",
        lambda: repo,
    )
    manager = ConfigManager(str(tmp_path / "global"))
    _write_json(manager.config_file, AppConfig(api_region="beijing").model_dump(mode="json"))

    config = manager.load()

    assert config.api_region == "beijing"
    assert repo.seen_ids == []
