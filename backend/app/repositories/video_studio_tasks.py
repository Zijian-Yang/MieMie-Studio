"""Video studio task repositories.

The current migration keeps JSON files as the primary source. This module adds
the boundary needed for PostgreSQL shadow writes, reconciliation, and later read
switches without changing router behavior yet.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.video_studio_tasks import video_studio_tasks
from app.models.media import VideoStudioTask
from app.repositories.base import (
    RepositoryMode,
    RepositoryWriteError,
    VideoStudioTaskRepository,
)
from app.services.storage import StorageService


logger = logging.getLogger(__name__)


def _json_snapshot(task: VideoStudioTask) -> dict[str, Any]:
    return task.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def video_studio_task_to_row(user_id: str, task: VideoStudioTask) -> dict[str, Any]:
    """Convert the full Pydantic task into indexed PostgreSQL columns."""

    return {
        "id": task.id,
        "user_id": user_id,
        "project_id": task.project_id,
        "task_kind": task.task_kind,
        "task_type": task.task_type,
        "provider": task.provider,
        "key_profile": task.key_profile,
        "model_id": task.model_id,
        "model": task.model,
        "name": task.name,
        "status": task.status,
        "submit_state": task.submit_state,
        "progress": int(getattr(task, "progress", 0) or 0),
        "group_count": task.group_count,
        "prompt": task.prompt,
        "negative_prompt": task.negative_prompt,
        "input_assets": task.input_assets or {},
        "normalized_params": task.normalized_params or {},
        "provider_payload_snapshot": task.provider_payload_snapshot,
        "provider_result_meta": task.provider_result_meta or {},
        "task_ids": task.task_ids or [],
        "request_ids": task.request_ids or [],
        "video_urls": task.video_urls or [],
        "selected_video_url": task.selected_video_url,
        "thumbnail_url": task.thumbnail_url,
        "error_message": task.error_message,
        "submit_attempt_id": task.submit_attempt_id,
        "submit_started_at": task.submit_started_at,
        "raw_task_snapshot": _json_snapshot(task),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "deleted_at": None,
    }


def row_to_video_studio_task(row: Mapping[str, Any]) -> VideoStudioTask:
    """Restore a task from a PostgreSQL row, preferring the full JSONB snapshot."""

    snapshot = row.get("raw_task_snapshot")
    if snapshot:
        return VideoStudioTask(**snapshot)

    return VideoStudioTask(
        id=row["id"],
        project_id=row["project_id"],
        task_kind=_mapping_value(row, "task_kind", "image_to_video"),
        task_type=_mapping_value(row, "task_type", "image_to_video"),
        provider=_mapping_value(row, "provider", "wan"),
        key_profile=row.get("key_profile"),
        model_id=row.get("model_id"),
        model=_mapping_value(row, "model", "wan2.5-i2v-preview"),
        name=_mapping_value(row, "name", ""),
        status=_mapping_value(row, "status", "pending"),
        submit_state=_mapping_value(row, "submit_state", "idle"),
        group_count=int(_mapping_value(row, "group_count", 1)),
        prompt=_mapping_value(row, "prompt", ""),
        negative_prompt=_mapping_value(row, "negative_prompt", ""),
        input_assets=_mapping_value(row, "input_assets", {}),
        normalized_params=_mapping_value(row, "normalized_params", {}),
        provider_payload_snapshot=row.get("provider_payload_snapshot"),
        provider_result_meta=_mapping_value(row, "provider_result_meta", {}),
        task_ids=_mapping_value(row, "task_ids", []),
        request_ids=_mapping_value(row, "request_ids", []),
        video_urls=_mapping_value(row, "video_urls", []),
        selected_video_url=row.get("selected_video_url"),
        thumbnail_url=row.get("thumbnail_url"),
        error_message=row.get("error_message"),
        submit_attempt_id=row.get("submit_attempt_id"),
        submit_started_at=row.get("submit_started_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class FileVideoStudioTaskRepository:
    """Adapter around the current JSON StorageService implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, task: VideoStudioTask) -> None:
        self._storage.save_video_studio_task(task)

    def get(self, task_id: str) -> Optional[VideoStudioTask]:
        return self._storage.get_video_studio_task(task_id)

    def list_for_project(self, project_id: str) -> list[VideoStudioTask]:
        return self._storage.get_video_studio_tasks(project_id)

    def list_all(self) -> list[VideoStudioTask]:
        return self._storage.get_all_video_studio_tasks()

    def delete(self, task_id: str) -> None:
        self._storage.delete_video_studio_task(task_id)

    def mark_deleted(self, task_id: str) -> None:
        self.delete(task_id)


