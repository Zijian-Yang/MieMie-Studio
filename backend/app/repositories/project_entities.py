"""Repositories for project editing entities."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, TypeVar

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.project_entities import project_entities
from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import Video
from app.repositories.base import ProjectEntityRepository, RepositoryWriteError
from app.services.storage import StorageService


logger = logging.getLogger(__name__)

CHARACTER = "character"
SCENE = "scene"
PROP = "prop"
FRAME = "frame"
VIDEO = "video"
STYLE = "style"

EntityT = TypeVar("EntityT", Character, Scene, Prop, Frame, Video, Style)
ProjectEntity = Character | Scene | Prop | Frame | Video | Style

ENTITY_MODELS: dict[str, type[ProjectEntity]] = {
    CHARACTER: Character,
    SCENE: Scene,
    PROP: Prop,
    FRAME: Frame,
    VIDEO: Video,
    STYLE: Style,
}


def _json_snapshot(entity: ProjectEntity) -> dict[str, Any]:
    return entity.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def _entity_status(entity_kind: str, entity: ProjectEntity) -> str | None:
    if entity_kind != VIDEO or not isinstance(entity, Video) or not entity.task:
        return None
    status = entity.task.status
    return getattr(status, "value", status)


def entity_to_row(user_id: str, entity_kind: str, entity: ProjectEntity) -> dict[str, Any]:
    """Convert a Pydantic project entity into indexed PostgreSQL columns."""

    if entity_kind not in ENTITY_MODELS:
        raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    return {
        "id": entity.id,
        "entity_kind": entity_kind,
        "user_id": user_id,
        "project_id": entity.project_id,
        "name": getattr(entity, "name", None),
        "shot_id": getattr(entity, "shot_id", None),
        "shot_number": getattr(entity, "shot_number", None),
        "status": _entity_status(entity_kind, entity),
        "thumbnail_url": getattr(entity, "thumbnail_url", None) or getattr(entity, "selected_url", None),
        "selected_group_index": getattr(entity, "selected_group_index", 0),
        "raw_entity_snapshot": _json_snapshot(entity),
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
        "deleted_at": None,
    }


def row_to_entity(row: Mapping[str, Any]) -> ProjectEntity:
    """Restore a project entity from a PostgreSQL row, preferring the full JSONB snapshot."""

    entity_kind = row["entity_kind"]
    model = ENTITY_MODELS.get(entity_kind)
    if model is None:
        raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    snapshot = row.get("raw_entity_snapshot")
    if snapshot:
        return model(**snapshot)

    common = {
        "id": row["id"],
        "project_id": row["project_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if entity_kind in {CHARACTER, SCENE, PROP, STYLE}:
        return model(
            **common,
            name=_mapping_value(row, "name", ""),
        )
    if entity_kind == FRAME:
        return Frame(
            **common,
            shot_id=_mapping_value(row, "shot_id", ""),
            shot_number=_mapping_value(row, "shot_number", 0),
        )
    return Video(
        **common,
        shot_id=_mapping_value(row, "shot_id", ""),
        shot_number=_mapping_value(row, "shot_number", 0),
    )


class FileProjectEntityRepository:
    """Adapter around the current JSON StorageService entity implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, entity_kind: str, entity: ProjectEntity) -> None:
        if entity_kind == CHARACTER:
            self.save_character(entity)
        elif entity_kind == SCENE:
            self.save_scene(entity)
        elif entity_kind == PROP:
            self.save_prop(entity)
        elif entity_kind == FRAME:
            self.save_frame(entity)
        elif entity_kind == VIDEO:
            self.save_video(entity)
        elif entity_kind == STYLE:
            self.save_style(entity)
        else:
            raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    def get(self, entity_kind: str, entity_id: str) -> Optional[ProjectEntity]:
        if entity_kind == CHARACTER:
            return self.get_character(entity_id)
        if entity_kind == SCENE:
            return self.get_scene(entity_id)
        if entity_kind == PROP:
            return self.get_prop(entity_id)
        if entity_kind == FRAME:
            return self.get_frame(entity_id)
        if entity_kind == VIDEO:
            return self.get_video(entity_id)
        if entity_kind == STYLE:
            return self.get_style(entity_id)
        raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    def list_for_project(self, entity_kind: str, project_id: str) -> list[ProjectEntity]:
        if entity_kind == CHARACTER:
            return self.list_characters_for_project(project_id)
        if entity_kind == SCENE:
            return self.list_scenes_for_project(project_id)
        if entity_kind == PROP:
            return self.list_props_for_project(project_id)
        if entity_kind == FRAME:
            return self.list_frames_for_project(project_id)
        if entity_kind == VIDEO:
            return self.list_videos_for_project(project_id)
        if entity_kind == STYLE:
            return self.list_styles_for_project(project_id)
        raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    def delete(self, entity_kind: str, entity_id: str) -> None:
        if entity_kind == CHARACTER:
            self.delete_character(entity_id)
        elif entity_kind == SCENE:
            self.delete_scene(entity_id)
        elif entity_kind == PROP:
            self.delete_prop(entity_id)
        elif entity_kind == FRAME:
            self.delete_frame(entity_id)
        elif entity_kind == VIDEO:
            self.delete_video(entity_id)
        elif entity_kind == STYLE:
            self.delete_style(entity_id)
        else:
            raise ValueError(f"Unsupported project entity kind: {entity_kind}")

    def mark_deleted(self, entity_kind: str, entity_id: str) -> None:
        self.delete(entity_kind, entity_id)

    def _list_dir(
        self,
        directory,
        model: type[EntityT],
        project_id: str,
        sort_key: Callable[[EntityT], Any],
    ) -> list[EntityT]:
        items = []
        for file_path in directory.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                items.append(model(**data))
        return sorted(items, key=sort_key)

    def save_character(self, character: Character) -> None:
        self._storage.save_character(character)

    def get_character(self, character_id: str) -> Optional[Character]:
        return self._storage.get_character(character_id)

    def list_characters_for_project(self, project_id: str) -> list[Character]:
        return self._list_dir(self._storage.characters_dir, Character, project_id, lambda item: item.created_at)

    def delete_character(self, character_id: str) -> None:
        self._storage.delete_character(character_id)

    def save_scene(self, scene: Scene) -> None:
        self._storage.save_scene(scene)

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        return self._storage.get_scene(scene_id)

    def list_scenes_for_project(self, project_id: str) -> list[Scene]:
        return self._list_dir(self._storage.scenes_dir, Scene, project_id, lambda item: item.created_at)

    def delete_scene(self, scene_id: str) -> None:
        self._storage.delete_scene(scene_id)

    def save_prop(self, prop: Prop) -> None:
        self._storage.save_prop(prop)

    def get_prop(self, prop_id: str) -> Optional[Prop]:
        return self._storage.get_prop(prop_id)

    def list_props_for_project(self, project_id: str) -> list[Prop]:
        return self._list_dir(self._storage.props_dir, Prop, project_id, lambda item: item.created_at)

    def delete_prop(self, prop_id: str) -> None:
        self._storage.delete_prop(prop_id)

    def save_frame(self, frame: Frame) -> None:
        self._storage.save_frame(frame)

    def get_frame(self, frame_id: str) -> Optional[Frame]:
        return self._storage.get_frame(frame_id)

    def get_frame_by_shot(self, project_id: str, shot_id: str) -> Optional[Frame]:
        return self._storage.get_frame_by_shot(project_id, shot_id)

    def list_frames_for_project(self, project_id: str) -> list[Frame]:
        return self._storage.get_frames_by_project(project_id)

    def delete_frame(self, frame_id: str) -> None:
        self._storage.delete_frame(frame_id)

    def save_video(self, video: Video) -> None:
        self._storage.save_video(video)

    def get_video(self, video_id: str) -> Optional[Video]:
        return self._storage.get_video(video_id)

    def get_video_by_shot(self, project_id: str, shot_id: str) -> Optional[Video]:
        return self._storage.get_video_by_shot(project_id, shot_id)

    def get_video_by_task(self, task_id: str) -> Optional[Video]:
        return self._storage.get_video_by_task(task_id)

    def list_videos_for_project(self, project_id: str) -> list[Video]:
        return self._storage.get_videos_by_project(project_id)

    def delete_video(self, video_id: str) -> None:
        self._storage.delete_video(video_id)

    def save_style(self, style: Style) -> None:
        self._storage.save_style(style)

    def get_style(self, style_id: str) -> Optional[Style]:
        return self._storage.get_style(style_id)

    def list_styles_for_project(self, project_id: str) -> list[Style]:
        return self._list_dir(self._storage.styles_dir, Style, project_id, lambda item: item.created_at)

    def delete_style(self, style_id: str) -> None:
        self._storage.delete_style(style_id)


