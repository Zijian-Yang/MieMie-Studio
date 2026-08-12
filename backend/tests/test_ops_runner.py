from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.models.platform_operations import OperationRun, PlatformOperationsSettings
from app.services.backup_oss import BackupOSSError, OSSOperationResult
from app.services.ops_runner import OpsRunner
from app.services.ops_webhook import WebhookDeliveryResult
from app.services.postgres_backup import BackupExecutionError, BackupResult


def _run(operation_type="backup"):
    now = datetime.now(timezone.utc)
    return OperationRun(
        id="run-1",
        operation_type=operation_type,
        status="running",
        trigger_source="manual",
        created_at=now,
        started_at=now,
        updated_at=now,
    )


class _Operations:
    def __init__(self, settings=None, run=None):
        self.settings = settings or PlatformOperationsSettings()
        self.run = run or _run()
        self.completed = []
        self.failed = []
        self.settings_error = None

    def claim_run(self, run_id):
        return self.run

    def get_runtime_settings(self):
        if self.settings_error:
            raise self.settings_error
        return self.settings

    def complete_run(self, run_id, **values):
        self.completed.append((run_id, values))
        return values

    def fail_run(self, run_id, *, error_category, **values):
        self.failed.append((run_id, error_category, values))
        return values


class _Backup:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def run(self, run_id, settings):
        self.calls.append((run_id, settings))
        if self.error:
            raise self.error
        return self.result


class _OSS:
    def __init__(self, *, upload_result=None, test_result=None, error=None):
        self.upload_result = upload_result
        self.test_result = test_result
        self.error = error
        self.calls = []

    def object_key(self, path, settings):
        return f"miemie/backups/{path.name}"

    def upload(self, path, key, settings):
        self.calls.append(("upload", path, key))
        if self.error:
            raise self.error
        return self.upload_result

    def test(self, settings):
        self.calls.append(("test",))
        if self.error:
            raise self.error
        return self.test_result


class _Webhook:
    def __init__(self, result=None):
        self.result = result or WebhookDeliveryResult(
            delivered=True, attempts=1, status_code=204
        )
        self.calls = []

    def send(self, event, settings):
        self.calls.append((event, settings))
        return self.result


def _backup_result(tmp_path):
    path = tmp_path / "miemie-postgres-test.dump"
    path.write_bytes(b"PGDMPbackup")
    return BackupResult(
        local_path=path,
        local_path_relative="postgres/miemie-postgres-test.dump",
        sha256="a" * 64,
        size_bytes=11,
        pruned_relative_paths=["postgres/old.dump"],
    )


def _runner(operations, backup, oss=None, webhook=None):
    return OpsRunner(
        operations=operations,
        backup_executor=backup,
        oss_client=oss or _OSS(),
        webhook_client=webhook or _Webhook(),
        instance_id="miemie-pre",
        release_commit="commit-1",
        clock=lambda: datetime(2026, 8, 12, 8, 30, tzinfo=timezone.utc),
    )


def test_successful_local_backup_without_oss_updates_separate_states(tmp_path):
    operations = _Operations(settings=PlatformOperationsSettings())
    runner = _runner(operations, _Backup(_backup_result(tmp_path)))

    runner.run_backup("run-1")

    assert operations.failed == []
    _, values = operations.completed[0]
    assert values["local_status"] == "succeeded"
    assert values["oss_status"] == "skipped"
    assert values["local_path_relative"].startswith("postgres/")
    assert values["sha256"] == "a" * 64
    assert values["summary"] == {"pruned_count": 1}


def test_successful_backup_uploads_to_oss_and_records_etag(tmp_path):
    settings = PlatformOperationsSettings(
        backup_oss_enabled=True,
        backup_oss_endpoint="https://oss-cn-test.aliyuncs.com",
        backup_oss_bucket_name="bucket",
        backup_oss_access_key_id="key",
        backup_oss_access_key_secret="secret",
    )
    operations = _Operations(settings=settings)
    oss = _OSS(
        upload_result=OSSOperationResult(
            succeeded=True,
            object_key="miemie/backups/backup.dump",
            etag="etag",
            size_bytes=11,
        )
    )

    _runner(operations, _Backup(_backup_result(tmp_path)), oss=oss).run_backup("run-1")

    _, values = operations.completed[0]
    assert values["local_status"] == "succeeded"
    assert values["oss_status"] == "succeeded"
    assert values["oss_object_key"] == "miemie/backups/backup.dump"
    assert values["oss_etag"] == "etag"


