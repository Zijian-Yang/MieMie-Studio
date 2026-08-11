#!/usr/bin/env python3
"""Verify PostgreSQL operational cron installer dry-run contract."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "postgres_install_operational_cron.sh"


def _write_stub(script_path: Path, marker_name: str) -> None:
    script_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "mkdir -p \"$ARTIFACT_DIR\"\n"
        f"printf 'passed\\n' > \"$ARTIFACT_DIR/{marker_name}\"\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def main() -> int:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT_DIR, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)

    with tempfile.TemporaryDirectory(prefix="miemie-operational-cron-") as temp_dir:
        artifact = Path(temp_dir) / "artifact"
        cron_target = Path(temp_dir) / "miemie-postgres-ops"
        install_root = Path(temp_dir) / "install-root"
        scripts_dir = install_root / "scripts"
        scripts_dir.mkdir(parents=True)
        _write_stub(scripts_dir / "postgres_operational_readiness.sh", "readiness-ran")
        _write_stub(scripts_dir / "postgres_backup_retention.sh", "retention-ran")
        _write_stub(scripts_dir / "postgres_database_snapshot.sh", "snapshot-ran")
        env = {
            **os.environ,
            "RUN_ID": "verify-operational-cron",
            "ARTIFACT_DIR": str(artifact),
            "CRON_FILE": str(cron_target),
            "INSTALL_ROOT": str(install_root),
            "ALERT_ENV_FILE": str(Path(temp_dir) / "missing-alert.env"),
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(f"dry-run failed: {result.returncode}\n{result.stdout}\n{result.stderr}")
        status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
        preview = (artifact / "miemie-postgres-ops.cron").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert not cron_target.exists()
        required = [
            str(Path(temp_dir) / "missing-alert.env"),
            "set -a; .",
            "POSTGRES_OPS_TRIGGER=cron",
            "CONFIRM_POSTGRES_OPERATIONAL_READINESS=run",
            "POSTGRES_OPS_BACKUP_RESTORE=run",
            "scripts/postgres_operational_readiness.sh",
            "CONFIRM_POSTGRES_BACKUP_RETENTION=prune",
            "scripts/postgres_backup_retention.sh",
            "CONFIRM_POSTGRES_DATABASE_SNAPSHOT=run",
            "scripts/postgres_database_snapshot.sh",
            "postgres-operational-readiness-cron.log",
            "postgres-backup-retention-cron.log",
            "postgres-database-snapshot-cron.log",
        ]
        for fragment in required:
            assert fragment in preview, fragment

        cron_commands = [
            line.split(maxsplit=6)[6]
            for line in preview.splitlines()
            if line and not line.startswith(("#", "SHELL=", "PATH="))
        ]
        assert len(cron_commands) == 3
        for command in cron_commands:
            command_result = subprocess.run(
                ["bash", "-lc", command],
                cwd=install_root,
                check=False,
                text=True,
                capture_output=True,
            )
            if command_result.returncode != 0:
                raise AssertionError(
                    "generated cron command failed before running its task: "
                    f"{shlex.join(['bash', '-lc', command])}\n"
                    f"stdout={command_result.stdout}\nstderr={command_result.stderr}"
                )

        validation_root = install_root / "validation-artifacts"
        assert list(validation_root.glob("postgres-ops-*/readiness-ran"))
        assert list(validation_root.glob("postgres-backup-retention-*/retention-ran"))
        assert list(validation_root.glob("postgres-database-snapshot-*/snapshot-ran"))
        assert (install_root / "logs" / "postgres-operational-readiness-cron.log").exists()
        assert (install_root / "logs" / "postgres-backup-retention-cron.log").exists()
        assert (install_root / "logs" / "postgres-database-snapshot-cron.log").exists()

    print("postgres operational cron verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
