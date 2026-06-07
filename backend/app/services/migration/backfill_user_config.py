"""Backfill users and per-user configs from JSON files into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.config import AppConfig
from app.models.user import User


@dataclass(frozen=True)
class UserConfigJsonRecord:
    user_id: str
    user: User
    config: AppConfig | None
    user_path: Path
    config_path: Path | None


def iter_user_config_json_files(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, str, Path, Exception], None]] = None,
) -> Iterable[UserConfigJsonRecord]:
    """Yield valid users and optional per-user config from current JSON storage."""

    root = Path(data_root)
    users_path = root / "users.json"
    if not users_path.exists():
        return

    try:
        with users_path.open("r", encoding="utf-8") as handle:
            raw_users = json.load(handle)
    except Exception as exc:
        if on_error:
            on_error("", "users", users_path, exc)
        return

    for user_id, user_data in sorted(raw_users.items()):
        try:
            user = User(**user_data)
        except Exception as exc:
            if on_error:
                on_error(user_id, "user", users_path, exc)
            continue

        config_path = root / "users" / user_id / "config.json"
        config: AppConfig | None = None
        if config_path.exists():
            try:
                with config_path.open("r", encoding="utf-8") as handle:
                    config = AppConfig(**json.load(handle))
            except Exception as exc:
                if on_error:
                    on_error(user_id, "config", config_path, exc)

        yield UserConfigJsonRecord(
            user_id=user_id,
            user=user,
            config=config,
            user_path=users_path,
            config_path=config_path if config_path.exists() else None,
        )


def backfill_user_config(
    data_root: str | Path,
    user_repository,
    config_repository,
) -> dict:
    """Upsert all valid users and per-user configs into PostgreSQL repositories."""

    failures: list[dict] = []
    scanned_users: set[str] = set()
    user_json_count = 0
    config_json_count = 0
    users_upserted_count = 0
    configs_upserted_count = 0

    def record_load_failure(user_id: str, record_kind: str, record_path: Path, exc: Exception) -> None:
        failures.append(
            {
                "user_id": user_id,
                "record_kind": record_kind,
                "record_file": record_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_user_config_json_files(data_root, on_error=record_load_failure):
        scanned_users.add(item.user_id)
        user_json_count += 1
        if item.config is not None:
            config_json_count += 1
        try:
            user_repository.save(item.user)
            users_upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "user_id": item.user_id,
                    "record_kind": "user",
                    "record_file": item.user_path.name,
                    "error": exc.__class__.__name__,
                }
            )
        if item.config is not None:
            try:
                config_repository.save(item.user_id, item.config)
                configs_upserted_count += 1
            except Exception as exc:
                failures.append(
                    {
                        "user_id": item.user_id,
                        "record_kind": "config",
                        "record_file": item.config_path.name if item.config_path else "config.json",
                        "error": exc.__class__.__name__,
                    }
                )

    return {
        "domain": "user_config",
        "scanned_users": sorted(scanned_users),
        "user_json_count": user_json_count,
        "config_json_count": config_json_count,
        "users_upserted_count": users_upserted_count,
        "configs_upserted_count": configs_upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized user/config backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
