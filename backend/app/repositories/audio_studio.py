"""Audio studio repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.audio_studio import audio_studio_tasks, voice_profiles
from app.models.audio_studio import AudioStudioTask, VoiceProfile
from app.repositories.base import AudioStudioRepository, RepositoryWriteError
from app.services.storage import StorageService


logger = logging.getLogger(__name__)


def _json_snapshot(item: AudioStudioTask | VoiceProfile) -> dict[str, Any]:
    return item.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def audio_studio_task_to_row(user_id: str, task: AudioStudioTask) -> dict[str, Any]:
    """Convert the full Pydantic audio task into indexed PostgreSQL columns."""

    return {
        "id": task.id,
        "user_id": user_id,
        "project_id": task.project_id,
        "task_type": task.task_type,
        "name": task.name,
        "status": task.status,
        "voice": task.voice,
        "format": task.format,
        "result_audio_url": task.result_audio_url,
        "result_voice_id": task.result_voice_id,
        "audio_duration": task.audio_duration,
        "saved_to_library": bool(task.saved_to_library),
        "request_id": task.request_id,
        "markers": task.markers or [],
        "error_message": task.error_message,
        "raw_task_snapshot": _json_snapshot(task),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "deleted_at": None,
    }


def row_to_audio_studio_task(row: Mapping[str, Any]) -> AudioStudioTask:
    """Restore an audio studio task from a PostgreSQL row."""

    snapshot = row.get("raw_task_snapshot")
    if snapshot:
        return AudioStudioTask(**snapshot)

    return AudioStudioTask(
        id=row["id"],
        project_id=row["project_id"],
        task_type=_mapping_value(row, "task_type", "tts"),
        name=_mapping_value(row, "name", ""),
        voice=_mapping_value(row, "voice", ""),
        format=_mapping_value(row, "format", "mp3_22050hz_mono_256kbps"),
        result_audio_url=row.get("result_audio_url"),
        result_voice_id=row.get("result_voice_id"),
        audio_duration=row.get("audio_duration"),
        saved_to_library=bool(_mapping_value(row, "saved_to_library", False)),
        markers=_mapping_value(row, "markers", []),
        status=_mapping_value(row, "status", "pending"),
        error_message=row.get("error_message"),
        request_id=row.get("request_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def voice_profile_to_row(user_id: str, profile: VoiceProfile) -> dict[str, Any]:
    """Convert a voice profile into indexed PostgreSQL columns."""

    return {
        "id": profile.id,
        "user_id": user_id,
        "project_id": profile.project_id,
        "voice_id": profile.voice_id,
        "name": profile.name,
        "source": profile.source,
        "target_model": profile.target_model,
        "prefix": profile.prefix,
        "status": profile.status,
        "preview_audio_url": profile.preview_audio_url,
        "audio_url": profile.audio_url,
        "raw_profile_snapshot": _json_snapshot(profile),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "deleted_at": None,
    }


def row_to_voice_profile(row: Mapping[str, Any]) -> VoiceProfile:
    """Restore a voice profile from a PostgreSQL row."""

    snapshot = row.get("raw_profile_snapshot")
    if snapshot:
        return VoiceProfile(**snapshot)

    return VoiceProfile(
        id=row["id"],
        project_id=row["project_id"],
        voice_id=row["voice_id"],
        name=_mapping_value(row, "name", ""),
        source=_mapping_value(row, "source", "clone"),
        target_model=_mapping_value(row, "target_model", "cosyvoice-v3-flash"),
        prefix=_mapping_value(row, "prefix", ""),
        status=_mapping_value(row, "status", "deploying"),
        preview_audio_url=row.get("preview_audio_url"),
        audio_url=row.get("audio_url"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class FileAudioStudioRepository:
    """Adapter around the current JSON StorageService audio studio implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save_task(self, task: AudioStudioTask) -> None:
        self._storage.save_audio_studio_task(task)

    def get_task(self, task_id: str) -> Optional[AudioStudioTask]:
        return self._storage.get_audio_studio_task(task_id)

    def list_tasks_for_project(self, project_id: str) -> list[AudioStudioTask]:
        return self._storage.get_audio_studio_tasks(project_id)

    def list_all_tasks(self) -> list[AudioStudioTask]:
        tasks = []
        for file_path in self._storage.audio_studio_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                tasks.append(AudioStudioTask(**data))
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    def delete_task(self, task_id: str) -> None:
        self._storage.delete_audio_studio_task(task_id)

    def mark_task_deleted(self, task_id: str) -> None:
        self.delete_task(task_id)

    def save_voice_profile(self, profile: VoiceProfile) -> None:
        self._storage.save_voice_profile(profile)

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        return self._storage.get_voice_profile(profile_id)

    def get_voice_profile_by_voice_id(self, voice_id: str) -> Optional[VoiceProfile]:
        return self._storage.get_voice_profile_by_voice_id(voice_id)

    def list_voice_profiles_for_project(self, project_id: str) -> list[VoiceProfile]:
        return self._storage.get_voice_profiles(project_id)

    def list_all_voice_profiles(self) -> list[VoiceProfile]:
        profiles = []
        for file_path in self._storage.voices_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                profiles.append(VoiceProfile(**data))
        return sorted(profiles, key=lambda profile: profile.created_at, reverse=True)

    def delete_voice_profile(self, profile_id: str) -> None:
        self._storage.delete_voice_profile(profile_id)

    def mark_voice_profile_deleted(self, profile_id: str) -> None:
        self.delete_voice_profile(profile_id)


