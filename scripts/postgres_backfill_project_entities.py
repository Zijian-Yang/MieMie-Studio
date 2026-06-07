#!/usr/bin/env python3
"""Backfill per-user project editing entity JSON files into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill project editing entities from JSON files into PostgreSQL."
    )
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r25-project-entities-backfill-reconcile/project_entities_backfill.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.repositories.project_entities import PostgresProjectEntityRepository
    from app.services.migration.backfill_project_entities import (
        backfill_project_entities,
        write_backfill_summary,
    )

    engine = create_database_engine(poolclass=NullPool)

    def repository_factory(user_id: str) -> PostgresProjectEntityRepository:
        return PostgresProjectEntityRepository(engine, user_id)

    try:
        summary = backfill_project_entities(args.data_root, repository_factory)
        write_backfill_summary(summary, args.output)
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
