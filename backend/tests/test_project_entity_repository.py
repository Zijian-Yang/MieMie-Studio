from datetime import datetime, timedelta

from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import TaskStatus, Video, VideoTask
from app.repositories.base import RepositoryWriteError
from app.repositories.project_entities import (
    CHARACTER,
    FRAME,
    PROP,
    SCENE,
    STYLE,
    VIDEO,
    DualProjectEntityRepository,
    FileProjectEntityRepository,
    entity_to_row,
    row_to_entity,
)
from app.services.storage import StorageService


def _character(entity_id: str = "character-1", **overrides) -> Character:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": f"character {entity_id}",
        "description": "description",
        "appearance": "blue coat",
        "personality": "brave",
        "created_at": datetime(2026, 6, 7, 18, 0, 0),
        "updated_at": datetime(2026, 6, 7, 18, 1, 0),
    }
    base.update(overrides)
    return Character(**base)


def _scene(entity_id: str = "scene-1", **overrides) -> Scene:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": f"scene {entity_id}",
        "description": "description",
        "scene_prompt": "street at night",
        "selected_group_index": 1,
        "created_at": datetime(2026, 6, 7, 18, 2, 0),
        "updated_at": datetime(2026, 6, 7, 18, 3, 0),
    }
    base.update(overrides)
    return Scene(**base)


def _prop(entity_id: str = "prop-1", **overrides) -> Prop:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": f"prop {entity_id}",
        "description": "description",
        "prop_prompt": "glowing key",
        "created_at": datetime(2026, 6, 7, 18, 4, 0),
        "updated_at": datetime(2026, 6, 7, 18, 5, 0),
    }
    base.update(overrides)
    return Prop(**base)


def _frame(entity_id: str = "frame-1", **overrides) -> Frame:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "shot_id": "shot-1",
        "shot_number": 2,
        "prompt": "first frame prompt",
        "created_at": datetime(2026, 6, 7, 18, 6, 0),
        "updated_at": datetime(2026, 6, 7, 18, 7, 0),
    }
    base.update(overrides)
    return Frame(**base)


def _video(entity_id: str = "video-1", **overrides) -> Video:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "shot_id": "shot-1",
        "shot_number": 2,
        "first_frame_url": "https://example.test/frame.png",
        "prompt": "video prompt",
        "video_url": "https://example.test/video.mp4",
        "task": VideoTask(task_id="provider-task-1", status=TaskStatus.PROCESSING),
        "created_at": datetime(2026, 6, 7, 18, 8, 0),
        "updated_at": datetime(2026, 6, 7, 18, 9, 0),
    }
    base.update(overrides)
    return Video(**base)


def _style(entity_id: str = "style-1", **overrides) -> Style:
    base = {
        "id": entity_id,
        "project_id": "project-1",
        "name": f"style {entity_id}",
        "description": "description",
        "style_type": "text",
        "text_style_content": "{\"palette\":\"warm\"}",
        "is_selected": True,
        "created_at": datetime(2026, 6, 7, 18, 10, 0),
        "updated_at": datetime(2026, 6, 7, 18, 11, 0),
    }
    base.update(overrides)
    return Style(**base)


def test_project_entity_row_mapping_keeps_index_columns_and_raw_snapshots():
    cases = [
        (CHARACTER, _character(), {"name": "character character-1"}),
        (SCENE, _scene(), {"name": "scene scene-1", "selected_group_index": 1}),
        (PROP, _prop(), {"name": "prop prop-1"}),
        (FRAME, _frame(), {"shot_id": "shot-1", "shot_number": 2}),
        (VIDEO, _video(), {"shot_id": "shot-1", "shot_number": 2, "status": "processing"}),
        (STYLE, _style(), {"name": "style style-1"}),
    ]

    for entity_kind, entity, expected in cases:
        row = entity_to_row("user-1", entity_kind, entity)

        assert row["id"] == entity.id
        assert row["entity_kind"] == entity_kind
        assert row["user_id"] == "user-1"
        assert row["project_id"] == "project-1"
        assert row["raw_entity_snapshot"]["id"] == entity.id
        assert row["raw_entity_snapshot"]["updated_at"] == entity.updated_at.isoformat()
        for key, value in expected.items():
            assert row[key] == value
        assert row_to_entity(row) == entity


