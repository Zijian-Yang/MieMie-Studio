"""Minute-loop scheduler for one idempotent daily platform backup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import signal
import time
from typing import Callable
from zoneinfo import ZoneInfo


_SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class SchedulerTickResult:
    state: str
    idempotency_key: str | None = None
    run_id: str | None = None


class OpsScheduler:
    def __init__(self, *, operations, dispatcher: Callable[[str], object]):
        self._operations = operations
        self._dispatcher = dispatcher

    def tick(self, now: datetime) -> SchedulerTickResult:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("ops_scheduler_timezone_required")
        settings = self._operations.get_runtime_settings()
        if not settings.backup_enabled:
            return SchedulerTickResult(state="disabled")

        local = now.astimezone(_SHANGHAI)
        hour, minute = map(int, settings.backup_schedule.split(":"))
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if local < due:
            return SchedulerTickResult(state="not_due")

        idempotency_key = f"scheduled-backup:{local.date().isoformat()}"
        run, created = self._operations.queue_operation(
            operation_type="backup",
            source="scheduled",
            idempotency_key=idempotency_key,
        )
        if not created:
            return SchedulerTickResult(
                state="already_queued",
                idempotency_key=idempotency_key,
                run_id=run.id,
            )
        self._dispatcher(run.id)
        return SchedulerTickResult(
            state="queued",
            idempotency_key=idempotency_key,
            run_id=run.id,
        )


def _dispatch_backup(run_id: str):
    from app.worker_tasks import run_ops_backup

    return run_ops_backup.apply_async(args=(run_id,), queue="ops")


def run_scheduler_loop(
    *,
    scheduler: OpsScheduler | None = None,
    interval_seconds: int = 60,
) -> None:
    from app.services.platform_operations import build_platform_operations_service

    scheduler = scheduler or OpsScheduler(
        operations=build_platform_operations_service(),
        dispatcher=_dispatch_backup,
    )
    stopping = False

    def stop(*_args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        scheduler.tick(datetime.now(_SHANGHAI))
        for _ in range(max(1, interval_seconds)):
            if stopping:
                break
            time.sleep(1)


if __name__ == "__main__":
    run_scheduler_loop()


__all__ = ["OpsScheduler", "SchedulerTickResult", "run_scheduler_loop"]
