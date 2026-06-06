"""Image studio task repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.studio_tasks import studio_tasks
from app.models.studio import StudioTask
from app.repositories.base import (
    RepositoryWriteError,
    StudioTaskRepository,
)
from app.services.storage import StorageService


logger = logging.getLogger(__name__)


def _json_snapshot(task: StudioTask) -> dict[str, Any]:
    return task.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def studio_task_to_row(user_id: str, task: StudioTask) -> dict[str, Any]:
    """Convert the full Pydantic task into indexed PostgreSQL columns."""

    images = task.images or []
    return {
        "id": task.id,
        "user_id": user_id,
        "project_id": task.project_id,
        "task_kind": task.task_kind,
        "provider": task.provider,
        "model_id": task.model_id,
        "model": task.model,
        "name": task.name,
        "status": task.status,
        "group_count": int(task.group_count or 0),
        "image_count": len(images),
        "selected_image_count": sum(1 for image in images if image.is_selected),
        "prompt": task.prompt,
        "negative_prompt": task.negative_prompt,
        "input_assets": task.input_assets or {},
        "normalized_params": task.normalized_params or {},
        "provider_payload_snapshot": task.provider_payload_snapshot,
        "provider_result_meta": task.provider_result_meta or {},
        "task_ids": task.task_ids or [],
        "request_ids": task.request_ids or [],
        "images": [image.model_dump(mode="json") for image in images],
        "warnings": task.warnings or [],
        "error_message": task.error_message,
        "last_task_id": task.last_task_id,
        "last_request_id": task.last_request_id,
        "raw_task_snapshot": _json_snapshot(task),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "deleted_at": None,
    }


def row_to_studio_task(row: Mapping[str, Any]) -> StudioTask:
    """Restore a task from a PostgreSQL row, preferring the full JSONB snapshot."""

    snapshot = row.get("raw_task_snapshot")
    if snapshot:
        return StudioTask(**snapshot)

    return StudioTask(
        id=row["id"],
        project_id=row["project_id"],
        task_kind=_mapping_value(row, "task_kind", "image_edit"),
        provider=_mapping_value(row, "provider", "wan"),
        model_id=row.get("model_id"),
        model=_mapping_value(row, "model", "wan2.5-i2i-preview"),
        name=_mapping_value(row, "name", ""),
        status=_mapping_value(row, "status", "pending"),
        group_count=int(_mapping_value(row, "group_count", 1)),
        prompt=_mapping_value(row, "prompt", ""),
        negative_prompt=_mapping_value(row, "negative_prompt", ""),
        input_assets=_mapping_value(row, "input_assets", {}),
        normalized_params=_mapping_value(row, "normalized_params", {}),
        provider_payload_snapshot=row.get("provider_payload_snapshot"),
        provider_result_meta=_mapping_value(row, "provider_result_meta", {}),
        task_ids=_mapping_value(row, "task_ids", []),
        request_ids=_mapping_value(row, "request_ids", []),
        images=_mapping_value(row, "images", []),
        warnings=_mapping_value(row, "warnings", []),
        error_message=row.get("error_message"),
        last_task_id=row.get("last_task_id"),
        last_request_id=row.get("last_request_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class FileStudioTaskRepository:
    """Adapter around the current JSON StorageService implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, task: StudioTask) -> None:
        self._storage.save_studio_task(task)

    def get(self, task_id: str) -> Optional[StudioTask]:
        return self._storage.get_studio_task(task_id)

    def list_for_project(self, project_id: str) -> list[StudioTask]:
        return self._storage.get_studio_tasks_by_project(project_id)

    def list_all(self) -> list[StudioTask]:
        tasks = []
        for file_path in self._storage.studio_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                tasks.append(StudioTask(**data))
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    def delete(self, task_id: str) -> None:
        self._storage.delete_studio_task(task_id)

    def mark_deleted(self, task_id: str) -> None:
        self.delete(task_id)


class PostgresStudioTaskRepository:
    """PostgreSQL repository for one user namespace."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, task: StudioTask) -> None:
        row = studio_task_to_row(self._user_id, task)
        statement = insert(studio_tasks).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in studio_tasks.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[studio_tasks.c.id],
            set_=update_values,
        )

        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, task_id: str) -> Optional[StudioTask]:
        statement = (
            select(studio_tasks)
            .where(studio_tasks.c.user_id == self._user_id)
            .where(studio_tasks.c.id == task_id)
            .where(studio_tasks.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_studio_task(row) if row else None

    def list_for_project(self, project_id: str) -> list[StudioTask]:
        statement = (
            select(studio_tasks)
            .where(studio_tasks.c.user_id == self._user_id)
            .where(studio_tasks.c.project_id == project_id)
            .where(studio_tasks.c.deleted_at.is_(None))
            .order_by(studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_studio_task(row) for row in rows]

    def list_all(self) -> list[StudioTask]:
        statement = (
            select(studio_tasks)
            .where(studio_tasks.c.user_id == self._user_id)
            .where(studio_tasks.c.deleted_at.is_(None))
            .order_by(studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_studio_task(row) for row in rows]

    def delete(self, task_id: str) -> None:
        self.mark_deleted(task_id)

    def mark_deleted(self, task_id: str) -> None:
        statement = (
            update(studio_tasks)
            .where(studio_tasks.c.user_id == self._user_id)
            .where(studio_tasks.c.id == task_id)
            .where(studio_tasks.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class DualStudioTaskRepository:
    """Write JSON first, then shadow PostgreSQL until read-switch gates pass."""

    def __init__(
        self,
        primary: StudioTaskRepository,
        shadow: StudioTaskRepository,
        *,
        strict_shadow_writes: bool = False,
    ):
        self._primary = primary
        self._shadow = shadow
        self._strict_shadow_writes = strict_shadow_writes

    def save(self, task: StudioTask) -> None:
        self._primary.save(task)
        try:
            self._shadow.save(task)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "studio_task_shadow_write_failed",
                extra={"task_id": task.id, "error": exc.__class__.__name__},
            )

    def get(self, task_id: str) -> Optional[StudioTask]:
        return self._primary.get(task_id)

    def list_for_project(self, project_id: str) -> list[StudioTask]:
        return self._primary.list_for_project(project_id)

    def list_all(self) -> list[StudioTask]:
        return self._primary.list_all()

    def delete(self, task_id: str) -> None:
        self.mark_deleted(task_id)

    def mark_deleted(self, task_id: str) -> None:
        self._primary.delete(task_id)
        try:
            self._shadow.mark_deleted(task_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "studio_task_shadow_delete_failed",
                extra={"task_id": task_id, "error": exc.__class__.__name__},
            )
