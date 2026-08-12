from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models.platform_operations import OperationRun, PlatformOperationsSettings
from app.ops_scheduler import OpsScheduler


SHANGHAI = ZoneInfo("Asia/Shanghai")


class _Operations:
    def __init__(self, settings, *, created=True):
        self.settings = settings
        self.created = created
        self.calls = []
        self.claimed = []
        self.failed = []

    def get_runtime_settings(self):
        return self.settings

    def queue_operation(self, **kwargs):
        self.calls.append(kwargs)
        now = datetime.now(timezone.utc)
        return OperationRun(
            id="run-scheduled",
            operation_type="backup",
            status="queued",
            trigger_source="scheduled",
            idempotency_key=kwargs["idempotency_key"],
            created_at=now,
            updated_at=now,
        ), self.created

    def claim_run(self, run_id):
        self.claimed.append(run_id)
        now = datetime.now(timezone.utc)
        return OperationRun(
            id=run_id,
            operation_type="backup",
            status="running",
            trigger_source="scheduled",
            created_at=now,
            started_at=now,
            updated_at=now,
        )

    def fail_run(self, run_id, *, error_category, **values):
        self.failed.append((run_id, error_category, values))


def _scheduler(settings, *, created=True):
    operations = _Operations(settings, created=created)
    dispatched = []
    scheduler = OpsScheduler(
        operations=operations,
        dispatcher=lambda run_id: dispatched.append(run_id),
    )
    return scheduler, operations, dispatched


def test_disabled_schedule_does_nothing():
    scheduler, operations, dispatched = _scheduler(PlatformOperationsSettings())

    result = scheduler.tick(datetime(2026, 8, 12, 3, 5, tzinfo=SHANGHAI))

    assert result.state == "disabled"
    assert operations.calls == []
    assert dispatched == []


def test_before_due_time_does_not_create_run():
    scheduler, operations, _ = _scheduler(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00")
    )

    result = scheduler.tick(datetime(2026, 8, 12, 2, 59, tzinfo=SHANGHAI))

    assert result.state == "not_due"
    assert operations.calls == []


def test_due_time_queues_once_with_shanghai_schedule_date_and_dispatches():
    scheduler, operations, dispatched = _scheduler(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00")
    )

    result = scheduler.tick(datetime(2026, 8, 11, 19, 5, tzinfo=timezone.utc))

    assert result.state == "queued"
    assert operations.calls == [
        {
            "operation_type": "backup",
            "source": "scheduled",
            "idempotency_key": "scheduled-backup:2026-08-12",
        }
    ]
    assert dispatched == ["run-scheduled"]


def test_restart_duplicate_reads_existing_key_without_dispatching_again():
    scheduler, operations, dispatched = _scheduler(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00"),
        created=False,
    )

    result = scheduler.tick(datetime(2026, 8, 12, 8, 0, tzinfo=SHANGHAI))

    assert result.state == "already_queued"
    assert len(operations.calls) == 1
    assert dispatched == []


def test_next_day_uses_a_new_idempotency_key():
    scheduler, operations, dispatched = _scheduler(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00")
    )

    first = scheduler.tick(datetime(2026, 8, 12, 3, 0, tzinfo=SHANGHAI))
    second = scheduler.tick(datetime(2026, 8, 13, 3, 0, tzinfo=SHANGHAI))

    assert first.idempotency_key == "scheduled-backup:2026-08-12"
    assert second.idempotency_key == "scheduled-backup:2026-08-13"
    assert dispatched == ["run-scheduled", "run-scheduled"]


def test_naive_clock_is_rejected():
    scheduler, _, _ = _scheduler(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00")
    )

    try:
        scheduler.tick(datetime(2026, 8, 12, 3, 0))
    except ValueError as exc:
        assert str(exc) == "ops_scheduler_timezone_required"
    else:
        raise AssertionError("naive time must not be accepted")


def test_dispatch_failure_closes_run_with_stable_category():
    operations = _Operations(
        PlatformOperationsSettings(backup_enabled=True, backup_schedule="03:00")
    )
    scheduler = OpsScheduler(
        operations=operations,
        dispatcher=lambda run_id: (_ for _ in ()).throw(
            RuntimeError("private broker detail")
        ),
    )

    result = scheduler.tick(datetime(2026, 8, 12, 3, 0, tzinfo=SHANGHAI))

    assert result.state == "dispatch_failed"
    assert operations.claimed == ["run-scheduled"]
    assert operations.failed == [
        (
            "run-scheduled",
            "ops_queue_dispatch_failed",
            {"local_status": "skipped", "oss_status": "skipped"},
        )
    ]
    assert "private broker" not in repr(operations.failed)
