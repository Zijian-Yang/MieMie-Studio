#!/usr/bin/env python3
"""Verify the isolated PostgreSQL restore rehearsal safety contract."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "postgres_restore_rehearsal.sh"


def main() -> int:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    content = SCRIPT.read_text(encoding="utf-8")
    required = [
        "cleanup_restore_database",
        'COMPOSE_FILE_2="${COMPOSE_FILE_2-docker-compose.pre.override.yml}"',
        "trap cleanup_restore_database EXIT",
        'od -An -N5 -c "$DUMP_FILE"',
        '"PGDMP"',
        "pg_restore --exit-on-error --no-owner --no-privileges",
        'psql -U "$POSTGRES_USER" -d "$0" -v ON_ERROR_STOP=1',
        "trap - EXIT",
    ]
    for fragment in required:
        if fragment not in content:
            raise AssertionError(f"missing restore contract: {fragment}")

    forbidden = ["docker compose down", "docker volume rm", "DROP DATABASE miemie"]
    for fragment in forbidden:
        if fragment in content:
            raise AssertionError(f"unsafe restore contract: {fragment}")

    print("postgres restore rehearsal verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