def test_file_project_entity_repository_preserves_storage_behavior(tmp_path):
    storage = StorageService(str(tmp_path))
    repo = FileProjectEntityRepository(storage)
    older = _frame("older", shot_number=1, created_at=datetime.now() - timedelta(days=2))
    newer = _frame("newer", shot_number=2)

    repo.save_character(_character())
    repo.save_scene(_scene())
    repo.save_prop(_prop())
    repo.save_frame(newer)
    repo.save_frame(older)
    repo.save_video(_video())
    repo.save_style(_style())

    assert repo.get_character("character-1").id == "character-1"
    assert repo.get_scene("scene-1").id == "scene-1"
    assert repo.get_prop("prop-1").id == "prop-1"
    assert [character.id for character in repo.list_all(CHARACTER)] == ["character-1"]
    assert repo.get_frame("newer").id == "newer"
    assert repo.get_frame_by_shot("project-1", "shot-1").id == "newer"
    assert [frame.id for frame in repo.list_frames_for_project("project-1")] == ["older", "newer"]
    assert [frame.id for frame in repo.list_all(FRAME)] == ["older", "newer"]
    assert repo.get_video("video-1").id == "video-1"
    assert repo.get_video_by_shot("project-1", "shot-1").id == "video-1"
    assert repo.get_video_by_task("provider-task-1").id == "video-1"
    assert repo.get_style("style-1").id == "style-1"

    repo.delete_character("character-1")
    repo.delete_frame("newer")

    assert repo.get_character("character-1") is None
    assert repo.get_frame("newer") is None


class _RecordingRepository:
    def __init__(self, *, fail_on_save: bool = False):
        self.fail_on_save = fail_on_save
        self.saved = []
        self.deleted = []
        self.entities = {}

    def save(self, entity_kind, entity):
        if self.fail_on_save:
            raise RepositoryWriteError("postgres unavailable")
        self.saved.append((entity_kind, entity.id))
        self.entities[(entity_kind, entity.id)] = entity

    def get(self, entity_kind, entity_id):
        return self.entities.get((entity_kind, entity_id))

    def list_for_project(self, entity_kind, project_id):
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind and entity.project_id == project_id
        ]

    def list_all(self, entity_kind):
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind
        ]

    def delete(self, entity_kind, entity_id):
        self.deleted.append((entity_kind, entity_id))
        self.entities.pop((entity_kind, entity_id), None)

    def mark_deleted(self, entity_kind, entity_id):
        self.delete(entity_kind, entity_id)


def test_dual_project_entity_repository_saves_file_first_and_tolerates_shadow_failure():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualProjectEntityRepository(primary, shadow, strict_shadow_writes=False)
    character = _character()

    repo.save(CHARACTER, character)

    assert primary.saved == [(CHARACTER, "character-1")]
    assert shadow.saved == []
    assert repo.get(CHARACTER, "character-1") == character
    assert repo.list_all(CHARACTER) == [character]


def test_dual_project_entity_repository_can_enforce_strict_shadow_writes():
    primary = _RecordingRepository()
    shadow = _RecordingRepository(fail_on_save=True)
    repo = DualProjectEntityRepository(primary, shadow, strict_shadow_writes=True)

    try:
        repo.save(CHARACTER, _character())
    except RepositoryWriteError as exc:
        assert "postgres unavailable" in str(exc)
    else:
        raise AssertionError("strict dual write should propagate PostgreSQL failures")

    assert primary.saved == [(CHARACTER, "character-1")]
