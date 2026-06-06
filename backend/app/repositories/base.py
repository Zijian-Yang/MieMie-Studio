"""Shared repository contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Optional, Protocol

from app.models.media import VideoStudioTask
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