class PostgresAudioStudioRepository:
    """PostgreSQL repository for one user namespace."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save_task(self, task: AudioStudioTask) -> None:
        row = audio_studio_task_to_row(self._user_id, task)
        statement = insert(audio_studio_tasks).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in audio_studio_tasks.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[audio_studio_tasks.c.id],
            set_=update_values,
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get_task(self, task_id: str) -> Optional[AudioStudioTask]:
        statement = (
            select(audio_studio_tasks)
            .where(audio_studio_tasks.c.user_id == self._user_id)
            .where(audio_studio_tasks.c.id == task_id)
            .where(audio_studio_tasks.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_audio_studio_task(row) if row else None

    def list_tasks_for_project(self, project_id: str) -> list[AudioStudioTask]:
        statement = (
            select(audio_studio_tasks)
            .where(audio_studio_tasks.c.user_id == self._user_id)
            .where(audio_studio_tasks.c.project_id == project_id)
            .where(audio_studio_tasks.c.deleted_at.is_(None))
            .order_by(audio_studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_audio_studio_task(row) for row in rows]

    def list_all_tasks(self) -> list[AudioStudioTask]:
        statement = (
            select(audio_studio_tasks)
            .where(audio_studio_tasks.c.user_id == self._user_id)
            .where(audio_studio_tasks.c.deleted_at.is_(None))
            .order_by(audio_studio_tasks.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_audio_studio_task(row) for row in rows]

    def delete_task(self, task_id: str) -> None:
        self.mark_task_deleted(task_id)

    def mark_task_deleted(self, task_id: str) -> None:
        statement = (
            update(audio_studio_tasks)
            .where(audio_studio_tasks.c.user_id == self._user_id)
            .where(audio_studio_tasks.c.id == task_id)
            .where(audio_studio_tasks.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def save_voice_profile(self, profile: VoiceProfile) -> None:
        row = voice_profile_to_row(self._user_id, profile)
        statement = insert(voice_profiles).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in voice_profiles.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[voice_profiles.c.id],
            set_=update_values,
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        statement = (
            select(voice_profiles)
            .where(voice_profiles.c.user_id == self._user_id)
            .where(voice_profiles.c.id == profile_id)
            .where(voice_profiles.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_voice_profile(row) if row else None

    def get_voice_profile_by_voice_id(self, voice_id: str) -> Optional[VoiceProfile]:
        statement = (
            select(voice_profiles)
            .where(voice_profiles.c.user_id == self._user_id)
            .where(voice_profiles.c.voice_id == voice_id)
            .where(voice_profiles.c.deleted_at.is_(None))
            .order_by(voice_profiles.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_voice_profile(row) if row else None

    def list_voice_profiles_for_project(self, project_id: str) -> list[VoiceProfile]:
        statement = (
            select(voice_profiles)
            .where(voice_profiles.c.user_id == self._user_id)
            .where(voice_profiles.c.project_id == project_id)
            .where(voice_profiles.c.deleted_at.is_(None))
            .order_by(voice_profiles.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_voice_profile(row) for row in rows]

    def list_all_voice_profiles(self) -> list[VoiceProfile]:
        statement = (
            select(voice_profiles)
            .where(voice_profiles.c.user_id == self._user_id)
            .where(voice_profiles.c.deleted_at.is_(None))
            .order_by(voice_profiles.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_voice_profile(row) for row in rows]

    def delete_voice_profile(self, profile_id: str) -> None:
        self.mark_voice_profile_deleted(profile_id)

    def mark_voice_profile_deleted(self, profile_id: str) -> None:
        statement = (
            update(voice_profiles)
            .where(voice_profiles.c.user_id == self._user_id)
            .where(voice_profiles.c.id == profile_id)
            .where(voice_profiles.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class DualAudioStudioRepository:
    """Write JSON first, then shadow PostgreSQL until read-switch gates pass."""

    def __init__(
        self,
        primary: AudioStudioRepository,
        shadow: AudioStudioRepository,
        *,
        strict_shadow_writes: bool = False,
    ):
        self._primary = primary
        self._shadow = shadow
        self._strict_shadow_writes = strict_shadow_writes

    def save_task(self, task: AudioStudioTask) -> None:
        self._primary.save_task(task)
        try:
            self._shadow.save_task(task)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "audio_studio_task_shadow_write_failed",
                extra={"task_id": task.id, "error": exc.__class__.__name__},
            )

    def get_task(self, task_id: str) -> Optional[AudioStudioTask]:
        return self._primary.get_task(task_id)

    def list_tasks_for_project(self, project_id: str) -> list[AudioStudioTask]:
        return self._primary.list_tasks_for_project(project_id)

    def list_all_tasks(self) -> list[AudioStudioTask]:
        return self._primary.list_all_tasks()

    def delete_task(self, task_id: str) -> None:
        self.mark_task_deleted(task_id)

    def mark_task_deleted(self, task_id: str) -> None:
        self._primary.delete_task(task_id)
        try:
            self._shadow.mark_task_deleted(task_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "audio_studio_task_shadow_delete_failed",
                extra={"task_id": task_id, "error": exc.__class__.__name__},
            )

    def save_voice_profile(self, profile: VoiceProfile) -> None:
        self._primary.save_voice_profile(profile)
        try:
            self._shadow.save_voice_profile(profile)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "voice_profile_shadow_write_failed",
                extra={"profile_id": profile.id, "error": exc.__class__.__name__},
            )

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        return self._primary.get_voice_profile(profile_id)

    def get_voice_profile_by_voice_id(self, voice_id: str) -> Optional[VoiceProfile]:
        return self._primary.get_voice_profile_by_voice_id(voice_id)

    def list_voice_profiles_for_project(self, project_id: str) -> list[VoiceProfile]:
        return self._primary.list_voice_profiles_for_project(project_id)

    def list_all_voice_profiles(self) -> list[VoiceProfile]:
        return self._primary.list_all_voice_profiles()

    def delete_voice_profile(self, profile_id: str) -> None:
        self.mark_voice_profile_deleted(profile_id)

    def mark_voice_profile_deleted(self, profile_id: str) -> None:
        self._primary.delete_voice_profile(profile_id)
        try:
            self._shadow.mark_voice_profile_deleted(profile_id)
        except Exception as exc:
            if self._strict_shadow_writes:
                if isinstance(exc, RepositoryWriteError):
                    raise
                raise RepositoryWriteError(str(exc)) from exc
            logger.warning(
                "voice_profile_shadow_delete_failed",
                extra={"profile_id": profile_id, "error": exc.__class__.__name__},
            )
