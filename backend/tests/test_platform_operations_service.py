from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.platform_operations import (
    OperationRun,
    OperationRunPage,
    PlatformOperationsSettingsPatch,
)
from app.models.user import User
from app.services.platform_crypto import PlatformSecretCipher, PlatformSecretError
from app.services.platform_operations import PlatformOperationsService


def _cipher(byte: int = 17) -> PlatformSecretCipher:
    key = base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")
    return PlatformSecretCipher(key)


def _settings_row(cipher: PlatformSecretCipher) -> dict:
    return {
        "backup_enabled": False,
        "backup_schedule": "03:00",
        "backup_retention_days": 30,
        "backup_min_keep": 7,
        "backup_local_subdirectory": "postgres",
        "backup_oss_enabled": True,
        "backup_oss_endpoint": "https://oss-cn-test.aliyuncs.com",
        "backup_oss_bucket_name": "platform-backups",
        "backup_oss_prefix": "miemie/backups",
        "backup_oss_access_key_id_encrypted": cipher.encrypt("LTAI-platform-key"),
        "backup_oss_access_key_secret_encrypted": cipher.encrypt("platform-secret"),
        "webhook_enabled": True,
        "webhook_url_encrypted": cipher.encrypt("https://hooks.example.test/secret"),
        "webhook_timeout_seconds": 10,
        "webhook_retry_count": 2,
        "webhook_alert_on_warning": False,
    }


class _SettingsRepository:
    def __init__(self, row):
        self.row = dict(row)
        self.events = []

    def get_operations_row(self):
        return dict(self.row)

    def mutate_operations(self, mutator, event):
        values, result = mutator(dict(self.row))
        self.row.update(values)
        self.events.append(event)
        return result


class _RunRepository:
    def __init__(self):
        self.created = []
        self.claimed = []
        self.finished = []

    def create(self, run):
        self.created.append(run)
        return run, True

    def claim(self, run_id):
        self.claimed.append(run_id)
        return None

    def finish(self, run_id, *, succeeded, values):
        self.finished.append((run_id, succeeded, values))
        now = datetime.now(timezone.utc)
        return OperationRun(
            id=run_id,
            operation_type="backup",
            status="succeeded" if succeeded else "failed",
            trigger_source="manual",
            local_status=values.get("local_status", "pending"),
            oss_status=values.get("oss_status", "pending"),
            error_category=values.get("error_category"),
            created_at=now,
            started_at=now,
            finished_at=now,
            updated_at=now,
        )

    def list(self, **kwargs):
        return OperationRunPage(items=[], total=0)


def _service(cipher=None):
    cipher = cipher or _cipher()
    settings = _SettingsRepository(_settings_row(cipher))
    runs = _RunRepository()
    return PlatformOperationsService(
        settings_repository=settings,
        run_repository=runs,
        cipher=cipher,
    ), settings, runs


def _admin():
    return User(
        id="admin-1",
        username="admin",
        password="stored-hash",
        role="admin",
    )


def test_masked_settings_never_return_plaintext_or_ciphertext():
    service, repository, _ = _service()

    result = service.get_settings().model_dump()
    serialized = repr(result)

    assert result["backup_oss_credentials_configured"] is True
    assert result["webhook_configured"] is True
    assert result["backup_oss_access_key_id_masked"].startswith("LTA")
    for forbidden in (
        "LTAI-platform-key",
        "platform-secret",
        "hooks.example.test/secret",
        repository.row["backup_oss_access_key_id_encrypted"],
    ):
        assert forbidden not in serialized


def test_plain_update_preserves_encrypted_secrets_and_sanitizes_audit():
    service, repository, _ = _service()
    encrypted_before = {
        key: repository.row[key]
        for key in (
            "backup_oss_access_key_id_encrypted",
            "backup_oss_access_key_secret_encrypted",
            "webhook_url_encrypted",
        )
    }

    result = service.update_settings(
        actor=_admin(),
        patch=PlatformOperationsSettingsPatch(
            backup_enabled=True,
            backup_schedule="04:25",
        ),
        request_id="req-1",
    )

    assert result.backup_enabled is True
    assert result.backup_schedule == "04:25"
    assert {key: repository.row[key] for key in encrypted_before} == encrypted_before
    assert repository.events[0].changes == {
        "backup_enabled": True,
        "backup_schedule": "04:25",
    }


