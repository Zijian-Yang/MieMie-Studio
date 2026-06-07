#!/usr/bin/env python3
"""Reconcile per-user project JSON files with PostgreSQL."""

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
        description="Reconcile projects JSON files against PostgreSQL."
    )
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output-dir",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r14-projects-backfill-reconcile"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.repositories.projects import PostgresProjectRepository
    from app.services.migration.reconcile_projects import (
        reconcile_projects,
        write_reconcile_reports,
    )

    engine = create_database_engine(poolclass=NullPool)

    def repository_factory(user_id: str) -> PostgresProjectRepository:
        return PostgresProjectRepository(engine, user_id)

    try:
        summary = reconcile_projects(args.data_root, repository_factory)
        write_reconcile_reports(summary, args.output_dir)
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
