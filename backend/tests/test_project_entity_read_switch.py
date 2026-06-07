from datetime import datetime

from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import TaskStatus, Video, VideoTask
from app.repositories.project_entities import CHARACTER, FRAME, PROP, SCENE, STYLE, VIDEO
from app.services.storage import StorageService


def _character(entity_id: str, *, project_id: str = "project-1") -> Character:
    return Character(
        id=entity_id,
        project_id=project_id,
        name=f"character {entity_id}",
        created_at=datetime(2026, 6, 7, 23, 0, 0),
        updated_at=datetime(2026, 6, 7, 23, 1, 0),
    )


def _scene(entity_id: str, *, project_id: str = "project-1") -> Scene:
    return Scene(
        id=entity_id,
        project_id=project_id,
        name=f"scene {entity_id}",
        created_at=datetime(2026, 6, 7, 23, 2, 0),
        updated_at=datetime(2026, 6, 7, 23, 3, 0),
    )


def _prop(entity_id: str, *, project_id: str = "project-1") -> Prop:
    return Prop(
        id=entity_id,
        project_id=project_id,
        name=f"prop {entity_id}",
        created_at=datetime(2026, 6, 7, 23, 4, 0),
        updated_at=datetime(2026, 6, 7, 23, 5, 0),
    )


def _frame(entity_id: str, *, project_id: str = "project-1", shot_id: str = "shot-1", shot_number: int = 1) -> Frame:
    return Frame(
        id=entity_id,
        project_id=project_id,
        shot_id=shot_id,
        shot_number=shot_number,
        prompt=f"frame {entity_id}",
        created_at=datetime(2026, 6, 7, 23, 6, 0),
        updated_at=datetime(2026, 6, 7, 23, 7, 0),
    )


def _video(
    entity_id: str,
    *,
    project_id: str = "project-1",
    shot_id: str = "shot-1",
    shot_number: int = 1,
    task_id: str = "provider-task-1",
) -> Video:
    return Video(
        id=entity_id,
        project_id=project_id,
        shot_id=shot_id,
        shot_number=shot_number,
        prompt=f"video {entity_id}",
        task=VideoTask(task_id=task_id, status=TaskStatus.PROCESSING),
        created_at=datetime(2026, 6, 7, 23, 8, 0),
        updated_at=datetime(2026, 6, 7, 23, 9, 0),
    )


def _style(entity_id: str, *, project_id: str = "project-1") -> Style:
    return Style(
        id=entity_id,
        project_id=project_id,
        name=f"style {entity_id}",
        created_at=datetime(2026, 6, 7, 23, 10, 0),
        updated_at=datetime(2026, 6, 7, 23, 11, 0),
    )


class _ReadRepository:
    def __init__(self, entities=None, *, fail=False):
        self.entities = {
            (entity_kind, entity.id): entity
            for entity_kind, entity in (entities or [])
        }
        self.fail = fail
        self.calls = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres project entity read unavailable")

    def get(self, entity_kind, entity_id):
        self.calls.append(("get", entity_kind, entity_id))
        self._maybe_fail()
        return self.entities.get((entity_kind, entity_id))

    def list_for_project(self, entity_kind, project_id):
        self.calls.append(("list_for_project", entity_kind, project_id))
        self._maybe_fail()
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind and entity.project_id == project_id
        ]

    def list_all(self, entity_kind):
        self.calls.append(("list_all", entity_kind))
        self._maybe_fail()
        return [
            entity
            for (kind, _), entity in self.entities.items()
            if kind == entity_kind
        ]


def _enable_read_switch(monkeypatch, *, fallback=True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "project_entities")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def _patch_read_repository(monkeypatch, repository):
    monkeypatch.setattr(
        "app.repositories.project_entity_runtime.build_project_entity_read_repository",
        lambda user_id: repository,
    )


def test_project_entity_reads_are_file_only_by_default(tmp_path, monkeypatch):
    repository = _ReadRepository([(CHARACTER, _character("pg-character"))])
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_character(_character("json-character"))
    storage.save_frame(_frame("json-frame"))

    assert storage.get_character("json-character").id == "json-character"
    assert [item.id for item in storage.get_characters_by_project("project-1")] == ["json-character"]
    assert storage.get_frame_by_shot("project-1", "shot-1").id == "json-frame"
    assert repository.calls == []


def test_project_entity_read_switch_uses_postgres_for_get_and_project_lists(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repository = _ReadRepository(
        [
            (CHARACTER, _character("pg-character")),
            (SCENE, _scene("pg-scene")),
            (PROP, _prop("pg-prop")),
            (FRAME, _frame("pg-frame", shot_id="shot-pg")),
            (VIDEO, _video("pg-video", shot_id="shot-pg", task_id="provider-pg")),
            (STYLE, _style("pg-style")),
        ]
    )
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    assert storage.get_character("pg-character").id == "pg-character"
    assert [item.id for item in storage.get_characters_by_project("project-1")] == ["pg-character"]
    assert storage.get_scene("pg-scene").id == "pg-scene"
    assert [item.id for item in storage.get_scenes_by_project("project-1")] == ["pg-scene"]
    assert storage.get_prop("pg-prop").id == "pg-prop"
    assert [item.id for item in storage.get_props_by_project("project-1")] == ["pg-prop"]
    assert storage.get_frame("pg-frame").id == "pg-frame"
    assert storage.get_frame_by_shot("project-1", "shot-pg").id == "pg-frame"
    assert [item.id for item in storage.get_frames_by_project("project-1")] == ["pg-frame"]
    assert storage.get_video("pg-video").id == "pg-video"
    assert storage.get_video_by_shot("project-1", "shot-pg").id == "pg-video"
    assert storage.get_video_by_task("provider-pg").id == "pg-video"
    assert [item.id for item in storage.get_videos_by_project("project-1")] == ["pg-video"]
    assert storage.get_style("pg-style").id == "pg-style"
    assert [item.id for item in storage.get_styles_by_project("project-1")] == ["pg-style"]


def test_project_entity_read_switch_falls_back_to_json_on_miss_or_empty_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    repository = _ReadRepository()
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_character(_character("json-character"))
    storage.save_frame(_frame("json-frame"))
    storage.save_video(_video("json-video", task_id="provider-json"))

    assert storage.get_character("json-character").id == "json-character"
    assert [item.id for item in storage.get_characters_by_project("project-1")] == ["json-character"]
    assert storage.get_frame_by_shot("project-1", "shot-1").id == "json-frame"
    assert storage.get_video_by_task("provider-json").id == "json-video"
    assert [item.id for item in storage.get_videos_by_project("project-1")] == ["json-video"]


def test_project_entity_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    repository = _ReadRepository(fail=True)
    _patch_read_repository(monkeypatch, repository)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_character(_character("json-character"))

    try:
        storage.get_character("json-character")
    except RuntimeError as exc:
        assert "postgres project entity read unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL read errors should propagate when fallback is disabled")