def test_secret_replacement_is_encrypted_and_audit_only_records_flags():
    service, repository, _ = _service()

    service.update_settings(
        actor=_admin(),
        patch=PlatformOperationsSettingsPatch(
            backup_oss_access_key_id="LTAI-new-key",
            backup_oss_access_key_secret="new-secret",
            webhook_url="https://hooks.example.test/new-secret-path",
        ),
    )

    assert repository.row["backup_oss_access_key_id_encrypted"].startswith("v1.")
    assert repository.row["backup_oss_access_key_secret_encrypted"].startswith("v1.")
    assert repository.row["webhook_url_encrypted"].startswith("v1.")
    audit = repr(repository.events[0].changes)
    assert repository.events[0].changes == {
        "backup_oss_credentials_changed": True,
        "webhook_url_changed": True,
    }
    for forbidden in ("LTAI-new-key", "new-secret", "hooks.example"):
        assert forbidden not in audit


def test_clear_flags_require_dependent_features_to_be_disabled():
    service, repository, _ = _service()

    with pytest.raises(ValidationError, match="backup_oss_configuration_incomplete"):
        service.update_settings(
            actor=_admin(),
            patch=PlatformOperationsSettingsPatch(clear_backup_oss_credentials=True),
        )

    result = service.update_settings(
        actor=_admin(),
        patch=PlatformOperationsSettingsPatch(
            backup_oss_enabled=False,
            clear_backup_oss_credentials=True,
            webhook_enabled=False,
            clear_webhook_url=True,
        ),
    )

    assert result.backup_oss_credentials_configured is False
    assert result.webhook_configured is False
    assert repository.row["backup_oss_access_key_id_encrypted"] is None
    assert repository.row["backup_oss_access_key_secret_encrypted"] is None
    assert repository.row["webhook_url_encrypted"] is None
    assert repository.events[-1].changes["backup_oss_credentials_cleared"] is True
    assert repository.events[-1].changes["webhook_url_cleared"] is True


@pytest.mark.parametrize(
    "payload,error",
    (
        ({"backup_schedule": "3:00"}, "backup_schedule_invalid"),
        ({"backup_local_subdirectory": "../outside"}, "backup_local_subdirectory_invalid"),
        ({"backup_min_keep": 31}, "backup_min_keep_exceeds_retention"),
        ({"backup_oss_endpoint": "http://oss.example.test"}, "backup_oss_endpoint_invalid"),
        ({"backup_oss_prefix": "../escape"}, "backup_oss_prefix_invalid"),
        ({"webhook_url": "http://hooks.example.test"}, "webhook_url_invalid"),
        ({"webhook_url": None}, "platform_operations_null_not_allowed"),
    ),
)
def test_invalid_settings_are_rejected_without_writes(payload, error):
    service, repository, _ = _service()

    with pytest.raises(ValidationError, match=error):
        service.update_settings(
            actor=_admin(),
            patch=PlatformOperationsSettingsPatch(**payload),
        )

    assert repository.events == []


def test_wrong_encryption_key_uses_stable_secret_safe_error():
    service, _, _ = _service(cipher=_cipher(19))
    service._cipher = _cipher(20)

    with pytest.raises(PlatformSecretError) as exc:
        service.get_settings()

    assert str(exc.value) == "platform_secret_decryption_failed"


def test_operation_lifecycle_delegates_idempotency_and_failure_category():
    service, _, runs = _service()

    queued, created = service.queue_operation(
        operation_type="backup",
        source="scheduled",
        idempotency_key="scheduled-backup:2026-08-12",
    )
    assert created is True
    assert queued.status == "queued"
    assert runs.created[0].idempotency_key == "scheduled-backup:2026-08-12"

    assert service.claim_run(queued.id) is None
    failed = service.fail_run(
        queued.id,
        error_category="pg_dump_failed",
        local_status="failed",
        oss_status="skipped",
    )
    assert failed.status == "failed"
    assert runs.finished[-1][2]["error_category"] == "pg_dump_failed"
