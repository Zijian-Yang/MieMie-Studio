#!/usr/bin/env python3
"""Backfill file-backed sessions into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill sessions.json into PostgreSQL.")
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r59-sessions-backfill-reconcile/sessions_backfill.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.repositories.sessions import PostgresSessionRepository
    from app.services.migration.backfill_sessions import backfill_sessions, write_backfill_summary

    engine = create_database_engine(poolclass=NullPool)
    try:
        summary = backfill_sessions(args.data_root, PostgresSessionRepository(engine))
        write_backfill_summary(summary, args.output)
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
