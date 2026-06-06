from datetime import datetime, timedelta

from app.models.studio import StudioTask, StudioTaskImage
from app.repositories.base import RepositoryWriteError
from app.repositories.studio_tasks import (
    DualStudioTaskRepository,
    FileStudioTaskRepository,
    row_to_studio_task,
    studio_task_to_row,
)
from app.services.storage import StorageService


def _task(task_id: str, project_id: str = "project-1", **overrides) -> StudioTask:
    base = {
        "id": task_id,
        "project_id": project_id,
        "name": f"task {task_id}",
        "description": "description",
        "task_kind": "image_edit",
        "provider": "wan",
        "model_id": "wan2.7-image",
        "model": "wan2.7-image",
        "status": "generating",
        "group_count": 2,
        "n": 1,
        "prompt": "hello",
        "negative_prompt": "bad",
        "input_assets": {"kind": "gallery"},
        "normalized_params": {"size": "1280*1280"},
        "provider_payload_snapshot": {"model": "wan2.7-image"},
        "provider_result_meta": {"elapsed_ms": 120},
        "task_ids": ["dashscope-task-1"],
        "request_ids": ["request-1"],
        "images": [
            StudioTaskImage(
                group_index=0,
                url="https://example.test/image.png",
                is_selected=True,
            )
        ],
        "warnings": ["oss fallback"],
        "error_message": None,
        "last_task_id": "dashscope-task-1",
        "last_request_id": "request-1",
        "created_at": datetime(2026, 6, 7, 8, 0, 0),
        "updated_at": datetime(2026, 6, 7, 8, 31, 0),
    }
    base.update(overrides)
    return StudioTask(**base)


def test_file_studio_task_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileStudioTaskRepository(storage)
    older_updated_at = datetime.now() - timedelta(days=2)
    older = _task(
        "older",
        created_at=datetime.now() - timedelta(days=1),
        updated_at=older_updated_at,
    )
    newer = _task("newer", created_at=datetime.now(), updated_at=datetime.now())
    other_project = _task(
        "other",
        project_id="project-2",
        created_at=datetime.now() - timedelta(hours=1),
        updated_at=datetime.now(),
    )

    repo.save(older)
    repo.save(newer)
    repo.save(other_project)

    assert repo.get("older").id == "older"
    assert repo.get("missing") is None
    assert repo.get("older").updated_at >= older_updated_at
    assert [task.id for task in repo.list_for_project("project-1")] == ["newer", "older"]
    assert [task.id for task in repo.list_all()] == ["newer", "other", "older"]

    repo.delete("older")

    assert repo.get("older") is None


def test_studio_task_row_mapping_keeps_index_columns_and_raw_snapshot():
    task = _task("task-1")

    row = studio_task_to_row("user-1", task)

    assert row["id"] == "task-1"
    assert row["user_id"] == "user-1"
    assert row["project_id"] == "project-1"
    assert row["task_kind"] == "image_edit"
    assert row["provider"] == "wan"
    assert row["status"] == "generating"
    assert row["image_count"] == 1
    assert row["selected_image_count"] == 1
    assert row["raw_task_snapshot"]["id"] == "task-1"
    assert row["raw_task_snapshot"]["created_at"] == "2026-06-07T08:00:00"

    restored = row_to_studio_task(row)

    assert restored == task


class _RecordingRepository:
    def __init__(self, *, fail_on_save: bool = False):
        self.fail_on_save = fail_on_save
        self.saved = []
        self.deleted = []
        self.tasks = {}

    def save(self, task):
        if self.fail_on_save:
            raise RepositoryWriteError("postgres unavailable")
        self.saved.append(task.id)
        self.tasks[task.id] = task

    def get(self, task_id):
        return self.tasks.get(task_id)

    def list_for_project(self, project_id):
        return [task for task in self.tasks.values() if task.project_id == project_id]

    def list_all(self):
        return list(self.tasks.values())

    def delete(self, task_id):
        self.deleted.append(task_id)
        self.tasks.pop(task_id, None)

    def mark_deleted(self, task_id):
        self.delete(task_id)


def test_dual_studio_task_repository_saves_file_first_and_tolerates_shadow_failure():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualStudioTaskRepository(primary, shadow, strict_shadow_writes=False)
    task = _task("task-1")

    repo.save(task)

    assert primary.saved == ["task-1"]
    assert shadow.saved == []
    assert repo.get("task-1") == task


def test_dual_studio_task_repository_can_enforce_strict_shadow_writes():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualStudioTaskRepository(primary, shadow, strict_shadow_writes=True)

    try:
        repo.save(_task("task-1"))
    except RepositoryWriteError as exc:
        assert "postgres unavailable" in str(exc)
    else:
        raise AssertionError("strict dual write should propagate PostgreSQL failures")

    assert primary.saved == ["task-1"]
