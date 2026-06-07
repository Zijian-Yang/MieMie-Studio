from datetime import datetime, timezone

from app.config import AppConfig
from app.models.user import User
from app.repositories.user_config import (
    config_to_row,
    row_to_config,
    row_to_user,
    safe_config_indexes,
    user_to_row,
)


def _user(**overrides) -> User:
    data = {
        "id": "user-1",
        "username": "s4_user",
        "password": "$2b$12$hashed-password-placeholder",
        "display_name": "S4 User",
        "created_at": "2026-06-07T08:00:00+00:00",
        "last_login": "2026-06-07T08:30:00+00:00",
    }
    data.update(overrides)
    return User(**data)


def test_user_row_mapping_uses_password_hash_column_and_restores_model():
    user = _user()

    row = user_to_row(user)

    assert row["id"] == "user-1"
    assert row["username"] == "s4_user"
    assert row["password_hash"] == "$2b$12$hashed-password-placeholder"
    assert "password" not in row
    assert row["raw_user_snapshot"]["password"] == "$2b$12$hashed-password-placeholder"
    assert row["created_at"] == datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc)
    assert row["last_login"] == datetime(2026, 6, 7, 8, 30, tzinfo=timezone.utc)
    assert row["updated_at"] == datetime(2026, 6, 7, 8, 30, tzinfo=timezone.utc)
    assert row["deleted_at"] is None

    restored = row_to_user(row)

    assert restored == user


def test_user_row_mapping_handles_never_logged_in_users():
    user = _user(last_login=None)

    row = user_to_row(user)

    assert row["last_login"] is None
    assert row["updated_at"] == datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc)
    assert row_to_user(row) == user


def test_config_safe_indexes_do_not_expose_secret_values():
    config = AppConfig(
        api_region="singapore",
        dashscope_api_key="sk-dashscope",
        production_api_key="sk-production",
        oss={
            "enabled": True,
            "access_key_id": "ak-id",
            "access_key_secret": "ak-secret",
            "bucket_name": "bucket",
            "endpoint": "oss-cn-beijing.aliyuncs.com",
        },
    )

    indexes = safe_config_indexes(config)

    assert indexes == {
        "api_region": "singapore",
        "has_dashscope_key": True,
        "has_oss_config": True,
    }


def test_config_row_mapping_keeps_snapshot_for_roundtrip_but_only_indexes_safe_fields():
    config = AppConfig(
        api_region="us_virginia",
        test_api_key="sk-test",
        oss={"enabled": False, "access_key_id": "ak-id", "access_key_secret": ""},
    )

    row = config_to_row("user-1", config)

    assert row["user_id"] == "user-1"
    assert row["api_region"] == "us_virginia"
    assert row["has_dashscope_key"] is True
    assert row["has_oss_config"] is False
    assert row["raw_config_snapshot"]["test_api_key"] == "sk-test"
    assert row["created_at"] <= row["updated_at"]
    assert row["deleted_at"] is None

    restored = row_to_config(row)

    assert restored == config
