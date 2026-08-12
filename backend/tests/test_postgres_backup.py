from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pytest

from app.models.platform_operations import PlatformOperationsSettings
from app.services.postgres_backup import BackupExecutionError, PostgresBackupExecutor


DATABASE_URL = "postgresql+psycopg://miemie:p%40ssword@postgres:5432/miemie"


def _settings(**changes):
    values = {
        "backup_local_subdirectory": "postgres",
        "backup_retention_days": 30,
        "backup_min_keep": 2,
    }
    values.update(changes)
    return PlatformOperationsSettings(**values)


def _write_executable(path: Path, body: str):
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def fake_postgres_tools(tmp_path):
    dump = tmp_path / "pg_dump"
    restore = tmp_path / "pg_restore"
    psql = tmp_path / "psql"
    log = tmp_path / "postgres-tools.jsonl"
    _write_executable(
        dump,
        """import json, os, pathlib, sys
if "--version" in sys.argv:
    print(os.environ.get("FAKE_PG_DUMP_VERSION", "pg_dump (PostgreSQL) 16.4"))
    raise SystemExit(0)
entry = {
    "tool": "pg_dump",
    "argv": sys.argv[1:],
    "has_password": bool(os.environ.get("PGPASSWORD")),
    "has_database_url": "MIEMIE_DATABASE_URL" in os.environ,
    "host": os.environ.get("PGHOST"),
    "database": os.environ.get("PGDATABASE"),
}
with open(os.environ["FAKE_POSTGRES_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry) + "\\n")
if os.environ.get("FAKE_PG_DUMP_FAIL") == "1":
    raise SystemExit(7)
target = pathlib.Path(sys.argv[sys.argv.index("--file") + 1])
target.write_bytes(b"PGDMP\\x01platform-backup")
""",
    )
    _write_executable(
        restore,
        """import json, os, pathlib, sys
entry = {"tool": "pg_restore", "argv": sys.argv[1:]}
with open(os.environ["FAKE_POSTGRES_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry) + "\\n")
target = pathlib.Path(sys.argv[-1])
if "--list" not in sys.argv or not target.read_bytes().startswith(b"PGDMP"):
    raise SystemExit(9)
""",
    )
    _write_executable(
        psql,
        """import os
print(os.environ.get("FAKE_PG_SERVER_VERSION_NUM", "160004"))
""",
    )
    return dump, restore, psql, log


def _executor(root, tools, monkeypatch, **changes):
    dump, restore, psql, log = tools
    monkeypatch.setenv("FAKE_POSTGRES_LOG", str(log))
    monkeypatch.setenv("MIEMIE_DATABASE_URL", DATABASE_URL)
    values = {
        "backup_root": root,
        "pg_dump_binary": str(dump),
        "pg_restore_binary": str(restore),
        "psql_binary": str(psql),
        "clock": lambda: datetime(2026, 8, 12, 3, 4, 5, tzinfo=timezone.utc),
        "environment_provider": lambda: {
            "PATH": os.environ.get("PATH", ""),
            "FAKE_POSTGRES_LOG": os.environ["FAKE_POSTGRES_LOG"],
            **(
                {"FAKE_PG_DUMP_VERSION": os.environ["FAKE_PG_DUMP_VERSION"]}
                if "FAKE_PG_DUMP_VERSION" in os.environ
                else {}
            ),
            **(
                {"FAKE_PG_SERVER_VERSION_NUM": os.environ["FAKE_PG_SERVER_VERSION_NUM"]}
                if "FAKE_PG_SERVER_VERSION_NUM" in os.environ
                else {}
            ),
            **(
                {"FAKE_PG_DUMP_FAIL": os.environ["FAKE_PG_DUMP_FAIL"]}
                if "FAKE_PG_DUMP_FAIL" in os.environ
                else {}
            ),
        },
    }
    values.update(changes)
    return PostgresBackupExecutor(**values), log


