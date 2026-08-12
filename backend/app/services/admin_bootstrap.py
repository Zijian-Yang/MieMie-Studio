"""Explicit first-administrator bootstrap and registration policy."""

from __future__ import annotations

import os

from app.db.engine import TRUE_VALUES, database_enabled
from app.models.user import User
from app.repositories.platform_admin import (
    AdminAuditEvent,
    BootstrapAlreadyConfigured,
    ExistingUserRequiresPromotion,
)


class AdminAlreadyConfigured(RuntimeError):
    """Raised when a different administrator already owns the platform."""


class BootstrapUserNotFound(RuntimeError):
    """Raised when an explicit promotion/reset target does not exist."""


class AdminBootstrapService:
    def __init__(
        self,
        *,
        repository,
        password_hasher,
        user_data_initializer,
        session_revoker,
    ):
        self._repository = repository
        self._password_hasher = password_hasher
        self._user_data_initializer = user_data_initializer
        self._session_revoker = session_revoker

    def status(self) -> dict[str, bool]:
        status = self._repository.bootstrap_status()
        return {
            "admin_configured": status.active_admin_count > 0,
            "registration_enabled": status.registration_enabled,
        }

    def bootstrap(
        self,
        *,
        username: str,
        password: str,
        display_name: str | None = None,
        request_id: str = "host-cli-bootstrap",
    ) -> tuple[User, bool]:
        user = User(
            username=username.strip(),
            password=self._password_hasher(password),
            display_name=(display_name or username).strip(),
            role="admin",
            status="active",
            must_change_password=False,
        )
        event = AdminAuditEvent(
            actor_user_id=user.id,
            action="host.admin.bootstrap",
            target_type="user",
            target_id=user.id,
            request_id=request_id,
            changes={
                "username": user.username,
                "role": "admin",
                "source": "host_cli",
            },
        )
        try:
            stored, created = self._repository.bootstrap_admin(user, event)
        except BootstrapAlreadyConfigured as exc:
            raise AdminAlreadyConfigured("admin_already_configured") from exc
        if created:
            self._user_data_initializer(stored.id)
        return stored, created

    def promote(self, username: str) -> User:
        def event(target_id: str) -> AdminAuditEvent:
            return AdminAuditEvent(
                actor_user_id=target_id,
                action="host.admin.promote",
                target_type="user",
                target_id=target_id,
                request_id="host-cli-promote",
                changes={"role": "admin", "status": "active", "source": "host_cli"},
            )

        promoted = self._repository.promote_user(username.strip(), event)
        if promoted is None:
            raise BootstrapUserNotFound(username)
        self._session_revoker(promoted.id)
        return promoted

    def reset_password(self, username: str, password: str) -> User:
        def event(target_id: str) -> AdminAuditEvent:
            return AdminAuditEvent(
                actor_user_id=target_id,
                action="host.admin.reset_credential",
                target_type="user",
                target_id=target_id,
                request_id="host-cli-reset",
                changes={
                    "credential_reset": True,
                    "require_change": True,
                    "source": "host_cli",
                },
            )

        reset = self._repository.reset_admin_password(
            username.strip(),
            self._password_hasher(password),
            event,
        )
        if reset is None:
            raise BootstrapUserNotFound(username)
        self._session_revoker(reset.id)
        return reset


def build_admin_bootstrap_service() -> AdminBootstrapService:
    from app.repositories.user_config_runtime import build_admin_user_repository
    from app.services.user_service import get_user_service

    user_service = get_user_service()
    return AdminBootstrapService(
        repository=build_admin_user_repository(),
        password_hasher=user_service._hash_password,
        user_data_initializer=user_service.ensure_user_data_dir,
        session_revoker=user_service.revoke_user_sessions,
    )


def registration_enabled() -> bool:
    """Return the live registration policy, closed by default."""
    if database_enabled():
        from app.repositories.user_config_runtime import build_platform_settings_repository

        return build_platform_settings_repository().registration_enabled()
    return os.getenv("MIEMIE_REGISTRATION_ENABLED", "").strip().lower() in TRUE_VALUES


def bootstrap_status() -> dict[str, bool]:
    """Return the public, secret-free bootstrap status."""
    if database_enabled():
        return build_admin_bootstrap_service().status()

    from app.services.user_service import get_user_service

    user_service = get_user_service()
    users = [
        user_service.get_user_by_id(user_id)
        for user_id in user_service.list_user_ids()
    ]
    return {
        "admin_configured": any(
            user and user.role == "admin" and user.status == "active"
            for user in users
        ),
        "registration_enabled": registration_enabled(),
    }


__all__ = [
    "AdminAlreadyConfigured",
    "AdminBootstrapService",
    "BootstrapUserNotFound",
    "ExistingUserRequiresPromotion",
    "bootstrap_status",
    "build_admin_bootstrap_service",
    "registration_enabled",
]
