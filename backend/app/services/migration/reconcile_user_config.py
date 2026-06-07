"""Reconcile JSON and PostgreSQL user/config state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.models.user import User
from app.repositories.user_config import safe_config_indexes
from app.services.migration.backfill_user_config import iter_user_config_json_files


USER_COMPARE_FIELDS = ("username", "display_name", "created_at", "last_login", "password_hash")
CONFIG_COMPARE_FIELDS = ("api_region", "has_dashscope_key", "has_oss_config")


def _user_projection(user: User) -> dict[str, Any]:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "password_hash": user.password,
    }


def _config_projection(config: AppConfig) -> dict[str, Any]:
    return safe_config_indexes(config)


def _sorted_user_map(users: list[User]) -> dict[str, User]:
    return {
        user.id: user
        for user in sorted(users, key=lambda item: item.id)
    }


def reconcile_user_config(
    data_root: str | Path,
    user_repository,
    config_repository,
) -> dict:
    """Compare JSON primary user/config state with PostgreSQL shadow data."""

    json_users: dict[str, User] = {}
    json_configs: dict[str, AppConfig] = {}
    load_failures: list[dict] = []

    def record_load_failure(user_id: str, record_kind: str, record_path: Path, exc: Exception) -> None:
        load_failures.append(
            {
                "user_id": user_id,
                "record_kind": record_kind,
                "record_file": record_path.name,
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_user_config_json_files(data_root, on_error=record_load_failure):
        json_users[item.user_id] = item.user
        if item.config is not None:
            json_configs[item.user_id] = item.config

    postgres_users = _sorted_user_map(user_repository.list_all())
    postgres_configs = config_repository.list_all()

    missing_in_postgres: list[dict] = []
    missing_in_json: list[dict] = []
    field_differences: list[dict] = []

    for user_id in sorted(set(json_users) - set(postgres_users)):
        missing_in_postgres.append({"user_id": user_id, "record_kind": "user"})
    for user_id in sorted(set(json_configs) - set(postgres_configs)):
        missing_in_postgres.append({"user_id": user_id, "record_kind": "config"})

    for user_id in sorted(set(postgres_users) - set(json_users)):
        missing_in_json.append({"user_id": user_id, "record_kind": "user"})
    for user_id in sorted(set(postgres_configs) - set(json_configs)):
        missing_in_json.append({"user_id": user_id, "record_kind": "config"})

    for user_id in sorted(set(json_users) & set(postgres_users)):
        json_projection = _user_projection(json_users[user_id])
        postgres_projection = _user_projection(postgres_users[user_id])
        for field in USER_COMPARE_FIELDS:
            if json_projection[field] != postgres_projection[field]:
                field_differences.append(
                    {"user_id": user_id, "record_kind": "user", "field": field}
                )

    for user_id in sorted(set(json_configs) & set(postgres_configs)):
        json_projection = _config_projection(json_configs[user_id])
        postgres_projection = _config_projection(postgres_configs[user_id])
        for field in CONFIG_COMPARE_FIELDS:
            if json_projection[field] != postgres_projection[field]:
                field_differences.append(
                    {"user_id": user_id, "record_kind": "config", "field": field}
                )

    summary = {
        "domain": "user_config",
        "json_user_count": len(json_users),
        "postgres_user_count": len(postgres_users),
        "json_config_count": len(json_configs),
        "postgres_config_count": len(postgres_configs),
        "missing_in_postgres": missing_in_postgres,
        "missing_in_json": missing_in_json,
        "field_differences": field_differences,
        "load_failures": load_failures,
    }
    summary["ok"] = not (
        missing_in_postgres
        or missing_in_json
        or field_differences
        or load_failures
    )
    return summary


def render_reconcile_markdown(summary: dict) -> str:
    """Render a sanitized human-readable user/config reconcile summary."""

    lines = [
        "# User Config Reconcile",
        "",
        f"- domain: `{summary['domain']}`",
        f"- ok: `{str(summary['ok']).lower()}`",
        f"- json_user_count: `{summary['json_user_count']}`",
        f"- postgres_user_count: `{summary['postgres_user_count']}`",
        f"- json_config_count: `{summary['json_config_count']}`",
        f"- postgres_config_count: `{summary['postgres_config_count']}`",
        f"- missing_in_postgres: `{len(summary['missing_in_postgres'])}`",
        f"- missing_in_json: `{len(summary['missing_in_json'])}`",
        f"- field_differences: `{len(summary['field_differences'])}`",
        f"- load_failures: `{len(summary.get('load_failures', []))}`",
        "",
    ]

    for key in ("missing_in_postgres", "missing_in_json", "field_differences", "load_failures"):
        items = summary.get(key, [])
        if not items:
            continue
        lines.append(f"## {key}")
        for item in items:
            prefix = f"user_id=`{item['user_id']}` record_kind=`{item['record_kind']}`"
            if key == "field_differences":
                lines.append(f"- {prefix} field=`{item['field']}`")
            elif key == "load_failures":
                lines.append(
                    f"- {prefix} record_file=`{item['record_file']}` error=`{item['error']}`"
                )
            else:
                lines.append(f"- {prefix}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "user_config_reconcile.json"
    markdown_path = output_path / "user_config_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
