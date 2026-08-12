"""Administrator-only platform settings and audit APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from slowapi.util import get_remote_address

from app.dependencies import require_admin
from app.models.admin import (
    AdminAuditPageResponse,
    PlatformSettingsResponse,
    PlatformSettingsUpdateRequest,
)
from app.models.user import User
from app.repositories.platform_admin import AdminAuditEvent
from app.repositories.user_config_runtime import (
    build_admin_audit_repository,
    build_platform_settings_repository,
)
from app.services.rate_limit import create_limiter


router = APIRouter()
limiter = create_limiter(key_func=get_remote_address, key_prefix="miemie-admin-platform")


@router.get("/platform-settings", response_model=PlatformSettingsResponse)
@limiter.limit("120/minute")
async def get_platform_settings(request: Request, actor: User = Depends(require_admin)):
    del request, actor
    enabled = build_platform_settings_repository().registration_enabled()
    return PlatformSettingsResponse(registration_enabled=enabled)


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
