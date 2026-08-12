"""PostgreSQL repositories for platform administrator governance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.schema.platform_admin import admin_audit_logs, operation_runs, platform_settings
from app.db.schema.user_config import users
from app.models.platform_operations import OperationRun, OperationRunPage
from app.models.user import User
from app.repositories.base import RepositoryWriteError
from app.repositories.user_config import row_to_user, user_to_row


class AdminRepositoryError(RuntimeError):
    """Base error for administrator repository operations."""


class AdminUserNotFound(AdminRepositoryError):
    """Raised when an active platform user does not exist."""


class DuplicateUsername(AdminRepositoryError):
    """Raised when an active username already exists."""


class LastActiveAdmin(AdminRepositoryError):
    """Raised when a mutation would remove the final active administrator."""


class BootstrapAlreadyConfigured(AdminRepositoryError):
    """Raised when bootstrap is attempted after another administrator exists."""


class ExistingUserRequiresPromotion(AdminRepositoryError):
    """Raised when bootstrap names an existing non-administrator account."""


@dataclass(frozen=True)
class AdminAuditEvent:
    actor_user_id: str
    action: str
    target_type: str
    target_id: str | None
    request_id: str | None
    changes: dict[str, Any]
    result: str = "success"


@dataclass(frozen=True)
class UserPage:
    items: list[User]
    total: int


@dataclass(frozen=True)
class AuditPage:
    items: list[dict[str, Any]]
    total: int


@dataclass(frozen=True)
class BootstrapStatus:
    active_admin_count: int
    registration_enabled: bool


def _audit_row(event: AdminAuditEvent, *, now: datetime) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "actor_user_id": event.actor_user_id,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "request_id": event.request_id,
        "result": event.result,
        "changes": event.changes,
        "created_at": now,
    }


def _active_user_clause():
    return users.c.deleted_at.is_(None)


def _lock_governance(conn) -> None:
    """Serialize administrator mutations on the singleton platform row."""
    conn.execute(
        select(platform_settings.c.id)
        .where(platform_settings.c.id == "platform")
        .with_for_update()
    ).scalar_one()


def _lock_target(conn, user_id: str):
    row = conn.execute(
        select(users).where(users.c.id == user_id, _active_user_clause()).with_for_update()
    ).mappings().first()
    if row is None:
        raise AdminUserNotFound(user_id)
    return row


def _guard_last_active_admin(conn, target, changes: dict[str, Any], *, deleting: bool = False) -> None:
    is_active_admin = target["role"] == "admin" and target["status"] == "active"
    stays_active_admin = (
        not deleting
        and changes.get("role", target["role"]) == "admin"
        and changes.get("status", target["status"]) == "active"
    )
    if not is_active_admin or stays_active_admin:
        return

    active_admin_ids = conn.execute(
        select(users.c.id)
        .where(
            users.c.role == "admin",
            users.c.status == "active",
            _active_user_clause(),
        )
        .with_for_update()
    ).scalars().all()
    if len(active_admin_ids) <= 1:
        raise LastActiveAdmin(target["id"])


class PostgresAdminUserRepository:
    """Transactional platform-user mutations with invariant checks and audit writes."""

    def __init__(self, engine):
        self._engine = engine

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        role: Literal["admin", "member"] | None = None,
        status: Literal["active", "disabled"] | None = None,
    ) -> UserPage:
        conditions = [_active_user_clause()]
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(
                or_(users.c.username.ilike(pattern), users.c.display_name.ilike(pattern))
            )
        if role:
            conditions.append(users.c.role == role)
        if status:
            conditions.append(users.c.status == status)

        base = and_(*conditions)
        offset = (page - 1) * page_size
        with self._engine.connect() as conn:
            total = int(conn.execute(select(func.count()).select_from(users).where(base)).scalar_one())
            rows = conn.execute(
                select(users)
                .where(base)
                .order_by(users.c.updated_at.desc(), users.c.username)
                .limit(page_size)
                .offset(offset)
            ).mappings().all()
        return UserPage(items=[row_to_user(row) for row in rows], total=total)

    def bootstrap_status(self) -> BootstrapStatus:
        with self._engine.connect() as conn:
            active_admin_count = int(
                conn.execute(
                    select(func.count())
                    .select_from(users)
                    .where(
                        users.c.role == "admin",
                        users.c.status == "active",
                        _active_user_clause(),
                    )
                ).scalar_one()
            )
            registration_enabled = bool(
                conn.execute(
                    select(platform_settings.c.registration_enabled).where(
                        platform_settings.c.id == "platform"
                    )
                ).scalar_one()
            )
        return BootstrapStatus(
            active_admin_count=active_admin_count,
            registration_enabled=registration_enabled,
        )

    def bootstrap_admin(
        self,
        user: User,
        event: AdminAuditEvent,
    ) -> tuple[User, bool]:
        now = datetime.now(timezone.utc)
        try:
            with self._engine.begin() as conn:
                _lock_governance(conn)
                active_admins = conn.execute(
                    select(users)
                    .where(
                        users.c.role == "admin",
                        users.c.status == "active",
                        _active_user_clause(),
                    )
                    .with_for_update()
                ).mappings().all()
                named_row = conn.execute(
                    select(users)
                    .where(users.c.username == user.username, _active_user_clause())
                    .with_for_update()
                ).mappings().first()
                if active_admins:
                    if (
                        named_row
                        and named_row["role"] == "admin"
                        and named_row["status"] == "active"
                    ):
                        return row_to_user(named_row), False
                    raise BootstrapAlreadyConfigured(user.username)
                if named_row:
                    raise ExistingUserRequiresPromotion(user.username)
                conn.execute(insert(users).values(**user_to_row(user)))
                conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        except IntegrityError as exc:
            raise DuplicateUsername(user.username) from exc
        except Exception as exc:
            if isinstance(exc, AdminRepositoryError):
                raise
            raise RepositoryWriteError(f"Failed to bootstrap administrator: {exc}") from exc
        return user, True

    def promote_user(self, username: str, event_factory) -> User | None:
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            _lock_governance(conn)
            row = conn.execute(
                select(users)
                .where(users.c.username == username, _active_user_clause())
                .with_for_update()
            ).mappings().first()
            if row is None:
                return None
            current = row_to_user(row)
            promoted = User(
                **{
                    **current.model_dump(),
                    "role": "admin",
                    "status": "active",
                    "updated_at": now.isoformat(),
                }
            )
            values = user_to_row(promoted)
            conn.execute(
                update(users)
                .where(users.c.id == promoted.id)
                .values(
                    role=promoted.role,
                    status=promoted.status,
                    raw_user_snapshot=values["raw_user_snapshot"],
                    updated_at=now,
                )
            )
            conn.execute(
                insert(admin_audit_logs).values(
                    **_audit_row(event_factory(promoted.id), now=now)
                )
            )
        return promoted

    def reset_admin_password(self, username: str, password_hash: str, event_factory) -> User | None:
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            _lock_governance(conn)
            row = conn.execute(
                select(users)
                .where(
                    users.c.username == username,
                    users.c.role == "admin",
                    _active_user_clause(),
                )
                .with_for_update()
            ).mappings().first()
            if row is None:
                return None
            current = row_to_user(row)
            reset = User(
                **{
                    **current.model_dump(),
                    "password": password_hash,
                    "must_change_password": True,
                    "updated_at": now.isoformat(),
                }
            )
            values = user_to_row(reset)
            conn.execute(
                update(users)
                .where(users.c.id == reset.id)
                .values(
                    password_hash=password_hash,
                    must_change_password=True,
                    raw_user_snapshot=values["raw_user_snapshot"],
                    updated_at=now,
                )
            )
            conn.execute(
                insert(admin_audit_logs).values(
                    **_audit_row(event_factory(reset.id), now=now)
                )
            )
        return reset

    def create_user(self, user: User, event: AdminAuditEvent) -> User:
        now = datetime.now(timezone.utc)
        try:
            with self._engine.begin() as conn:
                _lock_governance(conn)
                conn.execute(insert(users).values(**user_to_row(user)))
                conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        except IntegrityError as exc:
            if "username" in str(exc).lower() or "idx_users_username_active_unique" in str(exc):
                raise DuplicateUsername(user.username) from exc
            raise RepositoryWriteError(f"Failed to create administrator-managed user: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, AdminRepositoryError):
                raise
            raise RepositoryWriteError(f"Failed to create administrator-managed user: {exc}") from exc
        return user

    def update_user(self, user_id: str, changes: dict[str, Any], event: AdminAuditEvent) -> User:
        now = datetime.now(timezone.utc)
        try:
            with self._engine.begin() as conn:
                _lock_governance(conn)
                target = _lock_target(conn, user_id)
                _guard_last_active_admin(conn, target, changes)
                current = row_to_user(target)
                updated_user = User(
                    **{
                        **current.model_dump(),
                        **changes,
                        "updated_at": now.isoformat(),
                    }
                )
                row = user_to_row(updated_user)
                values = {
                    key: value
                    for key, value in row.items()
                    if key not in {"id", "created_at", "deleted_at"}
                }
                conn.execute(update(users).where(users.c.id == user_id).values(**values))
                conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        except IntegrityError as exc:
            if "username" in str(exc).lower() or "idx_users_username_active_unique" in str(exc):
                raise DuplicateUsername(str(changes.get("username", ""))) from exc
            raise RepositoryWriteError(f"Failed to update administrator-managed user: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, AdminRepositoryError):
                raise
            raise RepositoryWriteError(f"Failed to update administrator-managed user: {exc}") from exc
        return updated_user

    def reset_password(
        self,
        user_id: str,
        password_hash: str,
        must_change_password: bool,
        event: AdminAuditEvent,
    ) -> User:
        return self.update_user(
            user_id,
            {"password": password_hash, "must_change_password": must_change_password},
            event,
        )

    def soft_delete_user(self, user_id: str, event: AdminAuditEvent) -> User:
        now = datetime.now(timezone.utc)
        try:
            with self._engine.begin() as conn:
                _lock_governance(conn)
                target = _lock_target(conn, user_id)
                _guard_last_active_admin(conn, target, {}, deleting=True)
                deleted_user = row_to_user(target)
                conn.execute(
                    update(users)
                    .where(users.c.id == user_id)
                    .values(deleted_at=now, updated_at=now, status="disabled")
                )
                conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        except Exception as exc:
            if isinstance(exc, AdminRepositoryError):
                raise
            raise RepositoryWriteError(f"Failed to delete administrator-managed user: {exc}") from exc
        return deleted_user


class PlatformSettingsRepository:
    """Read and update the singleton platform settings row."""

    def __init__(self, engine):
        self._engine = engine

    def registration_enabled(self) -> bool:
        with self._engine.connect() as conn:
            value = conn.execute(
                select(platform_settings.c.registration_enabled).where(
                    platform_settings.c.id == "platform"
                )
            ).scalar_one()
        return bool(value)

    def set_registration_enabled(self, enabled: bool, event: AdminAuditEvent) -> bool:
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                update(platform_settings)
                .where(platform_settings.c.id == "platform")
                .values(
                    registration_enabled=enabled,
                    updated_at=now,
                    updated_by=event.actor_user_id,
                )
            )
            conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        return enabled

    def get_operations_row(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(platform_settings).where(platform_settings.c.id == "platform")
            ).mappings().one()
        return dict(row)

    def mutate_operations(self, mutator, event: AdminAuditEvent):
        """Apply a validated patch while holding the singleton settings row lock."""
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            row = conn.execute(
                select(platform_settings)
                .where(platform_settings.c.id == "platform")
                .with_for_update()
            ).mappings().one()
            values, result = mutator(dict(row))
            if values:
                conn.execute(
                    update(platform_settings)
                    .where(platform_settings.c.id == "platform")
                    .values(**values, updated_at=now, updated_by=event.actor_user_id)
                )
            conn.execute(insert(admin_audit_logs).values(**_audit_row(event, now=now)))
        return result


def _operation_row(run: OperationRun) -> dict[str, Any]:
    return run.model_dump()


def _row_to_operation(row) -> OperationRun:
    return OperationRun(**dict(row))


class OperationRunRepository:
    """Transactional state machine and idempotent creation for ops jobs."""

    def __init__(self, engine):
        self._engine = engine

    def create(self, run: OperationRun) -> tuple[OperationRun, bool]:
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(operation_runs).values(**_operation_row(run)))
            return run, True
        except IntegrityError as exc:
            if not run.idempotency_key:
                raise RepositoryWriteError("Failed to create operation run") from exc
            with self._engine.connect() as conn:
                row = conn.execute(
                    select(operation_runs).where(
                        operation_runs.c.idempotency_key == run.idempotency_key
                    )
                ).mappings().first()
            if row is None:
                raise RepositoryWriteError("Failed to create operation run") from exc
            return _row_to_operation(row), False

    def get(self, run_id: str) -> OperationRun | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(operation_runs).where(operation_runs.c.id == run_id)
            ).mappings().first()
        return _row_to_operation(row) if row else None

    def list(
        self,
        *,
        page: int,
        page_size: int,
        operation_type: str | None = None,
        status: str | None = None,
    ) -> OperationRunPage:
        conditions = []
        if operation_type:
            conditions.append(operation_runs.c.operation_type == operation_type)
        if status:
            conditions.append(operation_runs.c.status == status)
        count_query = select(func.count()).select_from(operation_runs)
        list_query = select(operation_runs)
        if conditions:
            clause = and_(*conditions)
            count_query = count_query.where(clause)
            list_query = list_query.where(clause)
        with self._engine.connect() as conn:
            total = int(conn.execute(count_query).scalar_one())
            rows = conn.execute(
                list_query.order_by(operation_runs.c.created_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            ).mappings().all()
        return OperationRunPage(items=[_row_to_operation(row) for row in rows], total=total)

    def claim(self, run_id: str) -> OperationRun | None:
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            row = conn.execute(
                update(operation_runs)
                .where(operation_runs.c.id == run_id, operation_runs.c.status == "queued")
                .values(status="running", started_at=now, updated_at=now)
                .returning(operation_runs)
            ).mappings().first()
        return _row_to_operation(row) if row else None

    def finish(self, run_id: str, *, succeeded: bool, values: dict[str, Any]) -> OperationRun:
        now = datetime.now(timezone.utc)
        safe_values = {
            key: value
            for key, value in values.items()
            if key
            in {
                "local_status",
                "oss_status",
                "local_path_relative",
                "oss_object_key",
                "oss_etag",
                "sha256",
                "size_bytes",
                "summary",
                "error_category",
                "artifact_relative_path",
            }
        }
        with self._engine.begin() as conn:
            row = conn.execute(
                update(operation_runs)
                .where(operation_runs.c.id == run_id, operation_runs.c.status == "running")
                .values(
                    **safe_values,
                    status="succeeded" if succeeded else "failed",
                    finished_at=now,
                    updated_at=now,
                )
                .returning(operation_runs)
            ).mappings().first()
        if row is None:
            raise RepositoryWriteError("Operation run is not running")
        return _row_to_operation(row)


class AdminAuditRepository:
    """Paginated read access for sanitized administrator audit events."""

    def __init__(self, engine):
        self._engine = engine

    def append(self, event: AdminAuditEvent) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(admin_audit_logs).values(
                    **_audit_row(event, now=datetime.now(timezone.utc))
                )
            )

    def list(self, *, page: int, page_size: int, action: str | None = None) -> AuditPage:
        condition = admin_audit_logs.c.action == action if action else None
        count_statement = select(func.count()).select_from(admin_audit_logs)
        list_statement = select(admin_audit_logs)
        if condition is not None:
            count_statement = count_statement.where(condition)
            list_statement = list_statement.where(condition)
        list_statement = (
            list_statement.order_by(admin_audit_logs.c.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        with self._engine.connect() as conn:
            total = int(conn.execute(count_statement).scalar_one())
            rows = conn.execute(list_statement).mappings().all()
        return AuditPage(items=[dict(row) for row in rows], total=total)
