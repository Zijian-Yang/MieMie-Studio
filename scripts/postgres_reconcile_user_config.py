#!/usr/bin/env python3
"""Reconcile user/config JSON files with PostgreSQL."""

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
        description="Reconcile users and per-user config JSON files against PostgreSQL."
    )
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output-dir",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r36-user-config-backfill-reconcile"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.repositories.user_config import PostgresUserConfigRepository, PostgresUserRepository
    from app.services.migration.reconcile_user_config import (
        reconcile_user_config,
        write_reconcile_reports,
    )

    engine = create_database_engine(poolclass=NullPool)
    try:
        summary = reconcile_user_config(
            args.data_root,
            PostgresUserRepository(engine),
            PostgresUserConfigRepository(engine),
        )
        write_reconcile_reports(summary, args.output_dir)
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