class PostgresProjectEntityRepository:
    """PostgreSQL repository for one user namespace of project editing entities."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, entity_kind: str, entity: ProjectEntity) -> None:
        row = entity_to_row(self._user_id, entity_kind, entity)
        statement = insert(project_entities).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in project_entities.c
            if column.name not in {"id", "entity_kind", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[project_entities.c.id, project_entities.c.entity_kind],
            set_=update_values,
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, entity_kind: str, entity_id: str) -> Optional[ProjectEntity]:
        statement = (
            select(project_entities)
            .where(project_entities.c.user_id == self._user_id)
            .where(project_entities.c.entity_kind == entity_kind)
            .where(project_entities.c.id == entity_id)
            .where(project_entities.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_entity(row) if row else None

    def list_for_project(self, entity_kind: str, project_id: str) -> list[ProjectEntity]:
        statement = (
            select(project_entities)
            .where(project_entities.c.user_id == self._user_id)
            .where(project_entities.c.entity_kind == entity_kind)
            .where(project_entities.c.project_id == project_id)
            .where(project_entities.c.deleted_at.is_(None))
        )
        if entity_kind in {FRAME, VIDEO}:
            statement = statement.order_by(project_entities.c.shot_number.asc(), project_entities.c.created_at.asc())
        else:
            statement = statement.order_by(project_entities.c.updated_at.desc())
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_entity(row) for row in rows]

    def delete(self, entity_kind: str, entity_id: str) -> None:
        self.mark_deleted(entity_kind, entity_id)

    def mark_deleted(self, entity_kind: str, entity_id: str) -> None:
        statement = (
            update(project_entities)
            .where(project_entities.c.user_id == self._user_id)
            .where(project_entities.c.entity_kind == entity_kind)
            .where(project_entities.c.id == entity_id)
            .where(project_entities.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class DualProjectEntityRepository:
    """Write JSON first, then shadow PostgreSQL until read-switch gates pass."""

    def __init__(
        self,
        primary: ProjectEntityRepository,
        shadow: ProjectEntityRepository,
        *,
        strict_shadow_writes: bool = False,
    ):
        self._primary = primary
        self._shadow = shadow
        self._strict_shadow_writes = strict_shadow_writes

    def save(self, entity_kind: str, entity: ProjectEntity) -> None:
        self._primary.save(entity_kind, entity)
        try:
            self._shadow.save(entity_kind, entity)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "project_entity_shadow_write_failed",
                extra={"entity_kind": entity_kind, "entity_id": entity.id, "error": exc.__class__.__name__},
            )

    def get(self, entity_kind: str, entity_id: str) -> Optional[ProjectEntity]:
        return self._primary.get(entity_kind, entity_id)

    def list_for_project(self, entity_kind: str, project_id: str) -> list[ProjectEntity]:
        return self._primary.list_for_project(entity_kind, project_id)

    def delete(self, entity_kind: str, entity_id: str) -> None:
        self.mark_deleted(entity_kind, entity_id)

    def mark_deleted(self, entity_kind: str, entity_id: str) -> None:
        self._primary.delete(entity_kind, entity_id)
        try:
            self._shadow.mark_deleted(entity_kind, entity_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "project_entity_shadow_delete_failed",
                extra={"entity_kind": entity_kind, "entity_id": entity_id, "error": exc.__class__.__name__},
            )
