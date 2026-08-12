"""Low-privilege PostgreSQL custom-format backup execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Callable
import uuid

from sqlalchemy.engine import make_url

from app.models.platform_operations import PlatformOperationsSettings


_BACKUP_NAME = re.compile(r"^miemie-postgres-[A-Za-z0-9-]+\.dump$")
_RUN_ID = re.compile(r"^[A-Za-z0-9-]+$")


class BackupExecutionError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class BackupResult:
    local_path: Path
    local_path_relative: str
    sha256: str
    size_bytes: int
    pruned_relative_paths: list[str]


class PostgresBackupExecutor:
    def __init__(
        self,
        *,
        backup_root: str | Path = "/var/lib/miemie/backups",
        pg_dump_binary: str = "pg_dump",
        pg_restore_binary: str = "pg_restore",
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        process_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        environment_provider: Callable[[], dict[str, str]] | None = None,
    ):
        self._backup_root = Path(backup_root)
        self._pg_dump = pg_dump_binary
        self._pg_restore = pg_restore_binary
        self._clock = clock
        self._run_process = process_runner
        self._environment_provider = environment_provider or self._minimal_environment

    @staticmethod
    def _minimal_environment() -> dict[str, str]:
        return {
            name: os.environ[name]
            for name in ("PATH", "LANG", "LC_ALL", "TZ")
            if name in os.environ
        }

    def _database_environment(self) -> dict[str, str]:
        raw = os.getenv("MIEMIE_DATABASE_URL", "").strip()
        try:
            url = make_url(raw)
        except Exception as exc:
            raise BackupExecutionError("database_configuration_invalid") from exc
        if not raw or not url.drivername.startswith("postgresql"):
            raise BackupExecutionError("database_configuration_invalid")
        if not all((url.host, url.username, url.database)):
            raise BackupExecutionError("database_configuration_invalid")

        env = self._environment_provider()
        env.update(
            PGHOST=str(url.host),
            PGPORT=str(url.port or 5432),
            PGUSER=str(url.username),
            PGDATABASE=str(url.database),
            PGPASSWORD=str(url.password or ""),
            PGCONNECT_TIMEOUT="10",
        )
        query = dict(url.query)
        if query.get("sslmode"):
            env["PGSSLMODE"] = str(query["sslmode"])
        return env

    def _target_directory(self, subdirectory: str) -> tuple[Path, Path]:
        self._backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root = self._backup_root.resolve(strict=True)
        target = root / subdirectory
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        resolved = target.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise BackupExecutionError("backup_path_escapes_root") from exc
        return root, resolved

    def _execute(self, command: list[str], env: dict[str, str], category: str) -> None:
        try:
            result = self._run_process(
                command,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=3600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackupExecutionError(category) from exc
        if result.returncode != 0:
            raise BackupExecutionError(category)

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _fsync_file(path: Path) -> None:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _apply_retention(
        self,
        directory: Path,
        *,
        root: Path,
        now: datetime,
        retention_days: int,
        min_keep: int,
    ) -> list[str]:
        candidates = [
            path
            for path in directory.iterdir()
            if path.is_file() and not path.is_symlink() and _BACKUP_NAME.fullmatch(path.name)
        ]
        candidates.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
        threshold = now.timestamp() - retention_days * 86400
        pruned: list[str] = []
        for index, path in enumerate(candidates):
            if index < min_keep or path.stat().st_mtime >= threshold:
                continue
            relative = path.relative_to(root).as_posix()
            path.unlink()
            pruned.append(relative)
        if pruned:
            self._fsync_directory(directory)
        return sorted(pruned)

    def run(self, run_id: str, settings: PlatformOperationsSettings) -> BackupResult:
        if not _RUN_ID.fullmatch(run_id):
            raise BackupExecutionError("backup_run_id_invalid")
        env = self._database_environment()
        root, directory = self._target_directory(settings.backup_local_subdirectory)
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise BackupExecutionError("backup_clock_timezone_required")
        timestamp = now.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
        final_path = directory / f"miemie-postgres-{timestamp}-{run_id}.dump"
        temporary_path = directory / f".{final_path.name}.tmp-{uuid.uuid4().hex}"

        try:
            self._execute(
                [
                    self._pg_dump,
                    "--format=custom",
                    "--compress=6",
                    "--no-owner",
                    "--no-privileges",
                    "--no-password",
                    "--file",
                    str(temporary_path),
                ],
                env,
                "pg_dump_failed",
            )
            if not temporary_path.is_file() or temporary_path.stat().st_size <= 0:
                raise BackupExecutionError("pg_dump_output_invalid")
            os.chmod(temporary_path, 0o600)
            self._execute(
                [self._pg_restore, "--list", str(temporary_path)],
                env,
                "pg_restore_validation_failed",
            )
            checksum = self._checksum(temporary_path)
            size_bytes = temporary_path.stat().st_size
            self._fsync_file(temporary_path)
            os.replace(temporary_path, final_path)
            os.utime(final_path, (now.timestamp(), now.timestamp()))
            self._fsync_directory(directory)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        pruned = self._apply_retention(
            directory,
            root=root,
            now=now,
            retention_days=settings.backup_retention_days,
            min_keep=settings.backup_min_keep,
        )
        return BackupResult(
            local_path=final_path,
            local_path_relative=final_path.relative_to(root).as_posix(),
            sha256=checksum,
            size_bytes=size_bytes,
            pruned_relative_paths=pruned,
        )


__all__ = ["BackupExecutionError", "BackupResult", "PostgresBackupExecutor"]
