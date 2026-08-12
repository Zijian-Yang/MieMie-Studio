"""Administrator-only platform user lifecycle API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi.util import get_remote_address

from app.dependencies import require_admin
from app.models.admin import (
    AdminPasswordResetRequest,
    AdminUserCreateRequest,
    AdminUserPageResponse,
    AdminUserUpdateRequest,
)
from app.models.user import User, UserResponse
from app.repositories.platform_admin import AdminUserNotFound, DuplicateUsername
from app.services.admin_user_service import AdminUserConflict, build_admin_user_service
from app.services.rate_limit import create_limiter


router = APIRouter()
limiter = create_limiter(key_func=get_remote_address, key_prefix="miemie-admin-users")


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        role=user.role,
        status=user.status,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


def _raise_admin_error(exc: Exception) -> None:
    if isinstance(exc, DuplicateUsername):
        status_code, code, message = 409, "duplicate_username", "用户名已存在"
    elif isinstance(exc, AdminUserNotFound):
        status_code, code, message = 404, "user_not_found", "用户不存在"
    elif isinstance(exc, AdminUserConflict):
        code = str(exc)
        messages = {
            "cannot_demote_self": "不能降低自己的管理员权限",
            "cannot_disable_self": "不能禁用自己的账户",
            "cannot_delete_self": "不能删除自己的账户",
            "last_active_admin": "平台必须保留至少一个启用的管理员",
            "no_changes": "没有可应用的修改",
        }
        status_code, message = 409, messages.get(code, "操作违反平台安全约束")
    else:
        raise exc
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.get("/users", response_model=AdminUserPageResponse)
@limiter.limit("120/minute")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: str | None = Query(default=None, max_length=128),
    role: str | None = Query(default=None, pattern="^(admin|member)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(active|disabled)$"),
    actor: User = Depends(require_admin),
):
    del actor
    result = build_admin_user_service().list_users(
        page=page,
        page_size=page_size,
        query=query,
        role=role,
        status=status_filter,
    )
    return AdminUserPageResponse(
        items=[_user_response(user) for user in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_user(
    request: Request,
    data: AdminUserCreateRequest,
    actor: User = Depends(require_admin),
):
    try:
        user = build_admin_user_service().create_user(
            actor=actor,
            request_id=getattr(request.state, "request_id", None),
            **data.model_dump(),
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return _user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
@limiter.limit("30/minute")
async def update_user(
    request: Request,
    user_id: str,
    data: AdminUserUpdateRequest,
    actor: User = Depends(require_admin),
):
    try:
        user = build_admin_user_service().update_user(
            actor=actor,
            user_id=user_id,
            request_id=getattr(request.state, "request_id", None),
            **data.model_dump(exclude_unset=True),
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return _user_response(user)


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
@limiter.limit("15/minute")
async def reset_password(
    request: Request,
    user_id: str,
    data: AdminPasswordResetRequest,
    actor: User = Depends(require_admin),
):
    try:
        user = build_admin_user_service().reset_password(
            actor=actor,
            user_id=user_id,
            new_password=data.new_password,
            must_change_password=data.must_change_password,
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return _user_response(user)


@router.delete("/users/{user_id}", response_model=UserResponse)
@limiter.limit("15/minute")
async def delete_user(
    request: Request,
    user_id: str,
    actor: User = Depends(require_admin),
):
    try:
        user = build_admin_user_service().delete_user(
            actor=actor,
            user_id=user_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return _user_response(user)
