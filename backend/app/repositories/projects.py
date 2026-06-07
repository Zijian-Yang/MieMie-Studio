"""Project repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.projects import projects
from app.models.project import Project
from app.repositories.base import ProjectRepository, RepositoryWriteError
from app.services.storage import StorageService


logger = logging.getLogger(__name__)


def _json_snapshot(project: Project) -> dict[str, Any]:
    return project.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def project_to_row(user_id: str, project: Project) -> dict[str, Any]:
    """Convert the full Pydantic project into indexed PostgreSQL columns."""

    shot_count = len(project.script.shots) if project.script else 0
    return {
        "id": project.id,
        "user_id": user_id,
        "name": project.name,
        "description": project.description,
        "has_script": project.script is not None,
        "script_shot_count": shot_count,
        "character_count": len(project.character_ids or []),
        "scene_count": len(project.scene_ids or []),
        "prop_count": len(project.prop_ids or []),
        "style_count": len(project.style_ids or []),
        "llm_configs": {
            key: value.model_dump(mode="json")
            for key, value in (project.llm_configs or {}).items()
        },
        "raw_project_snapshot": _json_snapshot(project),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "deleted_at": None,
    }


def row_to_project(row: Mapping[str, Any]) -> Project:
    """Restore a project from a PostgreSQL row, preferring the full JSONB snapshot."""

    snapshot = row.get("raw_project_snapshot")
    if snapshot:
        return Project(**snapshot)

    return Project(
        id=row["id"],
        name=row["name"],
        description=_mapping_value(row, "description", ""),
        llm_configs=_mapping_value(row, "llm_configs", {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class FileProjectRepository:
    """Adapter around the current JSON StorageService project implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, project: Project) -> None:
        self._storage.save_project(project)

    def get(self, project_id: str) -> Optional[Project]:
        return self._storage.get_project(project_id)

    def list_all(self) -> list[Project]:
        return self._storage.list_projects()

    def delete(self, project_id: str) -> None:
        self._storage.delete_project(project_id)

    def mark_deleted(self, project_id: str) -> None:
        self.delete(project_id)


class PostgresProjectRepository:
    """PostgreSQL repository for one user namespace."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, project: Project) -> None:
        row = project_to_row(self._user_id, project)
        statement = insert(projects).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in projects.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[projects.c.id],
            set_=update_values,
        )

        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, project_id: str) -> Optional[Project]:
        statement = (
            select(projects)
            .where(projects.c.user_id == self._user_id)
            .where(projects.c.id == project_id)
            .where(projects.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_project(row) if row else None

    def list_all(self) -> list[Project]:
        statement = (
            select(projects)
            .where(projects.c.user_id == self._user_id)
            .where(projects.c.deleted_at.is_(None))
            .order_by(projects.c.updated_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_project(row) for row in rows]

    def delete(self, project_id: str) -> None:
        self.mark_deleted(project_id)

    def mark_deleted(self, project_id: str) -> None:
        statement = (
            update(projects)
            .where(projects.c.user_id == self._user_id)
            .where(projects.c.id == project_id)
            .where(projects.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class DualProjectRepository:
    """Write JSON first, then shadow PostgreSQL until read-switch gates pass."""

    def __init__(
        self,
        primary: ProjectRepository,
        shadow: ProjectRepository,
        *,
        strict_shadow_writes: bool = False,
    ):
        self._primary = primary
        self._shadow = shadow
        self._strict_shadow_writes = strict_shadow_writes

    def save(self, project: Project) -> None:
        self._primary.save(project)
        try:
            self._shadow.save(project)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "project_shadow_write_failed",
                extra={"project_id": project.id, "error": exc.__class__.__name__},
            )

    def get(self, project_id: str) -> Optional[Project]:
        return self._primary.get(project_id)

    def list_all(self) -> list[Project]:
        return self._primary.list_all()

    def delete(self, project_id: str) -> None:
        self.mark_deleted(project_id)

    def mark_deleted(self, project_id: str) -> None:
        self._primary.delete(project_id)
        try:
            self._shadow.mark_deleted(project_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "project_shadow_delete_failed",
                extra={"project_id": project_id, "error": exc.__class__.__name__},
            )
