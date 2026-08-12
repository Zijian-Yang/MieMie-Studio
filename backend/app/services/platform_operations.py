"""Validated platform operations configuration and run lifecycle service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from app.models.platform_operations import (
    MaskedPlatformOperationsSettings,
    OperationRun,
    PlatformOperationsSettings,
    PlatformOperationsSettingsPatch,
)
from app.models.user import User
from app.repositories.platform_admin import AdminAuditEvent
from app.services.platform_crypto import PlatformSecretCipher


_PLAIN_FIELDS = {
    "backup_enabled",
    "backup_schedule",
    "backup_retention_days",
    "backup_min_keep",
    "backup_local_subdirectory",
    "backup_oss_enabled",
    "backup_oss_endpoint",
    "backup_oss_bucket_name",
    "backup_oss_prefix",
    "webhook_enabled",
    "webhook_timeout_seconds",
    "webhook_retry_count",
    "webhook_alert_on_warning",
}


class PlatformOperationsService:
    def __init__(self, *, settings_repository, run_repository, cipher: PlatformSecretCipher):
        self._settings = settings_repository
        self._runs = run_repository
        self._cipher = cipher

    def _runtime_from_row(self, row: dict[str, Any]) -> PlatformOperationsSettings:
        def decrypt(name: str) -> str | None:
            value = row.get(name)
            return self._cipher.decrypt(value) if value else None

        values = {name: row.get(name) for name in _PLAIN_FIELDS}
        values.update(
            backup_oss_access_key_id=decrypt("backup_oss_access_key_id_encrypted"),
            backup_oss_access_key_secret=decrypt("backup_oss_access_key_secret_encrypted"),
            webhook_url=decrypt("webhook_url_encrypted"),
        )
        return PlatformOperationsSettings(**values)

    def get_runtime_settings(self) -> PlatformOperationsSettings:
        return self._runtime_from_row(self._settings.get_operations_row())

    def _masked(self, settings: PlatformOperationsSettings) -> MaskedPlatformOperationsSettings:
        return MaskedPlatformOperationsSettings(
            **settings.model_dump(
                exclude={
                    "backup_oss_access_key_id",
                    "backup_oss_access_key_secret",
                    "webhook_url",
                }
            ),
            backup_oss_credentials_configured=bool(
                settings.backup_oss_access_key_id and settings.backup_oss_access_key_secret
            ),
            backup_oss_access_key_id_masked=self._cipher.mask(
                settings.backup_oss_access_key_id or ""
            ),
            webhook_configured=bool(settings.webhook_url),
            webhook_url_masked=self._cipher.mask(settings.webhook_url or ""),
        )

    def get_settings(self) -> MaskedPlatformOperationsSettings:
        return self._masked(self.get_runtime_settings())

    def update_settings(
        self,
        *,
        actor: User,
        patch: PlatformOperationsSettingsPatch,
        request_id: str | None = None,
    ) -> MaskedPlatformOperationsSettings:
        safe_changes: dict[str, Any] = {}
        for field in patch.model_fields_set & _PLAIN_FIELDS:
            safe_changes[field] = getattr(patch, field)
        if (
            "backup_oss_access_key_id" in patch.model_fields_set
            or "backup_oss_access_key_secret" in patch.model_fields_set
        ):
            safe_changes["backup_oss_credentials_changed"] = True
        if patch.clear_backup_oss_credentials:
            safe_changes["backup_oss_credentials_cleared"] = True
        if "webhook_url" in patch.model_fields_set:
            safe_changes["webhook_url_changed"] = True
        if patch.clear_webhook_url:
            safe_changes["webhook_url_cleared"] = True

        event = AdminAuditEvent(
            actor_user_id=actor.id,
            action="admin.platform.operations.update",
            target_type="platform_settings",
            target_id="platform",
            request_id=request_id,
            changes=safe_changes,
        )

        def mutate(row: dict[str, Any]):
            current = self._runtime_from_row(row)
            candidate_values = current.model_dump()
            for name in patch.model_fields_set & _PLAIN_FIELDS:
                candidate_values[name] = getattr(patch, name)
            if patch.clear_backup_oss_credentials:
                candidate_values["backup_oss_access_key_id"] = None
                candidate_values["backup_oss_access_key_secret"] = None
            else:
                for name in ("backup_oss_access_key_id", "backup_oss_access_key_secret"):
                    if name in patch.model_fields_set:
                        candidate_values[name] = getattr(patch, name)
            if patch.clear_webhook_url:
                candidate_values["webhook_url"] = None
            elif "webhook_url" in patch.model_fields_set:
                candidate_values["webhook_url"] = patch.webhook_url

            candidate = PlatformOperationsSettings(**candidate_values)
            values = {
                name: getattr(candidate, name)
                for name in patch.model_fields_set & _PLAIN_FIELDS
            }
            if patch.clear_backup_oss_credentials:
                values.update(
                    backup_oss_access_key_id_encrypted=None,
                    backup_oss_access_key_secret_encrypted=None,
                )
            else:
                for plain, encrypted in (
                    ("backup_oss_access_key_id", "backup_oss_access_key_id_encrypted"),
                    ("backup_oss_access_key_secret", "backup_oss_access_key_secret_encrypted"),
                ):
                    if plain in patch.model_fields_set:
                        secret = getattr(candidate, plain)
                        if secret is None:
                            raise ValueError("platform_operations_null_not_allowed")
                        values[encrypted] = self._cipher.encrypt(secret)
            if patch.clear_webhook_url:
                values["webhook_url_encrypted"] = None
            elif "webhook_url" in patch.model_fields_set:
                if candidate.webhook_url is None:
                    raise ValueError("platform_operations_null_not_allowed")
                values["webhook_url_encrypted"] = self._cipher.encrypt(
                    candidate.webhook_url
                )
            return values, self._masked(candidate)

        return self._settings.mutate_operations(mutate, event)

    def queue_operation(
        self,
        *,
        operation_type: str,
        source: str,
        actor_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[OperationRun, bool]:
        now = datetime.now(timezone.utc)
        run = OperationRun(
            id=str(uuid.uuid4()),
            operation_type=operation_type,
            trigger_source=source,
            requested_by=actor_id,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        return self._runs.create(run)

    def claim_run(self, run_id: str) -> OperationRun | None:
        return self._runs.claim(run_id)

    def complete_run(self, run_id: str, **values) -> OperationRun:
        return self._runs.finish(run_id, succeeded=True, values=values)

    def fail_run(self, run_id: str, *, error_category: str, **values) -> OperationRun:
        return self._runs.finish(
            run_id,
            succeeded=False,
            values={**values, "error_category": error_category},
        )

    def list_runs(self, **kwargs):
        return self._runs.list(**kwargs)


def build_platform_operations_service() -> PlatformOperationsService:
    from app.repositories.user_config_runtime import (
        build_operation_run_repository,
        build_platform_settings_repository,
    )
    from app.services.platform_crypto import build_platform_secret_cipher

    return PlatformOperationsService(
        settings_repository=build_platform_settings_repository(),
        run_repository=build_operation_run_repository(),
        cipher=build_platform_secret_cipher(),
    )


__all__ = ["PlatformOperationsService", "build_platform_operations_service"]
