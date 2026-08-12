"""Platform-level operations settings and run history models."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


OperationType = Literal["backup", "oss_test", "webhook_test", "restore_rehearsal"]
OperationStatus = Literal["queued", "running", "succeeded", "failed"]
OperationPartStatus = Literal["pending", "succeeded", "failed", "skipped"]
OperationTrigger = Literal["manual", "scheduled", "cli"]


def validate_backup_subdirectory(value: str) -> str:
    normalized = value.strip().strip("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or value.strip().startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
    ):
        raise ValueError("backup_local_subdirectory_invalid")
    return path.as_posix()


def validate_oss_prefix(value: str) -> str:
    normalized = value.strip().strip("/")
    if not normalized or "\\" in value or any(
        part in {"", ".", ".."} for part in PurePosixPath(normalized).parts
    ):
        raise ValueError("backup_oss_prefix_invalid")
    return normalized


def validate_https_endpoint(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().rstrip("/")
    parts = urlsplit(normalized)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("backup_oss_endpoint_invalid")
    if parts.query or parts.fragment:
        raise ValueError("backup_oss_endpoint_invalid")
    return normalized


def validate_webhook_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    parts = urlsplit(normalized)
    loopback = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if parts.scheme not in ({"https"} if not loopback else {"http", "https"}):
        raise ValueError("webhook_url_invalid")
    if not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError("webhook_url_invalid")
    return normalized


class PlatformOperationsSettings(BaseModel):
    backup_enabled: bool = False
    backup_schedule: str = "03:00"
    backup_retention_days: int = Field(default=30, ge=1, le=3650)
    backup_min_keep: int = Field(default=7, ge=1, le=365)
    backup_local_subdirectory: str = "postgres"
    backup_oss_enabled: bool = False
    backup_oss_endpoint: str | None = None
    backup_oss_bucket_name: str | None = None
    backup_oss_prefix: str = "miemie/backups"
    backup_oss_access_key_id: str | None = None
    backup_oss_access_key_secret: str | None = None
    webhook_enabled: bool = False
    webhook_url: str | None = None
    webhook_timeout_seconds: int = Field(default=10, ge=1, le=30)
    webhook_retry_count: int = Field(default=2, ge=0, le=3)
    webhook_alert_on_warning: bool = False

    @field_validator("backup_schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        parts = value.strip().split(":")
        if len(parts) != 2 or not all(part.isdigit() and len(part) == 2 for part in parts):
            raise ValueError("backup_schedule_invalid")
        hour, minute = map(int, parts)
        if hour > 23 or minute > 59:
            raise ValueError("backup_schedule_invalid")
        return f"{hour:02d}:{minute:02d}"

    @field_validator("backup_local_subdirectory")
    @classmethod
    def validate_subdirectory(cls, value: str) -> str:
        return validate_backup_subdirectory(value)

    @field_validator("backup_oss_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        return validate_oss_prefix(value)

    @field_validator("backup_oss_endpoint")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        return validate_https_endpoint(value)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, value: str | None) -> str | None:
        return validate_webhook_url(value)

    @model_validator(mode="after")
    def validate_complete_configuration(self):
        if self.backup_min_keep > self.backup_retention_days:
            raise ValueError("backup_min_keep_exceeds_retention")
        if self.backup_oss_enabled and not all(
            (
                self.backup_oss_endpoint,
                self.backup_oss_bucket_name,
                self.backup_oss_access_key_id,
                self.backup_oss_access_key_secret,
            )
        ):
            raise ValueError("backup_oss_configuration_incomplete")
        if self.webhook_enabled and not self.webhook_url:
            raise ValueError("webhook_configuration_incomplete")
        return self


class PlatformOperationsSettingsPatch(BaseModel):
    backup_enabled: bool | None = None
    backup_schedule: str | None = None
    backup_retention_days: int | None = Field(default=None, ge=1, le=3650)
    backup_min_keep: int | None = Field(default=None, ge=1, le=365)
    backup_local_subdirectory: str | None = None
    backup_oss_enabled: bool | None = None
    backup_oss_endpoint: str | None = None
    backup_oss_bucket_name: str | None = None
    backup_oss_prefix: str | None = None
    backup_oss_access_key_id: str | None = Field(default=None, min_length=1, max_length=512)
    backup_oss_access_key_secret: str | None = Field(default=None, min_length=1, max_length=512)
    clear_backup_oss_credentials: bool = False
    webhook_enabled: bool | None = None
    webhook_url: str | None = Field(default=None, min_length=1, max_length=2048)
    clear_webhook_url: bool = False
    webhook_timeout_seconds: int | None = Field(default=None, ge=1, le=30)
    webhook_retry_count: int | None = Field(default=None, ge=0, le=3)
    webhook_alert_on_warning: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("platform_operations_no_changes")
        if self.clear_backup_oss_credentials and (
            "backup_oss_access_key_id" in self.model_fields_set
            or "backup_oss_access_key_secret" in self.model_fields_set
        ):
            raise ValueError("backup_oss_secret_update_conflict")
        if self.clear_webhook_url and "webhook_url" in self.model_fields_set:
            raise ValueError("webhook_secret_update_conflict")
        for name in self.model_fields_set:
            if name not in {"clear_backup_oss_credentials", "clear_webhook_url"} and getattr(
                self, name
            ) is None:
                raise ValueError("platform_operations_null_not_allowed")
        return self


class MaskedPlatformOperationsSettings(BaseModel):
    backup_enabled: bool
    backup_schedule: str
    backup_retention_days: int
    backup_min_keep: int
    backup_local_subdirectory: str
    backup_oss_enabled: bool
    backup_oss_endpoint: str | None = None
    backup_oss_bucket_name: str | None = None
    backup_oss_prefix: str
    backup_oss_credentials_configured: bool
    backup_oss_access_key_id_masked: str = ""
    webhook_enabled: bool
    webhook_configured: bool
    webhook_url_masked: str = ""
    webhook_timeout_seconds: int
    webhook_retry_count: int
    webhook_alert_on_warning: bool


class OperationRun(BaseModel):
    id: str
    operation_type: OperationType
    status: OperationStatus = "queued"
    trigger_source: OperationTrigger
    idempotency_key: str | None = None
    requested_by: str | None = None
    local_status: OperationPartStatus = "pending"
    oss_status: OperationPartStatus = "pending"
    local_path_relative: str | None = None
    oss_object_key: str | None = None
    oss_etag: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    error_category: str | None = None
    artifact_relative_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class OperationRunPage(BaseModel):
    items: list[OperationRun]
    total: int


__all__ = [
    "MaskedPlatformOperationsSettings",
    "OperationRun",
    "OperationRunPage",
    "PlatformOperationsSettings",
    "PlatformOperationsSettingsPatch",
    "validate_backup_subdirectory",
]
