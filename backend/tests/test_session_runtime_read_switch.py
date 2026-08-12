import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.user import User
from app.services.session_store import SessionRecord
from app.services.user_service import UserService


class _SessionReadRepository:
    def __init__(self, *, records=None, fail: bool = False):
        self.records = records or {}
        self.fail = fail
        self.seen = []

    def get(self, token):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.seen.append(token)
        return self.records.get(token)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _user(user_id: str, username: str) -> User:
    return User(
        id=user_id,
        username=username,
        password="$2b$12$hash-placeholder",
        display_name=username,
        created_at="2026-06-17T08:00:00",
    )


def _active_session_created_at() -> str:
    return datetime.now().isoformat()


def _user_service(tmp_path, *users: User) -> UserService:
    service = UserService()
    service.data_dir = Path(tmp_path)
    service.users_file = service.data_dir / "users.json"
    service.sessions = {}
    service._redis_sessions = None
    service._ensure_data_dir()
    _write_json(service.users_file, {user.id: user.model_dump(mode="json") for user in users})
    return service


def _enable_read(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "sessions")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")


def test_session_read_switch_is_disabled_by_default(tmp_path, monkeypatch):
    created_at = _active_session_created_at()
    json_user = _user("json-user-id", "json-user")
    postgres_user = _user("postgres-user-id", "postgres-user")
    repo = _SessionReadRepository(records={"token": SessionRecord(user_id=postgres_user.id, created_at=created_at)})
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user, postgres_user)
    _write_json(
        tmp_path / "sessions.json",
        {"token": {"user_id": json_user.id, "created_at": created_at}},
    )

    result = service.get_user_by_token("token")

    assert result.username == "json-user"
    assert repo.seen == []


def test_session_read_switch_prefers_postgres_session(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    created_at = _active_session_created_at()
    json_user = _user("json-user-id", "json-user")
    postgres_user = _user("postgres-user-id", "postgres-user")
    repo = _SessionReadRepository(records={"token": SessionRecord(user_id=postgres_user.id, created_at=created_at)})
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user, postgres_user)
    _write_json(
        tmp_path / "sessions.json",
        {"token": {"user_id": json_user.id, "created_at": created_at}},
    )

    result = service.get_user_by_token("token")

    assert result.username == "postgres-user"
    assert repo.seen == ["token"]


def test_session_read_switch_falls_back_to_file_on_miss_when_enabled(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true")
    created_at = _active_session_created_at()
    json_user = _user("json-user-id", "json-user")
    repo = _SessionReadRepository()
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)
    _write_json(
        tmp_path / "sessions.json",
        {"token": {"user_id": json_user.id, "created_at": created_at}},
    )

    result = service.get_user_by_token("token")

    assert result.username == "json-user"
    assert repo.seen == ["token"]


def test_session_read_switch_falls_back_to_file_on_error_when_enabled(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true")
    created_at = _active_session_created_at()
    json_user = _user("json-user-id", "json-user")
    repo = _SessionReadRepository(fail=True)
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, json_user)
    _write_json(
        tmp_path / "sessions.json",
        {"token": {"user_id": json_user.id, "created_at": created_at}},
    )

    result = service.get_user_by_token("token")

    assert result.username == "json-user"


def test_session_read_switch_rejects_expired_timezone_aware_postgres_session(tmp_path, monkeypatch):
    _enable_read(monkeypatch)
    expired_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    postgres_user = _user("postgres-user-id", "postgres-user")
    repo = _SessionReadRepository(
        records={"token": SessionRecord(user_id=postgres_user.id, created_at=expired_at)}
    )
    monkeypatch.setattr(
        "app.repositories.session_runtime.build_session_read_repository",
        lambda: repo,
    )
    service = _user_service(tmp_path, postgres_user)

    assert service.get_user_by_token("token") is None


def test_login_creates_timezone_aware_utc_session(tmp_path):
    service = _user_service(tmp_path)
    user = service.register("utc-session-user", "secure-password")

    token, logged_in_user = service.login(user.username, "secure-password")
    created_at = datetime.fromisoformat(service.sessions[token]["created_at"])

    assert logged_in_user.id == user.id
    assert created_at.utcoffset() == timedelta(0)
