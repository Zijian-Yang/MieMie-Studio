"""Orchestrate low-privilege platform operations and safe status updates."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Callable

from app.services.backup_oss import BackupOSSError
from app.services.ops_webhook import OpsWebhookEvent
from app.services.postgres_backup import BackupExecutionError


class OpsRunner:
    def __init__(
        self,
        *,
        operations,
        backup_executor,
        oss_client,
        webhook_client,
        instance_id: str,
        release_commit: str,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._operations = operations
        self._backup = backup_executor
        self._oss = oss_client
        self._webhook = webhook_client
        self._instance_id = instance_id
        self._release_commit = release_commit
        self._clock = clock

    @staticmethod
    def _delivery_summary(result) -> dict:
        return {
            "delivered": result.delivered,
            "attempts": result.attempts,
            "failure_category": result.failure_category,
        }

    def _send_event(self, *, settings, run_id: str, severity: str, event_type: str, state: str, reason: str):
        event = OpsWebhookEvent(
            instance_id=self._instance_id,
            severity=severity,
            event_type=event_type,
            state=state,
            reason=reason,
            release_commit=self._release_commit,
            run_id=run_id,
            occurred_at=self._clock(),
        )
        return self._webhook.send(event, settings)

    def _safe_event_summary(self, **kwargs) -> dict:
        try:
            return self._delivery_summary(self._send_event(**kwargs))
        except Exception:
            return {
                "delivered": False,
                "attempts": 0,
                "failure_category": "webhook_internal_error",
            }

    def _settings_or_fail(self, run_id: str):
        try:
            return self._operations.get_runtime_settings()
        except Exception:
            self._operations.fail_run(
                run_id,
                error_category="platform_settings_unavailable",
                local_status="skipped",
                oss_status="skipped",
            )
            return None

    def run_backup(self, run_id: str):
        run = self._operations.claim_run(run_id)
        if run is None:
            return None
        settings = self._settings_or_fail(run_id)
        if settings is None:
            return None
        try:
            backup = self._backup.run(run_id, settings)
        except BackupExecutionError as exc:
            delivery = self._safe_event_summary(
                settings=settings,
                run_id=run_id,
                severity="critical",
                event_type="platform.backup",
                state="failed",
                reason=exc.category,
            )
            return self._operations.fail_run(
                run_id,
                error_category=exc.category,
                local_status="failed",
                oss_status="skipped",
                summary={"webhook": delivery},
            )
        except Exception:
            delivery = self._safe_event_summary(
                settings=settings,
                run_id=run_id,
                severity="critical",
                event_type="platform.backup",
                state="failed",
                reason="backup_internal_error",
            )
            return self._operations.fail_run(
                run_id,
                error_category="backup_internal_error",
                local_status="failed",
                oss_status="skipped",
                summary={"webhook": delivery},
            )

        base_values = {
            "local_status": "succeeded",
            "local_path_relative": backup.local_path_relative,
            "sha256": backup.sha256,
            "size_bytes": backup.size_bytes,
            "summary": {"pruned_count": len(backup.pruned_relative_paths)},
        }
        if not settings.backup_oss_enabled:
            return self._operations.complete_run(
                run_id,
                **base_values,
                oss_status="skipped",
            )

        try:
            key = self._oss.object_key(backup.local_path, settings)
            uploaded = self._oss.upload(backup.local_path, key, settings)
        except BackupOSSError as exc:
            delivery = self._safe_event_summary(
                settings=settings,
                run_id=run_id,
                severity="critical",
                event_type="platform.backup.oss",
                state="failed",
                reason=exc.category,
            )
            summary = {
                **base_values["summary"],
                "webhook": delivery,
            }
            return self._operations.fail_run(
                run_id,
                error_category=exc.category,
                **{**base_values, "summary": summary},
                oss_status="failed",
            )
        except Exception:
            delivery = self._safe_event_summary(
                settings=settings,
                run_id=run_id,
                severity="critical",
                event_type="platform.backup.oss",
                state="failed",
                reason="oss_internal_error",
            )
            summary = {**base_values["summary"], "webhook": delivery}
            return self._operations.fail_run(
                run_id,
                error_category="oss_internal_error",
                **{**base_values, "summary": summary},
                oss_status="failed",
            )

        return self._operations.complete_run(
            run_id,
            **base_values,
            oss_status="succeeded",
            oss_object_key=uploaded.object_key,
            oss_etag=uploaded.etag,
        )

    def run_oss_test(self, run_id: str):
        run = self._operations.claim_run(run_id)
        if run is None:
            return None
        settings = self._settings_or_fail(run_id)
        if settings is None:
            return None
        try:
            result = self._oss.test(settings)
        except BackupOSSError as exc:
            return self._operations.fail_run(
                run_id,
                error_category=exc.category,
                local_status="skipped",
                oss_status="failed",
            )
        except Exception:
            return self._operations.fail_run(
                run_id,
                error_category="oss_internal_error",
                local_status="skipped",
                oss_status="failed",
            )
        return self._operations.complete_run(
            run_id,
            local_status="skipped",
            oss_status="succeeded",
            oss_etag=result.etag,
            summary={"test_object_cleaned": True},
        )

    def run_webhook_test(self, run_id: str):
        run = self._operations.claim_run(run_id)
        if run is None:
            return None
        settings = self._settings_or_fail(run_id)
        if settings is None:
            return None
        try:
            result = self._send_event(
                settings=settings,
                run_id=run_id,
                severity="info",
                event_type="platform.webhook.test",
                state="succeeded",
                reason="manual_test",
            )
        except Exception:
            return self._operations.fail_run(
                run_id,
                error_category="webhook_internal_error",
                local_status="skipped",
                oss_status="skipped",
                summary={
                    "webhook": {
                        "delivered": False,
                        "attempts": 0,
                        "failure_category": "webhook_internal_error",
                    }
                },
            )
        values = {
            "local_status": "skipped",
            "oss_status": "skipped",
            "summary": {"webhook": self._delivery_summary(result)},
        }
        if result.delivered:
            return self._operations.complete_run(run_id, **values)
        return self._operations.fail_run(
            run_id,
            error_category=result.failure_category or "webhook_delivery_failed",
            **values,
        )


def build_ops_runner() -> OpsRunner:
    from app.services.backup_oss import BackupOSSClient
    from app.services.ops_webhook import OpsWebhookClient
    from app.services.platform_operations import build_platform_operations_service
    from app.services.postgres_backup import PostgresBackupExecutor

    return OpsRunner(
        operations=build_platform_operations_service(),
        backup_executor=PostgresBackupExecutor(),
        oss_client=BackupOSSClient(),
        webhook_client=OpsWebhookClient(),
        instance_id=os.getenv("MIEMIE_INSTANCE_ID", "miemie-studio"),
        release_commit=os.getenv("MIEMIE_RUNTIME_GIT_COMMIT", "unknown"),
    )


__all__ = ["OpsRunner", "build_ops_runner"]
