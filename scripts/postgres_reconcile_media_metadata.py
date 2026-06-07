#!/usr/bin/env python3
"""Reconcile per-user media metadata JSON files with PostgreSQL."""

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
        description="Reconcile media metadata JSON files against PostgreSQL."
    )
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output-dir",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/r20-media-metadata-backfill-reconcile"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.repositories.media_assets import (
        PostgresMediaAssetRepository,
        PostgresTextItemRepository,
    )
    from app.services.migration.reconcile_media_metadata import (
        reconcile_media_metadata,
        write_reconcile_reports,
    )

    engine = create_database_engine(poolclass=NullPool)

    def media_repository_factory(user_id: str) -> PostgresMediaAssetRepository:
        return PostgresMediaAssetRepository(engine, user_id)

    def text_repository_factory(user_id: str) -> PostgresTextItemRepository:
        return PostgresTextItemRepository(engine, user_id)

    try:
        summary = reconcile_media_metadata(
            args.data_root,
            media_repository_factory,
            text_repository_factory,
        )
        write_reconcile_reports(summary, args.output_dir)
    finally:
        engine.dispose()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
