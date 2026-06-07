from datetime import datetime

import pytest

from app.models.character import Character
from app.models.frame import Frame
from app.models.prop import Prop
from app.models.scene import Scene
from app.models.style import Style
from app.models.video import TaskStatus, Video, VideoTask
from app.repositories.project_entities import CHARACTER, FRAME, PROP, SCENE, STYLE, VIDEO
from app.services.storage import StorageService


def _character(entity_id: str = "character-1") -> Character:
    return Character(
        id=entity_id,
        project_id="project-1",
        name="character",
        description="description",
        appearance="appearance",
        personality="personality",
        created_at=datetime(2026, 6, 7, 22, 0, 0),
        updated_at=datetime(2026, 6, 7, 22, 1, 0),
    )


def _scene(entity_id: str = "scene-1") -> Scene:
    return Scene(
        id=entity_id,
        project_id="project-1",
        name="scene",
        description="description",
        scene_prompt="scene prompt",
        created_at=datetime(2026, 6, 7, 22, 2, 0),
        updated_at=datetime(2026, 6, 7, 22, 3, 0),
    )


def _prop(entity_id: str = "prop-1") -> Prop:
    return Prop(
        id=entity_id,
        project_id="project-1",
        name="prop",
        description="description",
        prop_prompt="prop prompt",
        created_at=datetime(2026, 6, 7, 22, 4, 0),
        updated_at=datetime(2026, 6, 7, 22, 5, 0),
    )


def _frame(entity_id: str = "frame-1") -> Frame:
    return Frame(
        id=entity_id,
        project_id="project-1",
        shot_id="shot-1",
        shot_number=1,
        prompt="frame prompt",
        created_at=datetime(2026, 6, 7, 22, 6, 0),
        updated_at=datetime(2026, 6, 7, 22, 7, 0),
    )


def _video(entity_id: str = "video-1") -> Video:
    return Video(
        id=entity_id,
        project_id="project-1",
        shot_id="shot-1",
        shot_number=1,
        first_frame_url="https://example.test/frame.png",
        prompt="video prompt",
        video_url="https://example.test/video.mp4",
        task=VideoTask(task_id="provider-task-1", status=TaskStatus.PROCESSING),
        created_at=datetime(2026, 6, 7, 22, 8, 0),
        updated_at=datetime(2026, 6, 7, 22, 9, 0),
    )


def _style(entity_id: str = "style-1") -> Style:
    return Style(
        id=entity_id,
        project_id="project-1",
        name="style",
        description="description",
        style_type="text",
        text_style_content="{\"palette\":\"warm\"}",
        created_at=datetime(2026, 6, 7, 22, 10, 0),
        updated_at=datetime(2026, 6, 7, 22, 11, 0),
    )


class _ShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, entity_kind, entity):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append((entity_kind, entity.model_copy(deep=True)))

    def mark_deleted(self, entity_kind, entity_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append((entity_kind, entity_id))


def _enable_dual_write(monkeypatch, *, strict=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "project_entities")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true" if strict else "false")


def _patch_shadow_repository(monkeypatch, shadow, seen_user_ids=None):
    if seen_user_ids is None:
        seen_user_ids = []
    monkeypatch.setattr(
        "app.repositories.project_entity_runtime.build_project_entity_shadow_repository",
        lambda user_id: seen_user_ids.append(user_id) or shadow,
    )
    return seen_user_ids


def test_project_entity_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    shadow = _ShadowRepository()
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_character(_character())
    storage.save_scene(_scene())
    storage.save_prop(_prop())
    storage.save_frame(_frame())
    storage.save_video(_video())
    storage.save_style(_style())
    storage.delete_character("character-1")
    storage.delete_scene("scene-1")
    storage.delete_prop("prop-1")
    storage.delete_frame("frame-1")
    storage.delete_video("video-1")
    storage.delete_style("style-1")

    assert shadow.saved == []
    assert shadow.deleted == []


def test_project_entity_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository()
    seen_user_ids = _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_character(_character())
    storage.save_scene(_scene())
    storage.save_prop(_prop())
    storage.save_frame(_frame())
    storage.save_video(_video())
    storage.save_style(_style())
    storage.delete_character("character-1")
    storage.delete_scene("scene-1")
    storage.delete_prop("prop-1")
    storage.delete_frame("frame-1")
    storage.delete_video("video-1")
    storage.delete_style("style-1")

    assert seen_user_ids == ["user-1"] * 12
    assert [(kind, entity.id) for kind, entity in shadow.saved] == [
        (CHARACTER, "character-1"),
        (SCENE, "scene-1"),
        (PROP, "prop-1"),
        (FRAME, "frame-1"),
        (VIDEO, "video-1"),
        (STYLE, "style-1"),
    ]
    assert shadow.saved[0][1].updated_at != datetime(2026, 6, 7, 22, 1, 0)
    assert shadow.deleted == [
        (CHARACTER, "character-1"),
        (SCENE, "scene-1"),
        (PROP, "prop-1"),
        (FRAME, "frame-1"),
        (VIDEO, "video-1"),
        (STYLE, "style-1"),
    ]
    assert storage.get_character("character-1") is None
    assert storage.get_style("style-1") is None


def test_project_entity_shadow_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    shadow = _ShadowRepository(fail=True)
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_character(_character())
    storage.save_frame(_frame())

    assert storage.get_character("character-1") is not None
    assert storage.get_frame("frame-1") is not None


def test_project_entity_shadow_failure_can_be_strict(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch, strict=True)
    shadow = _ShadowRepository(fail=True)
    _patch_shadow_repository(monkeypatch, shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    with pytest.raises(RuntimeError, match="postgres unavailable"):
        storage.save_character(_character())

    assert storage.get_character("character-1") is not None
