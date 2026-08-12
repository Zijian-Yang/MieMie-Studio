"""Dedicated Aliyun OSS client for encrypted platform backup settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
import uuid

from app.models.platform_operations import PlatformOperationsSettings


class BackupOSSError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class OSSOperationResult:
    succeeded: bool
    object_key: str
    etag: str | None = None
    size_bytes: int | None = None


def _default_bucket_factory(
    access_key_id: str,
    access_key_secret: str,
    endpoint: str,
    bucket_name: str,
):
    try:
        import oss2
    except ImportError as exc:
        raise BackupOSSError("oss_sdk_unavailable") from exc
    auth = oss2.Auth(access_key_id, access_key_secret)
    return oss2.Bucket(auth, endpoint, bucket_name)


class BackupOSSClient:
    def __init__(
        self,
        *,
        bucket_factory: Callable = _default_bucket_factory,
        id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ):
        self._bucket_factory = bucket_factory
        self._id_factory = id_factory

    @staticmethod
    def _configuration(settings: PlatformOperationsSettings) -> tuple[str, ...]:
        values = (
            settings.backup_oss_access_key_id,
            settings.backup_oss_access_key_secret,
            settings.backup_oss_endpoint,
            settings.backup_oss_bucket_name,
        )
        if not settings.backup_oss_enabled or not all(values):
            raise BackupOSSError("oss_configuration_incomplete")
        return tuple(str(value) for value in values)

    def _bucket(self, settings: PlatformOperationsSettings):
        try:
            return self._bucket_factory(*self._configuration(settings))
        except BackupOSSError:
            raise
        except Exception as exc:
            raise BackupOSSError("oss_client_initialization_failed") from exc

    @staticmethod
    def _etag(response) -> str | None:
        value = getattr(response, "etag", None)
        return str(value).strip('"') if value else None

    @staticmethod
    def _validate_object_key(key: str, prefix: str) -> str:
        normalized_prefix = prefix.strip("/")
        path = PurePosixPath(key)
        if (
            not key
            or key.startswith("/")
            or "\\" in key
            or any(part in {"", ".", ".."} for part in path.parts)
            or not key.startswith(f"{normalized_prefix}/")
        ):
            raise BackupOSSError("oss_object_key_invalid")
        return path.as_posix()

    def object_key(self, local_path: Path, settings: PlatformOperationsSettings) -> str:
        if not local_path.name or local_path.name in {".", ".."}:
            raise BackupOSSError("oss_backup_file_invalid")
        return self._validate_object_key(
            f"{settings.backup_oss_prefix}/{local_path.name}",
            settings.backup_oss_prefix,
        )

    def test(self, settings: PlatformOperationsSettings) -> OSSOperationResult:
        bucket = self._bucket(settings)
        key = self._validate_object_key(
            f"{settings.backup_oss_prefix}/_checks/{self._id_factory()}.txt",
            settings.backup_oss_prefix,
        )
        failure: BackupOSSError | None = None
        etag: str | None = None
        try:
            bucket.put_object(key, b"miemie-platform-oss-check")
            response = bucket.head_object(key)
            etag = self._etag(response)
        except Exception as exc:
            failure = BackupOSSError("oss_test_verification_failed")
            failure.__cause__ = exc
        try:
            bucket.delete_object(key)
        except Exception as exc:
            if failure is None:
                raise BackupOSSError("oss_test_cleanup_failed") from exc
        if failure is not None:
            raise failure
        return OSSOperationResult(succeeded=True, object_key=key, etag=etag)

    def upload(
        self,
        local_path: Path,
        object_key: str,
        settings: PlatformOperationsSettings,
    ) -> OSSOperationResult:
        if not local_path.is_file() or local_path.stat().st_size <= 0:
            raise BackupOSSError("oss_backup_file_invalid")
        key = self._validate_object_key(object_key, settings.backup_oss_prefix)
        bucket = self._bucket(settings)
        try:
            response = bucket.put_object_from_file(key, str(local_path))
        except Exception as exc:
            raise BackupOSSError("oss_upload_failed") from exc
        return OSSOperationResult(
            succeeded=True,
            object_key=key,
            etag=self._etag(response),
            size_bytes=local_path.stat().st_size,
        )


__all__ = ["BackupOSSClient", "BackupOSSError", "OSSOperationResult"]