class PostgresVideoStudioTaskRepository:
    """PostgreSQL repository for one user namespace."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, task: VideoStudioTask) -> None:
        row = video_studio_task_to_row(self._user_id, task)
        statement = insert(video_studio_tasks).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in video_studio_tasks.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[video_studio_tasks.c.id],
            set_=update_values,
        )

        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, task_id: str) -> Optional[VideoStudioTask]:
        statement = (
            select(video_studio_tasks)
            .where(video_studio_tasks.c.user_id == self._user_id)
            .where(video_studio_tasks.c.id == task_id)
            .where(video_studio_tasks.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_video_studio_task(row) if row else None

    def list_for_project(self, project_id: str) -> list[VideoStudioTask]:
        statement = (
            select(video_studio_tasks)
            .where(video_studio_tasks.c.user_id == self._user_id)
            .where(video_studio_tasks.c.project_id == project_id)
            .where(video_studio_tasks.c.deleted_at.is_(None))
            .order_by(video_studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_video_studio_task(row) for row in rows]

    def list_all(self) -> list[VideoStudioTask]:
        statement = (
            select(video_studio_tasks)
            .where(video_studio_tasks.c.user_id == self._user_id)
            .where(video_studio_tasks.c.deleted_at.is_(None))
            .order_by(video_studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_video_studio_task(row) for row in rows]

    def delete(self, task_id: str) -> None:
        self.mark_deleted(task_id)

    def mark_deleted(self, task_id: str) -> None:
        statement = (
            update(video_studio_tasks)
            .where(video_studio_tasks.c.user_id == self._user_id)
            .where(video_studio_tasks.c.id == task_id)
            .where(video_studio_tasks.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class DualVideoStudioTaskRepository:
    """Write JSON first, then shadow PostgreSQL until read-switch gates pass."""

    def __init__(
        self,
        primary: VideoStudioTaskRepository,
        shadow: VideoStudioTaskRepository,
        *,
        strict_shadow_writes: bool = False,
    ):
        self._primary = primary
        self._shadow = shadow
        self._strict_shadow_writes = strict_shadow_writes

    def save(self, task: VideoStudioTask) -> None:
        self._primary.save(task)
        try:
            self._shadow.save(task)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "video_studio_task_shadow_write_failed",
                extra={"task_id": task.id, "error": exc.__class__.__name__},
            )

    def get(self, task_id: str) -> Optional[VideoStudioTask]:
        return self._primary.get(task_id)

    def list_for_project(self, project_id: str) -> list[VideoStudioTask]:
        return self._primary.list_for_project(project_id)

    def list_all(self) -> list[VideoStudioTask]:
        return self._primary.list_all()

    def delete(self, task_id: str) -> None:
        self.mark_deleted(task_id)

    def mark_deleted(self, task_id: str) -> None:
        primary_mark_deleted = getattr(self._primary, "mark_deleted", self._primary.delete)
        primary_mark_deleted(task_id)
        try:
            shadow_mark_deleted = getattr(self._shadow, "mark_deleted", self._shadow.delete)
            shadow_mark_deleted(task_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "video_studio_task_shadow_delete_failed",
                extra={"task_id": task_id, "error": exc.__class__.__name__},
            )


__all__ = [
    "DualVideoStudioTaskRepository",
    "FileVideoStudioTaskRepository",
    "PostgresVideoStudioTaskRepository",
    "RepositoryMode",
    "RepositoryWriteError",
    "VideoStudioTaskRepository",
    "row_to_video_studio_task",
    "video_studio_task_to_row",
]
