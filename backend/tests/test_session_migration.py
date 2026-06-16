import json

from app.services.migration.backfill_sessions import (
    backfill_sessions,
    iter_session_json_records,
)
from app.services.migration.reconcile_sessions import (
    reconcile_sessions,
    render_reconcile_markdown,
)
from app.services.session_store import SessionRecord


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


class _SessionRepository:
    def __init__(self):
        self.records = {}
        self.saved = []

    def save(self, token, record):
        self.records[token] = record
        self.saved.append(token)

    def list_all(self):
        return dict(self.records)


def test_iter_session_json_records_supports_current_and_legacy_shapes(tmp_path):
    _write_json(
        tmp_path / "sessions.json",
        {
            "raw-token-1": {"user_id": "user-1", "created_at": "2026-06-17T08:00:00+00:00"},
            "legacy-token": "user-2",
            "invalid-token": {"created_at": "missing-user"},
        },
    )

    failures = []
    records = list(iter_session_json_records(tmp_path, on_error=lambda token, exc: failures.append((token, exc.__class__.__name__))))

    assert [(item.token, item.record) for item in records] == [
        ("legacy-token", SessionRecord(user_id="user-2", created_at="")),
        ("raw-token-1", SessionRecord(user_id="user-1", created_at="2026-06-17T08:00:00+00:00")),
    ]
    assert failures == [("invalid-token", "ValueError")]


def test_backfill_sessions_upserts_without_exposing_raw_tokens(tmp_path):
    _write_json(
        tmp_path / "sessions.json",
        {"raw-token-secret": {"user_id": "user-1", "created_at": "2026-06-17T08:00:00+00:00"}},
    )
    repository = _SessionRepository()

    summary = backfill_sessions(tmp_path, repository)

    assert summary == {
        "domain": "sessions",
        "json_session_count": 1,
        "sessions_upserted_count": 1,
        "failed_count": 0,
        "failures": [],
        "ok": True,
    }
    assert repository.saved == ["raw-token-secret"]
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "raw-token-secret" not in serialized


def test_reconcile_sessions_compares_token_hashes_and_safe_fields(tmp_path):
    _write_json(
        tmp_path / "sessions.json",
        {
            "raw-token-secret": {"user_id": "user-1", "created_at": "2026-06-17T08:00:00+00:00"},
            "json-only-token": {"user_id": "user-2", "created_at": "2026-06-17T08:05:00+00:00"},
        },
    )
    repository = _SessionRepository()
    repository.save("raw-token-secret", SessionRecord(user_id="user-1", created_at="2026-06-17T08:00:00+00:00"))
    repository.save("postgres-only-token", SessionRecord(user_id="user-3", created_at="2026-06-17T08:10:00+00:00"))

    summary = reconcile_sessions(tmp_path, repository)
    markdown = render_reconcile_markdown(summary)

    assert summary["ok"] is False
    assert summary["json_session_count"] == 2
    assert summary["postgres_session_count"] == 2
    assert len(summary["missing_in_postgres"]) == 1
    assert len(summary["missing_in_json"]) == 1
    assert summary["field_differences"] == []
    assert "token_hash" in summary["missing_in_postgres"][0]
    assert "json-only-token" not in json.dumps(summary, ensure_ascii=False)
    assert "postgres-only-token" not in markdown
    assert "raw-token-secret" not in markdown