def test_oss_failure_preserves_local_success_fails_run_and_sends_alert(tmp_path):
    settings = PlatformOperationsSettings(
        backup_oss_enabled=True,
        backup_oss_endpoint="https://oss-cn-test.aliyuncs.com",
        backup_oss_bucket_name="bucket",
        backup_oss_access_key_id="key",
        backup_oss_access_key_secret="secret",
        webhook_enabled=True,
        webhook_url="https://hooks.example.test/private",
    )
    operations = _Operations(settings=settings)
    webhook = _Webhook()
    runner = _runner(
        operations,
        _Backup(_backup_result(tmp_path)),
        oss=_OSS(error=BackupOSSError("oss_upload_failed")),
        webhook=webhook,
    )

    runner.run_backup("run-1")

    _, category, values = operations.failed[0]
    assert category == "oss_upload_failed"
    assert values["local_status"] == "succeeded"
    assert values["oss_status"] == "failed"
    assert webhook.calls[0][0].reason == "oss_upload_failed"
    assert webhook.calls[0][0].severity == "critical"


def test_backup_failure_skips_oss_and_sends_secret_free_alert():
    settings = PlatformOperationsSettings(
        webhook_enabled=True,
        webhook_url="https://hooks.example.test/private",
    )
    operations = _Operations(settings=settings)
    webhook = _Webhook()
    runner = _runner(
        operations,
        _Backup(error=BackupExecutionError("pg_dump_failed")),
        webhook=webhook,
    )

    runner.run_backup("run-1")

    _, category, values = operations.failed[0]
    assert category == "pg_dump_failed"
    assert values["local_status"] == "failed"
    assert values["oss_status"] == "skipped"
    assert values["summary"]["webhook"]["delivered"] is True
    assert "hooks.example" not in repr(values)


def test_webhook_delivery_failure_is_recorded_without_private_target():
    settings = PlatformOperationsSettings(
        webhook_enabled=True,
        webhook_url="https://hooks.example.test/private",
    )
    operations = _Operations(settings=settings)
    webhook = _Webhook(
        WebhookDeliveryResult(
            delivered=False,
            attempts=2,
            failure_category="webhook_timeout",
        )
    )
    runner = _runner(
        operations,
        _Backup(error=BackupExecutionError("pg_dump_failed")),
        webhook=webhook,
    )

    runner.run_backup("run-1")

    summary = operations.failed[0][2]["summary"]
    assert summary["webhook"] == {
        "delivered": False,
        "attempts": 2,
        "failure_category": "webhook_timeout",
    }
    assert "hooks.example" not in repr(summary)


def test_unexpected_backup_exception_does_not_leave_run_running():
    operations = _Operations()
    runner = _runner(operations, _Backup(error=RuntimeError("private failure")))

    runner.run_backup("run-1")

    _, category, values = operations.failed[0]
    assert category == "backup_internal_error"
    assert values["local_status"] == "failed"
    assert "private failure" not in repr(values)


def test_oss_test_and_webhook_test_have_operation_specific_states():
    oss_operations = _Operations(run=_run("oss_test"), settings=PlatformOperationsSettings(
        backup_oss_enabled=True,
        backup_oss_endpoint="https://oss-cn-test.aliyuncs.com",
        backup_oss_bucket_name="bucket",
        backup_oss_access_key_id="key",
        backup_oss_access_key_secret="secret",
    ))
    oss = _OSS(test_result=OSSOperationResult(
        succeeded=True, object_key="miemie/backups/_checks/test.txt", etag="etag"
    ))
    _runner(oss_operations, _Backup(), oss=oss).run_oss_test("run-1")
    assert oss_operations.completed[0][1]["local_status"] == "skipped"
    assert oss_operations.completed[0][1]["oss_status"] == "succeeded"

    webhook_operations = _Operations(
        run=_run("webhook_test"),
        settings=PlatformOperationsSettings(
            webhook_enabled=True,
            webhook_url="https://hooks.example.test/private",
        ),
    )
    _runner(webhook_operations, _Backup()).run_webhook_test("run-1")
    values = webhook_operations.completed[0][1]
    assert values["local_status"] == "skipped"
    assert values["oss_status"] == "skipped"
    assert values["summary"]["webhook"]["delivered"] is True


def test_already_claimed_run_is_a_noop():
    operations = _Operations(run=None)
    operations.run = None
    backup = _Backup()

    result = _runner(operations, backup).run_backup("run-1")

    assert result is None
    assert backup.calls == []
    assert operations.completed == []


def test_settings_decryption_failure_does_not_leave_claimed_run_running():
    operations = _Operations()
    operations.settings_error = RuntimeError("private encryption detail")
    backup = _Backup()

    result = _runner(operations, backup).run_backup("run-1")

    assert result is None
    assert backup.calls == []
    assert operations.failed == [
        (
            "run-1",
            "platform_settings_unavailable",
            {"local_status": "skipped", "oss_status": "skipped"},
        )
    ]
    assert "private encryption" not in repr(operations.failed)
