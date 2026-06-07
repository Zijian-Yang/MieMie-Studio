"""Shared repository contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Optional, Protocol

from app.models.project import Project
from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem, VideoStudioTask
from app.models.studio import StudioTask


class RepositoryMode(StrEnum):
    FILE = "file"
    POSTGRES = "postgres"
    DUAL = "dual"


class RepositoryWriteError(RuntimeError):
    """Raised when a repository write cannot be completed."""


class VideoStudioTaskRepository(Protocol):
    def save(self, task: VideoStudioTask) -> None:
        """Persist a video studio task."""

    def get(self, task_id: str) -> Optional[VideoStudioTask]:
        """Return a task by id, or None when it does not exist."""

    def list_for_project(self, project_id: str) -> list[VideoStudioTask]:
        """Return tasks for a project in the legacy list order."""

    def list_all(self) -> list[VideoStudioTask]:
        """Return all tasks in the legacy list order."""

    def delete(self, task_id: str) -> None:
        """Delete a task."""

    def mark_deleted(self, task_id: str) -> None:
        """Mark a task deleted, using soft delete when supported."""


class StudioTaskRepository(Protocol):
    def save(self, task: StudioTask) -> None:
        """Persist an image studio task."""

    def get(self, task_id: str) -> Optional[StudioTask]:
        """Return a task by id, or None when it does not exist."""

    def list_for_project(self, project_id: str) -> list[StudioTask]:
        """Return tasks for a project in the legacy list order."""

    def list_all(self) -> list[StudioTask]:
        """Return all image studio tasks in the legacy list order."""

    def delete(self, task_id: str) -> None:
        """Delete a task."""

    def mark_deleted(self, task_id: str) -> None:
        """Mark a task deleted, using soft delete when supported."""


class ProjectRepository(Protocol):
    def save(self, project: Project) -> None:
        """Persist a project."""

    def get(self, project_id: str) -> Optional[Project]:
        """Return a project by id, or None when it does not exist."""

    def list_all(self) -> list[Project]:
        """Return all projects in the legacy list order."""

    def delete(self, project_id: str) -> None:
        """Delete a project."""

    def mark_deleted(self, project_id: str) -> None:
        """Mark a project deleted, using soft delete when supported."""


class MediaAssetRepository(Protocol):
    def save_gallery_image(self, image: GalleryImage) -> None:
        """Persist a gallery image."""

    def get_gallery_image(self, image_id: str) -> Optional[GalleryImage]:
        """Return a gallery image by id, or None."""

    def list_gallery_images_for_project(self, project_id: str) -> list[GalleryImage]:
        """Return gallery images for a project in the legacy list order."""

    def list_all_gallery_images(self) -> list[GalleryImage]:
        """Return all gallery images in this user namespace."""

    def delete_gallery_image(self, image_id: str) -> None:
        """Delete a gallery image."""

    def save_audio_item(self, audio: AudioItem) -> None:
        """Persist an audio library item."""

    def get_audio_item(self, audio_id: str) -> Optional[AudioItem]:
        """Return an audio item by id, or None."""

    def list_audio_items_for_project(self, project_id: str) -> list[AudioItem]:
        """Return audio items for a project in the legacy list order."""

    def list_all_audio_items(self) -> list[AudioItem]:
        """Return all audio items in this user namespace."""

    def delete_audio_item(self, audio_id: str) -> None:
        """Delete an audio item."""

    def save_video_item(self, video: VideoItem) -> None:
        """Persist a video library item."""

    def get_video_item(self, video_id: str) -> Optional[VideoItem]:
        """Return a video item by id, or None."""

    def list_video_items_for_project(self, project_id: str) -> list[VideoItem]:
        """Return video items for a project in the legacy list order."""

    def list_all_video_items(self) -> list[VideoItem]:
        """Return all video items in this user namespace."""

    def delete_video_item(self, video_id: str) -> None:
        """Delete a video item."""

    def mark_deleted(self, asset_id: str) -> None:
        """Mark an asset deleted, using soft delete when supported."""


class TextItemRepository(Protocol):
    def save(self, item: TextItem) -> None:
        """Persist a text library item."""

    def get(self, item_id: str) -> Optional[TextItem]:
        """Return a text item by id, or None."""

    def list_for_project(self, project_id: str) -> list[TextItem]:
        """Return text items for a project in the legacy list order."""

    def list_all(self) -> list[TextItem]:
        """Return all text items in this user namespace."""

    def delete(self, item_id: str) -> None:
        """Delete a text item."""

    def mark_deleted(self, item_id: str) -> None:
        """Mark a text item deleted, using soft delete when supported."""
