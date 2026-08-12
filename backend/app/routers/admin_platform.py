"""Administrator-only platform settings and audit APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from slowapi.util import get_remote_address

from app.dependencies import require_admin
from app.models.admin import (
    AdminAuditPageResponse,
    OperationRunPageResponse,
    PlatformOperationsSettingsPatchRequest,
    PlatformOperationsSettingsResponse,
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
)
from app.models.user import User
from app.models.platform_operations import OperationRun
from app.repositories.platform_admin import AdminAuditEvent
from app.repositories.user_config_runtime import (
    build_admin_audit_repository,
    build_platform_settings_repository,
)
from app.services.rate_limit import create_limiter
from app.services.platform_operations import build_platform_operations_service
from app.services.platform_crypto import PlatformSecretError


router = APIRouter()
limiter = create_limiter(key_func=get_remote_address, key_prefix="miemie-admin-platform")


def dispatch_ops_operation(run):
    from app.worker_tasks import run_ops_backup, run_ops_oss_test, run_ops_webhook_test

    tasks = {
        "backup": run_ops_backup,
        "oss_test": run_ops_oss_test,
        "webhook_test": run_ops_webhook_test,
    }
    task = tasks.get(run.operation_type)
    if task is None:
        raise RuntimeError("unsupported_operation_type")
    return task.apply_async(args=(run.id,), queue="ops")


def _queue_operation(*, operation_type: str, actor: User):
    service = build_platform_operations_service()
    run, _ = service.queue_operation(
        operation_type=operation_type,
        source="manual",
        actor_id=actor.id,
    )
    try:
        dispatch_ops_operation(run)
    except Exception as exc:
        claimed = service.claim_run(run.id)
        if claimed is not None:
            service.fail_run(
                run.id,
                error_category="ops_queue_dispatch_failed",
                local_status="skipped",
                oss_status="skipped",
            )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ops_queue_unavailable",
                "message": "运维任务队列暂时不可用",
            },
        ) from exc
    return run


def _raise_settings_error(exc: Exception) -> None:
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "platform_settings_invalid",
                "message": "平台设置不完整或不合法",
            },
        ) from exc
    if isinstance(exc, PlatformSecretError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "platform_secret_unavailable",
                "message": "平台运维密钥不可用，请检查部署配置",
            },
        ) from exc
    raise exc


@router.get("/platform-settings", response_model=PlatformOperationsSettingsResponse)
@limiter.limit("120/minute")
async def get_platform_settings(request: Request, actor: User = Depends(require_admin)):
    del request, actor
    return build_platform_operations_service().get_settings()


@router.patch("/platform-settings", response_model=PlatformOperationsSettingsResponse)
@limiter.limit("30/minute")
async def patch_platform_settings(
    request: Request,
    data: PlatformOperationsSettingsPatchRequest,
    actor: User = Depends(require_admin),
):
    try:
        return build_platform_operations_service().update_settings(
            actor=actor,
            patch=data,
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception as exc:
        _raise_settings_error(exc)


@router.put("/platform-settings", response_model=PlatformSettingsResponse)
@limiter.limit("30/minute")
async def update_platform_settings(
    request: Request,
    data: PlatformSettingsUpdateRequest,
    actor: User = Depends(require_admin),
):
    event = AdminAuditEvent(
        actor_user_id=actor.id,
        action="admin.platform.registration.update",
        target_type="platform_settings",
        target_id="platform",
        request_id=getattr(request.state, "request_id", None),
        changes={"registration_enabled": data.registration_enabled},
    )
    enabled = build_platform_settings_repository().set_registration_enabled(
        data.registration_enabled,
        event,
    )
    return PlatformSettingsResponse(registration_enabled=enabled)


@router.post(
    "/backups",
    response_model=OperationRun,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def create_backup(request: Request, actor: User = Depends(require_admin)):
    del request
    return _queue_operation(operation_type="backup", actor=actor)


@router.post(
    "/backups/test-oss",
    response_model=OperationRun,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def test_backup_oss(request: Request, actor: User = Depends(require_admin)):
    del request
    return _queue_operation(operation_type="oss_test", actor=actor)


@router.post(
    "/alerts/test",
    response_model=OperationRun,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
async def test_alert_webhook(request: Request, actor: User = Depends(require_admin)):
    del request
    return _queue_operation(operation_type="webhook_test", actor=actor)


@router.get("/backups", response_model=OperationRunPageResponse)
@limiter.limit("120/minute")
async def list_operation_runs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    operation_type: str | None = Query(
        default=None,
        pattern="^(backup|oss_test|webhook_test|restore_rehearsal)$",
    ),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(queued|running|succeeded|failed)$",
    ),
    actor: User = Depends(require_admin),
):
    del request, actor
    result = build_platform_operations_service().list_runs(
        page=page,
        page_size=page_size,
        operation_type=operation_type,
        status=status_filter,
    )
    return OperationRunPageResponse(
        items=result.items,
        page=page,
        page_size=page_size,
        total=result.total,
    )


@router.get("/audit-logs", response_model=AdminAuditPageResponse)
@limiter.limit("120/minute")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(default=None, max_length=128),
    actor: User = Depends(require_admin),
):
    del request, actor
    result = build_admin_audit_repository().list(
        page=page,
        page_size=page_size,
        action=action,
    )
    return AdminAuditPageResponse(
        items=result.items,
        page=page,
        page_size=page_size,
        total=result.total,
    )
