from datetime import datetime, timezone

from app.repositories.sessions import (
    row_to_session_record,
    session_to_row,
    token_sha256,
)
from app.services.session_store import SessionRecord


def test_token_hash_is_stable_and_does_not_expose_raw_token():
    token = "raw-token-secret"

    digest = token_sha256(token)

    assert digest == "59b184bb1b4e8c8e6133d119bcbdbb2740087227b5c9b2781ef9bb0db6d38978"
    assert token not in digest


def test_session_row_mapping_uses_token_hash_and_restores_record():
    record = SessionRecord(user_id="user-1", created_at="2026-06-17T08:30:00+00:00")

    row = session_to_row("raw-token-secret", record)

    assert row["token_hash"] == token_sha256("raw-token-secret")
    assert "token" not in row
    assert row["user_id"] == "user-1"
    assert row["created_at"] == datetime(2026, 6, 17, 8, 30, tzinfo=timezone.utc)
    assert row["last_seen_at"] == datetime(2026, 6, 17, 8, 30, tzinfo=timezone.utc)
    assert row["expires_at"] > row["created_at"]
    assert row["raw_session_snapshot"] == {"user_id": "user-1", "created_at": "2026-06-17T08:30:00+00:00"}
    assert row["deleted_at"] is None

    restored = row_to_session_record(row)

    assert restored == record


def test_session_row_mapping_handles_legacy_blank_created_at():
    record = SessionRecord(user_id="user-1", created_at="")

    row = session_to_row("legacy-token", record)

    assert row["created_at"].tzinfo is not None
    assert row["last_seen_at"] == row["created_at"]
    assert row_to_session_record(row) == SessionRecord(
        user_id="user-1",
        created_at=row["created_at"].isoformat(),
    )
