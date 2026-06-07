"""Media library repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, Optional, TypeVar

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.schema.media_assets import media_assets, text_items
from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.repositories.base import RepositoryWriteError
from app.services.storage import StorageService


AssetT = TypeVar("AssetT", GalleryImage, AudioItem, VideoItem)

GALLERY_IMAGE = "gallery_image"
AUDIO = "audio"
VIDEO = "video"


def _json_snapshot(item: Any) -> dict[str, Any]:
    return item.model_dump(mode="json")


def _mapping_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = row.get(key, default)
    return default if value is None else value


def _base_media_row(user_id: str, item: GalleryImage | AudioItem | VideoItem, asset_kind: str) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": user_id,
        "project_id": item.project_id,
        "asset_kind": asset_kind,
        "name": item.name,
        "description": item.description,
        "url": item.url,
        "file_type": getattr(item, "file_type", ""),
        "file_size": getattr(item, "file_size", 0),
        "duration": getattr(item, "duration", None),
        "width": getattr(item, "width", None),
        "height": getattr(item, "height", None),
        "fps": getattr(item, "fps", None),
        "thumbnail_url": getattr(item, "thumbnail_url", None),
        "sample_rate": getattr(item, "sample_rate", None),
        "channels": getattr(item, "channels", None),
        "source": getattr(item, "source", None),
        "task_id": getattr(item, "task_id", None),
        "tags": getattr(item, "tags", []),
        "prompt_used": getattr(item, "prompt_used", None),
        "raw_media_snapshot": _json_snapshot(item),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": None,
    }


def gallery_image_to_media_row(user_id: str, image: GalleryImage) -> dict[str, Any]:
    return _base_media_row(user_id, image, GALLERY_IMAGE)


def audio_item_to_media_row(user_id: str, audio: AudioItem) -> dict[str, Any]:
    return _base_media_row(user_id, audio, AUDIO)


def video_item_to_media_row(user_id: str, video: VideoItem) -> dict[str, Any]:
    return _base_media_row(user_id, video, VIDEO)


def row_to_gallery_image(row: Mapping[str, Any]) -> GalleryImage:
    snapshot = row.get("raw_media_snapshot")
    if snapshot:
        return GalleryImage(**snapshot)

    return GalleryImage(
        id=row["id"],
        project_id=row["project_id"],
        name=_mapping_value(row, "name", ""),
        description=_mapping_value(row, "description", ""),
        url=row["url"],
        prompt_used=row.get("prompt_used"),
        source=_mapping_value(row, "source", "upload"),
        task_id=row.get("task_id"),
        tags=_mapping_value(row, "tags", []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_audio_item(row: Mapping[str, Any]) -> AudioItem:
    snapshot = row.get("raw_media_snapshot")
    if snapshot:
        return AudioItem(**snapshot)

    return AudioItem(
        id=row["id"],
        project_id=row["project_id"],
        name=_mapping_value(row, "name", ""),
        description=_mapping_value(row, "description", ""),
        url=row["url"],
        file_type=_mapping_value(row, "file_type", ""),
        file_size=_mapping_value(row, "file_size", 0),
        duration=row.get("duration"),
        sample_rate=row.get("sample_rate"),
        channels=row.get("channels"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_video_item(row: Mapping[str, Any]) -> VideoItem:
    snapshot = row.get("raw_media_snapshot")
    if snapshot:
        return VideoItem(**snapshot)

    return VideoItem(
        id=row["id"],
        project_id=row["project_id"],
        name=_mapping_value(row, "name", ""),
        description=_mapping_value(row, "description", ""),
        url=row["url"],
        file_type=_mapping_value(row, "file_type", ""),
        file_size=_mapping_value(row, "file_size", 0),
        duration=row.get("duration"),
        width=row.get("width"),
        height=row.get("height"),
        fps=row.get("fps"),
        thumbnail_url=row.get("thumbnail_url"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def text_item_to_row(user_id: str, item: TextItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "user_id": user_id,
        "project_id": item.project_id,
        "name": item.name,
        "category": item.category,
        "content": item.content,
        "version_count": len(item.versions or []),
        "raw_text_snapshot": _json_snapshot(item),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": None,
    }


def row_to_text_item(row: Mapping[str, Any]) -> TextItem:
    snapshot = row.get("raw_text_snapshot")
    if snapshot:
        return TextItem(**snapshot)

    return TextItem(
        id=row["id"],
        project_id=row["project_id"],
        name=_mapping_value(row, "name", ""),
        content=row["content"],
        category=_mapping_value(row, "category", ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class FileMediaAssetRepository:
    """Adapter around the current JSON StorageService media library implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save_gallery_image(self, image: GalleryImage) -> None:
        self._storage.save_gallery_image(image)

    def get_gallery_image(self, image_id: str) -> Optional[GalleryImage]:
        return self._storage.get_gallery_image(image_id)

    def list_gallery_images_for_project(self, project_id: str) -> list[GalleryImage]:
        return self._storage.get_gallery_images_by_project(project_id)

    def list_all_gallery_images(self) -> list[GalleryImage]:
        images = []
        for file_path in self._storage.gallery_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                images.append(GalleryImage(**data))
        return sorted(images, key=lambda image: image.created_at, reverse=True)

    def delete_gallery_image(self, image_id: str) -> None:
        self._storage.delete_gallery_image(image_id)

    def save_audio_item(self, audio: AudioItem) -> None:
        self._storage.save_audio_item(audio)

    def get_audio_item(self, audio_id: str) -> Optional[AudioItem]:
        return self._storage.get_audio_item(audio_id)

    def list_audio_items_for_project(self, project_id: str) -> list[AudioItem]:
        return self._storage.get_audio_items(project_id)

    def list_all_audio_items(self) -> list[AudioItem]:
        audios = []
        for file_path in self._storage.audio_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                audios.append(AudioItem(**data))
        return sorted(audios, key=lambda audio: audio.created_at, reverse=True)

    def delete_audio_item(self, audio_id: str) -> None:
        self._storage.delete_audio_item(audio_id)

    def save_video_item(self, video: VideoItem) -> None:
        self._storage.save_video_item(video)

    def get_video_item(self, video_id: str) -> Optional[VideoItem]:
        return self._storage.get_video_item(video_id)

    def list_video_items_for_project(self, project_id: str) -> list[VideoItem]:
        return self._storage.get_video_items(project_id)

    def list_all_video_items(self) -> list[VideoItem]:
        videos = []
        for file_path in self._storage.video_library_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                videos.append(VideoItem(**data))
        return sorted(videos, key=lambda video: video.created_at, reverse=True)

    def delete_video_item(self, video_id: str) -> None:
        self._storage.delete_video_item(video_id)

    def mark_deleted(self, asset_id: str) -> None:
        if self.get_gallery_image(asset_id):
            self.delete_gallery_image(asset_id)
        elif self.get_audio_item(asset_id):
            self.delete_audio_item(asset_id)
        else:
            self.delete_video_item(asset_id)