def test_backup_uses_private_env_validates_checksums_and_atomically_finishes(
    tmp_path, fake_postgres_tools, monkeypatch
):
    executor, log = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)

    result = executor.run("run-123", _settings())

    assert result.local_path.exists()
    assert result.local_path.name == "miemie-postgres-20260812-030405-run-123.dump"
    assert result.local_path_relative == f"postgres/{result.local_path.name}"
    assert result.size_bytes == len(b"PGDMP\x01platform-backup")
    assert len(result.sha256) == 64
    assert result.pruned_relative_paths == []
    assert not list(result.local_path.parent.glob("*.tmp-*"))
    assert oct(result.local_path.stat().st_mode & 0o777) == "0o600"
    checksum_path = result.local_path.with_name(result.local_path.name + ".sha256")
    assert checksum_path.read_text(encoding="ascii") == (
        f"{result.sha256}  {result.local_path.name}\n"
    )
    assert oct(checksum_path.stat().st_mode & 0o777) == "0o600"

    entries = [json.loads(line) for line in log.read_text().splitlines()]
    dump_entry, restore_entry = entries
    assert dump_entry["tool"] == "pg_dump"
    assert dump_entry["has_password"] is True
    assert dump_entry["has_database_url"] is False
    assert dump_entry["host"] == "postgres"
    assert dump_entry["database"] == "miemie"
    assert "p@ssword" not in repr(entries)
    assert DATABASE_URL not in repr(entries)
    assert "--format=custom" in dump_entry["argv"]
    assert "--no-password" in dump_entry["argv"]
    assert "--list" in restore_entry["argv"]


def test_postgres_child_does_not_inherit_platform_or_provider_secrets(
    tmp_path, fake_postgres_tools, monkeypatch
):
    monkeypatch.setenv("MIEMIE_PLATFORM_ENCRYPTION_KEY", "must-not-reach-pg-tools")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "must-not-reach-pg-tools")
    seen = {}

    def runner(command, **kwargs):
        seen.update(kwargs["env"])
        if "--version" in command:
            return type("Result", (), {"returncode": 0, "stdout": b"pg_dump (PostgreSQL) 16.4"})()
        if "psql" in command[0]:
            return type("Result", (), {"returncode": 0, "stdout": b"160004\n"})()
        if "pg_dump" in command[0]:
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMPbackup")
        return type("Result", (), {"returncode": 0, "stdout": b""})()

    dump, restore, psql, _ = fake_postgres_tools
    executor = PostgresBackupExecutor(
        backup_root=tmp_path / "backups",
        pg_dump_binary=str(dump),
        pg_restore_binary=str(restore),
        psql_binary=str(psql),
        process_runner=runner,
    )
    monkeypatch.setenv("MIEMIE_DATABASE_URL", DATABASE_URL)

    executor.run("run-minimal-env", _settings())

    assert "MIEMIE_PLATFORM_ENCRYPTION_KEY" not in seen
    assert "DASHSCOPE_API_KEY" not in seen
    assert "MIEMIE_DATABASE_URL" not in seen
    assert seen["PGPASSWORD"] == "p@ssword"


def test_dump_failure_removes_temporary_file_and_returns_stable_error(
    tmp_path, fake_postgres_tools, monkeypatch
):
    executor, _ = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)
    monkeypatch.setenv("FAKE_PG_DUMP_FAIL", "1")

    with pytest.raises(BackupExecutionError) as exc:
        executor.run("run-failed", _settings())

    assert exc.value.category == "pg_dump_failed"
    assert str(exc.value) == "pg_dump_failed"
    assert DATABASE_URL not in str(exc.value)
    assert not list((tmp_path / "backups").rglob("*.tmp-*"))
    assert not list((tmp_path / "backups").rglob("*.dump"))


def test_restore_validation_failure_never_publishes_invalid_dump(
    tmp_path, fake_postgres_tools, monkeypatch
):
    _, restore, _, _ = fake_postgres_tools
    _write_executable(restore, "raise SystemExit(9)\n")
    executor, _ = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)

    with pytest.raises(BackupExecutionError) as exc:
        executor.run("run-invalid", _settings())

    assert exc.value.category == "pg_restore_validation_failed"
    assert not list((tmp_path / "backups").rglob("*.dump"))
    assert not list((tmp_path / "backups").rglob("*.tmp-*"))


