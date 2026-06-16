"""Reconcile JSON and PostgreSQL session state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.repositories.sessions import is_token_hash, token_sha256
from app.services.migration.backfill_sessions import iter_session_json_records
from app.services.session_store import SessionRecord


def _hash_key(key: str) -> str:
    return key if is_token_hash(key) else token_sha256(key)


def _record_projection(record: SessionRecord) -> dict[str, Any]:
    return {
        "user_id": record.user_id,
        "created_at": record.created_at,
    }


def _normalize_repository_records(records: dict[str, SessionRecord]) -> dict[str, SessionRecord]:
    return {
        _hash_key(token_or_hash): record
        for token_or_hash, record in records.items()
    }


def reconcile_sessions(data_root: str | Path, session_repository) -> dict:
    """Compare file-backed sessions with PostgreSQL shadow data."""

    json_sessions: dict[str, SessionRecord] = {}
    load_failures: list[dict] = []

    def record_load_failure(token: str, exc: Exception) -> None:
        load_failures.append(
            {
                "token_hash": token_sha256(token) if token else "",
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_session_json_records(data_root, on_error=record_load_failure):
        json_sessions[token_sha256(item.token)] = item.record

    postgres_sessions = _normalize_repository_records(session_repository.list_all())

    missing_in_postgres = [
        {"token_hash": token_hash}
        for token_hash in sorted(set(json_sessions) - set(postgres_sessions))
    ]
    missing_in_json = [
        {"token_hash": token_hash}
        for token_hash in sorted(set(postgres_sessions) - set(json_sessions))
    ]

    field_differences: list[dict] = []
    for token_hash in sorted(set(json_sessions) & set(postgres_sessions)):
        json_projection = _record_projection(json_sessions[token_hash])
        postgres_projection = _record_projection(postgres_sessions[token_hash])
        if json_projection["user_id"] != postgres_projection["user_id"]:
            field_differences.append({"token_hash": token_hash, "field": "user_id"})
        if (
            json_projection["created_at"]
            and postgres_projection["created_at"]
            and json_projection["created_at"] != postgres_projection["created_at"]
        ):
            field_differences.append({"token_hash": token_hash, "field": "created_at"})

    summary = {
        "domain": "sessions",
        "json_session_count": len(json_sessions),
        "postgres_session_count": len(postgres_sessions),
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
    """Render a sanitized human-readable sessions reconcile summary."""

    lines = [
        "# Sessions Reconcile",
        "",
        f"- domain: `{summary['domain']}`",
        f"- ok: `{str(summary['ok']).lower()}`",
        f"- json_session_count: `{summary['json_session_count']}`",
        f"- postgres_session_count: `{summary['postgres_session_count']}`",
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
            prefix = f"token_hash=`{item['token_hash']}`"
            if key == "field_differences":
                lines.append(f"- {prefix} field=`{item['field']}`")
            elif key == "load_failures":
                lines.append(f"- {prefix} error=`{item['error']}`")
            else:
                lines.append(f"- {prefix}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_reconcile_reports(summary: dict, output_dir: str | Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reconcile summaries."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "sessions_reconcile.json"
    markdown_path = output_path / "sessions_reconcile.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    markdown_path.write_text(render_reconcile_markdown(summary), encoding="utf-8")
    return json_path, markdown_path
