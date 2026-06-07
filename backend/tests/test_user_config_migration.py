import json

from app.config import AppConfig
from app.models.user import User
from app.services.migration.backfill_user_config import (
    backfill_user_config,
    iter_user_config_json_files,
)
from app.services.migration.reconcile_user_config import (
    reconcile_user_config,
    render_reconcile_markdown,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _user(user_id: str = "user-1", **overrides) -> dict:
    data = {
        "id": user_id,
        "username": f"user-{user_id}",
        "password": "$2b$12$private-hash-placeholder",
        "display_name": f"User {user_id}",
        "created_at": "2026-06-07T08:00:00+00:00",
        "last_login": "2026-06-07T08:30:00+00:00",
    }
    data.update(overrides)
    return data


def _config(**overrides) -> dict:
    config = AppConfig(
        api_region="singapore",
        dashscope_api_key="sk-private",
        oss={
            "enabled": True,
            "access_key_id": "ak-private",
            "access_key_secret": "secret-private",
            "bucket_name": "private-bucket",
        },
    ).model_dump(mode="json")
    config.update(overrides)
    return config


class _UserRepository:
    def __init__(self):
        self.users = {}
        self.saved = []

    def save(self, user):
        self.users[user.id] = user
        self.saved.append(user.id)

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def list_all(self):
        return list(self.users.values())


class _ConfigRepository:
    def __init__(self):
        self.configs = {}
        self.saved = []

    def save(self, user_id, config):
        self.configs[user_id] = config
        self.saved.append(user_id)

    def get(self, user_id):
        return self.configs.get(user_id)

    def list_all(self):
        return dict(self.configs)


def test_iter_user_config_json_files_scans_users_and_configs_without_sessions(tmp_path):
    _write_json(tmp_path / "users.json", {"user-1": _user("user-1")})
    _write_json(tmp_path / "users" / "user-1" / "config.json", _config())
    _write_json(tmp_path / "sessions.json", {"token": {"user_id": "user-1"}})

    records = list(iter_user_config_json_files(tmp_path))

    assert len(records) == 1
    assert records[0].user.id == "user-1"
    assert records[0].config.api_region == "singapore"
    assert records[0].config_path.name == "config.json"


def test_backfill_user_config_upserts_users_and_configs_with_sanitized_summary(tmp_path):
    _write_json(tmp_path / "users.json", {"user-1": _user("user-1")})
    _write_json(tmp_path / "users" / "user-1" / "config.json", _config())
    users = _UserRepository()
    configs = _ConfigRepository()

    summary = backfill_user_config(tmp_path, users, configs)

    assert summary == {
        "domain": "user_config",
        "scanned_users": ["user-1"],
        "user_json_count": 1,
        "config_json_count": 1,
        "users_upserted_count": 1,
        "configs_upserted_count": 1,
        "failed_count": 0,
        "failures": [],
        "ok": True,
    }
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "sk-private" not in serialized
    assert "private-hash-placeholder" not in serialized
    assert users.saved == ["user-1"]
    assert configs.saved == ["user-1"]


def test_backfill_user_config_reports_load_failures_without_secret_values(tmp_path):
    _write_json(tmp_path / "users.json", {"user-1": _user("user-1")})
    broken = tmp_path / "users" / "user-1" / "config.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{broken", encoding="utf-8")

    summary = backfill_user_config(tmp_path, _UserRepository(), _ConfigRepository())

    assert summary["ok"] is False
    assert summary["user_json_count"] == 1
    assert summary["config_json_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["failures"] == [
        {
            "user_id": "user-1",
            "record_kind": "config",
            "record_file": "config.json",
            "error": "JSONDecodeError",
        }
    ]


def test_reconcile_user_config_compares_safe_fields_only(tmp_path):
    user = _user("user-1")
    _write_json(tmp_path / "users.json", {"user-1": user})
    _write_json(tmp_path / "users" / "user-1" / "config.json", _config(api_region="singapore"))
    users = _UserRepository()
    configs = _ConfigRepository()
    users.save(User(**user))
    configs.save("user-1", AppConfig(**_config(api_region="beijing")))

    summary = reconcile_user_config(tmp_path, users, configs)
    markdown = render_reconcile_markdown(summary)

    assert summary["ok"] is False
    assert summary["json_user_count"] == 1
    assert summary["postgres_user_count"] == 1
    assert summary["json_config_count"] == 1
    assert summary["postgres_config_count"] == 1
    assert summary["missing_in_postgres"] == []
    assert summary["missing_in_json"] == []
    assert summary["field_differences"] == [
        {"user_id": "user-1", "record_kind": "config", "field": "api_region"}
    ]
    assert "api_region" in markdown
    assert "sk-private" not in markdown
    assert "private-hash-placeholder" not in markdown


def test_reconcile_user_config_detects_missing_records(tmp_path):
    _write_json(tmp_path / "users.json", {"user-1": _user("user-1")})
    _write_json(tmp_path / "users" / "user-1" / "config.json", _config())
    users = _UserRepository()
    configs = _ConfigRepository()
    users.save(User(**_user("extra-user")))

    summary = reconcile_user_config(tmp_path, users, configs)

    assert summary["ok"] is False
    assert {"user_id": "user-1", "record_kind": "user"} in summary["missing_in_postgres"]
    assert {"user_id": "user-1", "record_kind": "config"} in summary["missing_in_postgres"]
    assert {"user_id": "extra-user", "record_kind": "user"} in summary["missing_in_json"]
