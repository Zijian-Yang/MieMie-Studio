#!/usr/bin/env python3
"""Clean PostgreSQL-only canary user config residue before strict reconciliation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mark PostgreSQL-only canary user configs deleted when no JSON config mirror exists."
    )
    parser.add_argument("--data-root", default=str(BACKEND_ROOT / "data"))
    parser.add_argument(
        "--output",
        default=str(
            REPO_ROOT
            / "docs/reports/artifacts/2026-06-07-postgres-upgrade-rollout/canary-user-config-cleanup.json"
        ),
    )
    parser.add_argument("--username-prefix", default="canary_")
    return parser.parse_args()


def json_config_user_ids(data_root: Path) -> set[str]:
    users_root = data_root / "users"
    if not users_root.exists():
        return set()
    return {
        user_dir.name
        for user_dir in users_root.iterdir()
        if user_dir.is_dir() and (user_dir / "config.json").exists()
    }


def main() -> int:
    args = parse_args()

    from sqlalchemy import select, update
    from sqlalchemy.pool import NullPool

    from app.db.engine import create_database_engine
    from app.db.schema.user_config import user_configs, users

    data_root = Path(args.data_root)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_config_ids = json_config_user_ids(data_root)
    now = datetime.now(timezone.utc)
    cleaned: list[dict[str, str]] = []

    engine = create_database_engine(poolclass=NullPool)
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                select(users.c.id, users.c.username)
                .join(user_configs, user_configs.c.user_id == users.c.id)
                .where(users.c.deleted_at.is_(None))
                .where(user_configs.c.deleted_at.is_(None))
                .where(users.c.username.like(f"{args.username_prefix}%"))
            ).mappings().all()

            for row in rows:
                user_id = row["id"]
                if user_id in json_config_ids:
                    continue
                conn.execute(
                    update(user_configs)
                    .where(user_configs.c.user_id == user_id)
                    .where(user_configs.c.deleted_at.is_(None))
                    .values(deleted_at=now, updated_at=now)
                )
                cleaned.append({"user_id": user_id, "username": row["username"]})
    finally:
        engine.dispose()

    summary = {
        "ok": True,
        "username_prefix": args.username_prefix,
        "json_config_count": len(json_config_ids),
        "cleaned_count": len(cleaned),
        "cleaned": cleaned,
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