def test_checksum_publication_failure_removes_partially_published_backup(
    tmp_path, fake_postgres_tools, monkeypatch
):
    executor, _ = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)
    real_replace = os.replace
    calls = 0

    def fail_second_replace(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated checksum publication failure")
        return real_replace(source, target)

    monkeypatch.setattr("app.services.postgres_backup.os.replace", fail_second_replace)

    with pytest.raises(OSError, match="checksum publication failure"):
        executor.run("run-partial", _settings())

    assert not list((tmp_path / "backups").rglob("*.dump"))
    assert not list((tmp_path / "backups").rglob("*.sha256"))
    assert not list((tmp_path / "backups").rglob("*.tmp-*"))


def test_client_server_major_mismatch_stops_before_dump(
    tmp_path, fake_postgres_tools, monkeypatch
):
    monkeypatch.setenv("FAKE_PG_DUMP_VERSION", "pg_dump (PostgreSQL) 17.2")
    executor, log = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)

    with pytest.raises(BackupExecutionError) as exc:
        executor.run("run-version-mismatch", _settings())

    assert exc.value.category == "postgres_client_server_version_mismatch"
    assert not log.exists()
    assert not list((tmp_path / "backups").rglob("*.dump"))


def test_retention_keeps_minimum_and_recent_backups_deterministically(
    tmp_path, fake_postgres_tools, monkeypatch
):
    backup_root = tmp_path / "backups"
    target = backup_root / "postgres"
    target.mkdir(parents=True)
    old_time = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
    recent_time = datetime(2026, 8, 11, tzinfo=timezone.utc).timestamp()
    files = []
    for index, modified in enumerate((old_time, old_time + 1, recent_time)):
        path = target / f"miemie-postgres-existing-{index}.dump"
        path.write_bytes(b"PGDMPexisting")
        path.with_name(path.name + ".sha256").write_text(
            f"{'a' * 64}  {path.name}\n", encoding="ascii"
        )
        os.utime(path, (modified, modified))
        files.append(path)
    unrelated = target / "do-not-delete.sql"
    unrelated.write_text("private", encoding="utf-8")
    executor, _ = _executor(backup_root, fake_postgres_tools, monkeypatch)

    result = executor.run(
        "run-retention",
        _settings(backup_retention_days=5, backup_min_keep=2),
    )

    assert result.pruned_relative_paths == [
        "postgres/miemie-postgres-existing-0.dump",
        "postgres/miemie-postgres-existing-1.dump",
    ]
    assert not files[0].exists()
    assert not files[1].exists()
    assert not files[0].with_name(files[0].name + ".sha256").exists()
    assert not files[1].with_name(files[1].name + ".sha256").exists()
    assert files[2].exists()
    assert files[2].with_name(files[2].name + ".sha256").exists()
    assert unrelated.exists()


@pytest.mark.parametrize(
    "subdirectory",
    ("../outside", "/absolute", "safe/../../outside", r"safe\\outside"),
)
def test_backup_subdirectory_cannot_escape_fixed_root(
    tmp_path, fake_postgres_tools, monkeypatch, subdirectory
):
    with pytest.raises(ValueError, match="backup_local_subdirectory_invalid"):
        settings = _settings(backup_local_subdirectory=subdirectory)
        executor, _ = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)
        executor.run("run-path", settings)


def test_existing_symlink_cannot_escape_backup_root(
    tmp_path, fake_postgres_tools, monkeypatch
):
    root = tmp_path / "backups"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    (root / "postgres").symlink_to(outside, target_is_directory=True)
    executor, _ = _executor(root, fake_postgres_tools, monkeypatch)

    with pytest.raises(BackupExecutionError) as exc:
        executor.run("run-symlink", _settings())

    assert exc.value.category == "backup_path_escapes_root"
    assert list(outside.iterdir()) == []


def test_database_url_is_required_and_driver_must_be_postgresql(
    tmp_path, fake_postgres_tools, monkeypatch
):
    executor, _ = _executor(tmp_path / "backups", fake_postgres_tools, monkeypatch)
    for value in ("", "sqlite:///tmp/example.db"):
        monkeypatch.setenv("MIEMIE_DATABASE_URL", value)
        with pytest.raises(BackupExecutionError) as exc:
            executor.run("run-database", _settings())
        assert exc.value.category == "database_configuration_invalid"
