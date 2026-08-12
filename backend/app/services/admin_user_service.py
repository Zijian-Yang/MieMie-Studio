"""Administrator-facing platform user lifecycle rules."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.models.user import User
from app.repositories.platform_admin import (
    AdminAuditEvent,
    AdminUserNotFound,
    DuplicateUsername,
    LastActiveAdmin,
)


class AdminUserConflict(RuntimeError):
    """Raised when an administrator mutation violates a platform invariant."""


class AdminUserService:
    """Apply administrator user rules before transactional persistence."""

    def __init__(
        self,
        *,
        repository,
        password_hasher,
        session_revoker,
        user_data_initializer,
    ):
        self._repository = repository
        self._password_hasher = password_hasher
        self._session_revoker = session_revoker
        self._user_data_initializer = user_data_initializer

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        role: Literal["admin", "member"] | None = None,
        status: Literal["active", "disabled"] | None = None,
    ):
        return self._repository.list_users(
            page=page,
            page_size=page_size,
            query=query,
            role=role,
            status=status,
        )

    def create_user(
        self,
        *,
        actor: User,
        username: str,
        password: str,
        display_name: str | None = None,
        role: Literal["admin", "member"] = "member",
        must_change_password: bool = True,
        request_id: str | None = None,
    ) -> User:
        user = User(
            username=username.strip(),
            password=self._password_hasher(password),
            display_name=(display_name or username).strip(),
            role=role,
            status="active",
            must_change_password=must_change_password,
        )
        event = self._event(
            actor=actor,
            action="admin.user.create",
            target_id=user.id,
            request_id=request_id,
            changes={
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "status": user.status,
                "require_change": user.must_change_password,
            },
        )
        created = self._repository.create_user(user, event)
        self._user_data_initializer(created.id)
        return created

    def update_user(
        self,
        *,
        actor: User,
        user_id: str,
        username: str | None = None,
        display_name: str | None = None,
        role: Literal["admin", "member"] | None = None,
        status: Literal["active", "disabled"] | None = None,
        request_id: str | None = None,
    ) -> User:
        if actor.id == user_id and role is not None and role != "admin":
            raise AdminUserConflict("cannot_demote_self")
        if actor.id == user_id and status is not None and status != "active":
            raise AdminUserConflict("cannot_disable_self")

        changes = {}
        if username is not None:
            changes["username"] = username.strip()
        if display_name is not None:
            changes["display_name"] = display_name.strip()
        if role is not None:
            changes["role"] = role
        if status is not None:
            changes["status"] = status
        if not changes:
            raise AdminUserConflict("no_changes")

        event = self._event(
            actor=actor,
            action="admin.user.update",
            target_id=user_id,
            request_id=request_id,
            changes=changes,
        )
        try:
            updated = self._repository.update_user(user_id, changes, event)
        except LastActiveAdmin as exc:
            raise AdminUserConflict("last_active_admin") from exc
        if "role" in changes or "status" in changes:
            self._session_revoker(user_id)
        return updated

    def reset_password(
        self,
        *,
        actor: User,
        user_id: str,
        new_password: str,
        must_change_password: bool = True,
        request_id: str | None = None,
    ) -> User:
        event = self._event(
            actor=actor,
            action="admin.user.reset_credential",
            target_id=user_id,
            request_id=request_id,
            changes={"credential_reset": True, "require_change": must_change_password},
        )
        updated = self._repository.reset_password(
            user_id,
            self._password_hasher(new_password),
            must_change_password,
            event,
        )
        self._session_revoker(user_id)
        return updated

    def delete_user(
        self,
        *,
        actor: User,
        user_id: str,
        request_id: str | None = None,
    ) -> User:
        if actor.id == user_id:
            raise AdminUserConflict("cannot_delete_self")
        event = self._event(
            actor=actor,
            action="admin.user.delete",
            target_id=user_id,
            request_id=request_id,
            changes={"soft_delete": True, "business_data_preserved": True},
        )
        try:
            deleted = self._repository.soft_delete_user(user_id, event)
        except LastActiveAdmin as exc:
            raise AdminUserConflict("last_active_admin") from exc
        self._session_revoker(user_id)
        return deleted

    @staticmethod
    def _event(
        *,
        actor: User,
        action: str,
        target_id: str,
        request_id: str | None,
        changes: dict,
    ) -> AdminAuditEvent:
        return AdminAuditEvent(
            actor_user_id=actor.id,
            action=action,
            target_type="user",
            target_id=target_id,
            request_id=request_id,
            changes=changes,
        )


def build_admin_user_service() -> AdminUserService:
    """Build the production administrator service lazily from runtime dependencies."""

    from app.repositories.user_config_runtime import build_admin_user_repository
    from app.services.user_service import get_user_service

    user_service = get_user_service()
    return AdminUserService(
        repository=build_admin_user_repository(),
        password_hasher=user_service._hash_password,
        session_revoker=user_service.revoke_user_sessions,
        user_data_initializer=user_service.ensure_user_data_dir,
    )


__all__ = [
    "AdminUserConflict",
    "AdminUserNotFound",
    "AdminUserService",
    "DuplicateUsername",
    "build_admin_user_service",
]