class FileTextItemRepository:
    """Adapter around the current JSON StorageService text library implementation."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save(self, item: TextItem) -> None:
        self._storage.save_text_item(item)

    def get(self, item_id: str) -> Optional[TextItem]:
        return self._storage.get_text_item(item_id)

    def list_for_project(self, project_id: str) -> list[TextItem]:
        return self._storage.get_text_items(project_id)

    def list_all(self) -> list[TextItem]:
        texts = []
        for file_path in self._storage.text_library_dir.glob("*.json"):
            data = self._storage._read_json_with_lock(file_path)
            if data:
                texts.append(TextItem(**data))
        return sorted(texts, key=lambda text: text.created_at, reverse=True)

    def delete(self, item_id: str) -> None:
        self._storage.delete_text_item(item_id)

    def mark_deleted(self, item_id: str) -> None:
        self.delete(item_id)


class PostgresMediaAssetRepository:
    """PostgreSQL repository for gallery, audio, and video metadata."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def _save_row(self, row: dict[str, Any]) -> None:
        statement = insert(media_assets).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in media_assets.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[media_assets.c.id],
            set_=update_values,
        )

        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def _get(self, asset_id: str, asset_kind: str, restore: Callable[[Mapping[str, Any]], AssetT]) -> AssetT | None:
        statement = (
            select(media_assets)
            .where(media_assets.c.user_id == self._user_id)
            .where(media_assets.c.asset_kind == asset_kind)
            .where(media_assets.c.id == asset_id)
            .where(media_assets.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return restore(row) if row else None

    def _list_for_project(
        self,
        project_id: str,
        asset_kind: str,
        restore: Callable[[Mapping[str, Any]], AssetT],
    ) -> list[AssetT]:
        statement = (
            select(media_assets)
            .where(media_assets.c.user_id == self._user_id)
            .where(media_assets.c.project_id == project_id)
            .where(media_assets.c.asset_kind == asset_kind)
            .where(media_assets.c.deleted_at.is_(None))
            .order_by(media_assets.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [restore(row) for row in rows]

    def _list_all(
        self,
        asset_kind: str,
        restore: Callable[[Mapping[str, Any]], AssetT],
    ) -> list[AssetT]:
        statement = (
            select(media_assets)
            .where(media_assets.c.user_id == self._user_id)
            .where(media_assets.c.asset_kind == asset_kind)
            .where(media_assets.c.deleted_at.is_(None))
            .order_by(media_assets.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [restore(row) for row in rows]

    def save_gallery_image(self, image: GalleryImage) -> None:
        self._save_row(gallery_image_to_media_row(self._user_id, image))

    def get_gallery_image(self, image_id: str) -> Optional[GalleryImage]:
        return self._get(image_id, GALLERY_IMAGE, row_to_gallery_image)

    def list_gallery_images_for_project(self, project_id: str) -> list[GalleryImage]:
        return self._list_for_project(project_id, GALLERY_IMAGE, row_to_gallery_image)

    def list_all_gallery_images(self) -> list[GalleryImage]:
        return self._list_all(GALLERY_IMAGE, row_to_gallery_image)

    def delete_gallery_image(self, image_id: str) -> None:
        self.mark_deleted(image_id)

    def save_audio_item(self, audio: AudioItem) -> None:
        self._save_row(audio_item_to_media_row(self._user_id, audio))

    def get_audio_item(self, audio_id: str) -> Optional[AudioItem]:
        return self._get(audio_id, AUDIO, row_to_audio_item)

    def list_audio_items_for_project(self, project_id: str) -> list[AudioItem]:
        return self._list_for_project(project_id, AUDIO, row_to_audio_item)

    def list_all_audio_items(self) -> list[AudioItem]:
        return self._list_all(AUDIO, row_to_audio_item)

    def delete_audio_item(self, audio_id: str) -> None:
        self.mark_deleted(audio_id)

    def save_video_item(self, video: VideoItem) -> None:
        self._save_row(video_item_to_media_row(self._user_id, video))

    def get_video_item(self, video_id: str) -> Optional[VideoItem]:
        return self._get(video_id, VIDEO, row_to_video_item)

    def list_video_items_for_project(self, project_id: str) -> list[VideoItem]:
        return self._list_for_project(project_id, VIDEO, row_to_video_item)

    def list_all_video_items(self) -> list[VideoItem]:
        return self._list_all(VIDEO, row_to_video_item)

    def delete_video_item(self, video_id: str) -> None:
        self.mark_deleted(video_id)

    def mark_deleted(self, asset_id: str) -> None:
        statement = (
            update(media_assets)
            .where(media_assets.c.user_id == self._user_id)
            .where(media_assets.c.id == asset_id)
            .where(media_assets.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc


class PostgresTextItemRepository:
    """PostgreSQL repository for text library items."""

    def __init__(self, engine: Any, user_id: str):
        self._engine = engine
        self._user_id = user_id

    def save(self, item: TextItem) -> None:
        row = text_item_to_row(self._user_id, item)
        statement = insert(text_items).values(**row)
        update_values = {
            column.name: statement.excluded[column.name]
            for column in text_items.c
            if column.name not in {"id", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            index_elements=[text_items.c.id],
            set_=update_values,
        )

        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc

    def get(self, item_id: str) -> Optional[TextItem]:
        statement = (
            select(text_items)
            .where(text_items.c.user_id == self._user_id)
            .where(text_items.c.id == item_id)
            .where(text_items.c.deleted_at.is_(None))
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return row_to_text_item(row) if row else None

    def list_for_project(self, project_id: str) -> list[TextItem]:
        statement = (
            select(text_items)
            .where(text_items.c.user_id == self._user_id)
            .where(text_items.c.project_id == project_id)
            .where(text_items.c.deleted_at.is_(None))
            .order_by(text_items.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_text_item(row) for row in rows]

    def list_all(self) -> list[TextItem]:
        statement = (
            select(text_items)
            .where(text_items.c.user_id == self._user_id)
            .where(text_items.c.deleted_at.is_(None))
            .order_by(text_items.c.created_at.desc())
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [row_to_text_item(row) for row in rows]

    def delete(self, item_id: str) -> None:
        self.mark_deleted(item_id)

    def mark_deleted(self, item_id: str) -> None:
        statement = (
            update(text_items)
            .where(text_items.c.user_id == self._user_id)
            .where(text_items.c.id == item_id)
            .where(text_items.c.deleted_at.is_(None))
            .values(deleted_at=datetime.now())
        )
        try:
            with self._engine.begin() as connection:
                connection.execute(statement)
        except Exception as exc:
            raise RepositoryWriteError(str(exc)) from exc
