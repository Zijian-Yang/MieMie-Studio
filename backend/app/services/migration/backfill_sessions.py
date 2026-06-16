"""Backfill session JSON records into PostgreSQL repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from app.repositories.sessions import token_sha256
from app.services.session_store import SessionRecord


@dataclass(frozen=True)
class SessionJsonRecord:
    token: str
    record: SessionRecord


def iter_session_json_records(
    data_root: str | Path,
    *,
    on_error: Optional[Callable[[str, Exception], None]] = None,
) -> Iterable[SessionJsonRecord]:
    """Yield valid sessions from current file storage, including legacy token shapes."""

    sessions_path = Path(data_root) / "sessions.json"
    if not sessions_path.exists():
        return

    try:
        with sessions_path.open("r", encoding="utf-8") as handle:
            raw_sessions = json.load(handle)
    except Exception as exc:
        if on_error:
            on_error("", exc)
        return

    for token, raw_record in sorted(raw_sessions.items()):
        try:
            record = SessionRecord.from_raw(raw_record)
            if record is None:
                raise ValueError("invalid session record")
        except Exception as exc:
            if on_error:
                on_error(token, exc)
            continue
        yield SessionJsonRecord(token=token, record=record)


def backfill_sessions(data_root: str | Path, session_repository) -> dict:
    """Upsert valid file-backed sessions into PostgreSQL."""

    failures: list[dict] = []
    json_session_count = 0
    sessions_upserted_count = 0

    def record_load_failure(token: str, exc: Exception) -> None:
        failures.append(
            {
                "token_hash": token_sha256(token) if token else "",
                "error": exc.__class__.__name__,
            }
        )

    for item in iter_session_json_records(data_root, on_error=record_load_failure):
        json_session_count += 1
        try:
            session_repository.save(item.token, item.record)
            sessions_upserted_count += 1
        except Exception as exc:
            failures.append(
                {
                    "token_hash": token_sha256(item.token),
                    "error": exc.__class__.__name__,
                }
            )

    return {
        "domain": "sessions",
        "json_session_count": json_session_count,
        "sessions_upserted_count": sessions_upserted_count,
        "failed_count": len(failures),
        "failures": failures,
        "ok": len(failures) == 0,
    }


def write_backfill_summary(summary: dict, output_path: str | Path) -> Path:
    """Write a sanitized sessions backfill summary JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
