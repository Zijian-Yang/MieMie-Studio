from datetime import datetime

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.services.storage import StorageService


def _gallery_image(image_id: str, *, project_id: str = "project-1") -> GalleryImage:
    return GalleryImage(
        id=image_id,
        project_id=project_id,
        name=f"image {image_id}",
        description="description",
        url=f"https://example.test/{image_id}.png",
        source="upload",
        created_at=datetime(2026, 6, 7, 16, 0, 0),
        updated_at=datetime(2026, 6, 7, 16, 1, 0),
    )


def _audio_item(audio_id: str, *, project_id: str = "project-1") -> AudioItem:
    return AudioItem(
        id=audio_id,
        project_id=project_id,
        name=f"audio {audio_id}",
        description="description",
        url=f"https://example.test/{audio_id}.mp3",
        file_type="mp3",
        file_size=123,
        duration=1.5,
        created_at=datetime(2026, 6, 7, 16, 2, 0),
        updated_at=datetime(2026, 6, 7, 16, 3, 0),
    )


def _video_item(video_id: str, *, project_id: str = "project-1") -> VideoItem:
    return VideoItem(
        id=video_id,
        project_id=project_id,
        name=f"video {video_id}",
        description="description",
        url=f"https://example.test/{video_id}.mp4",
        file_type="mp4",
        file_size=456,
        duration=2.5,
        width=1280,
        height=720,
        fps=24,
        created_at=datetime(2026, 6, 7, 16, 4, 0),
        updated_at=datetime(2026, 6, 7, 16, 5, 0),
    )


def _text_item(text_id: str, *, project_id: str = "project-1") -> TextItem:
    return TextItem(
        id=text_id,
        project_id=project_id,
        name=f"text {text_id}",
        content="content",
        category="prompt",
        created_at=datetime(2026, 6, 7, 16, 6, 0),
        updated_at=datetime(2026, 6, 7, 16, 7, 0),
    )


class _ReadMediaRepository:
    def __init__(self, *, gallery=None, audio=None, video=None, fail=False):
        self.gallery = {item.id: item for item in (gallery or [])}
        self.audio = {item.id: item for item in (audio or [])}
        self.video = {item.id: item for item in (video or [])}
        self.fail = fail
        self.calls = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres media read unavailable")

    def get_gallery_image(self, image_id):
        self.calls.append(("get_gallery", image_id))
        self._maybe_fail()
        return self.gallery.get(image_id)

    def list_gallery_images_for_project(self, project_id):
        self.calls.append(("list_gallery", project_id))
        self._maybe_fail()
        return [item for item in self.gallery.values() if item.project_id == project_id]

    def get_audio_item(self, audio_id):
        self.calls.append(("get_audio", audio_id))
        self._maybe_fail()
        return self.audio.get(audio_id)

    def list_audio_items_for_project(self, project_id):
        self.calls.append(("list_audio", project_id))
        self._maybe_fail()
        return [item for item in self.audio.values() if item.project_id == project_id]

    def get_video_item(self, video_id):
        self.calls.append(("get_video", video_id))
        self._maybe_fail()
        return self.video.get(video_id)

    def list_video_items_for_project(self, project_id):
        self.calls.append(("list_video", project_id))
        self._maybe_fail()
        return [item for item in self.video.values() if item.project_id == project_id]


class _ReadTextRepository:
    def __init__(self, *, texts=None, fail=False):
        self.texts = {item.id: item for item in (texts or [])}
        self.fail = fail
        self.calls = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres text read unavailable")

    def get(self, item_id):
        self.calls.append(("get_text", item_id))
        self._maybe_fail()
        return self.texts.get(item_id)

    def list_for_project(self, project_id):
        self.calls.append(("list_text", project_id))
        self._maybe_fail()
        return [item for item in self.texts.values() if item.project_id == project_id]


def _enable_read_switch(monkeypatch, *, fallback=True):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_DOMAINS", "media_metadata")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_FALLBACK_READ", "true" if fallback else "false")


def _patch_read_repositories(monkeypatch, media_repo, text_repo):
    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_media_asset_read_repository",
        lambda user_id: media_repo,
    )
    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_text_item_read_repository",
        lambda user_id: text_repo,
    )


def test_media_metadata_reads_are_file_only_by_default(tmp_path, monkeypatch):
    media_repo = _ReadMediaRepository(gallery=[_gallery_image("pg-image")])
    text_repo = _ReadTextRepository(texts=[_text_item("pg-text")])
    _patch_read_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_gallery_image(_gallery_image("json-image"))
    storage.save_text_item(_text_item("json-text"))

    assert storage.get_gallery_image("json-image").id == "json-image"
    assert [item.id for item in storage.get_gallery_images_by_project("project-1")] == [
        "json-image"
    ]
    assert storage.get_text_item("json-text").id == "json-text"
    assert [item.id for item in storage.get_text_items("project-1")] == ["json-text"]
    assert media_repo.calls == []
    assert text_repo.calls == []


def test_media_metadata_read_switch_uses_postgres_for_get_and_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    media_repo = _ReadMediaRepository(
        gallery=[_gallery_image("pg-image")],
        audio=[_audio_item("pg-audio")],
        video=[_video_item("pg-video")],
    )
    text_repo = _ReadTextRepository(texts=[_text_item("pg-text")])
    _patch_read_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    assert storage.get_gallery_image("pg-image").id == "pg-image"
    assert [item.id for item in storage.get_gallery_images_by_project("project-1")] == [
        "pg-image"
    ]
    assert storage.get_audio_item("pg-audio").id == "pg-audio"
    assert [item.id for item in storage.get_audio_items("project-1")] == ["pg-audio"]
    assert storage.get_video_item("pg-video").id == "pg-video"
    assert [item.id for item in storage.get_video_items("project-1")] == ["pg-video"]
    assert storage.get_text_item("pg-text").id == "pg-text"
    assert [item.id for item in storage.get_text_items("project-1")] == ["pg-text"]


def test_media_metadata_read_switch_falls_back_to_json_on_miss_or_empty_list(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch)
    media_repo = _ReadMediaRepository()
    text_repo = _ReadTextRepository()
    _patch_read_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_gallery_image(_gallery_image("json-image"))
    storage.save_audio_item(_audio_item("json-audio"))
    storage.save_video_item(_video_item("json-video"))
    storage.save_text_item(_text_item("json-text"))

    assert storage.get_gallery_image("json-image").id == "json-image"
    assert [item.id for item in storage.get_gallery_images_by_project("project-1")] == [
        "json-image"
    ]
    assert storage.get_audio_item("json-audio").id == "json-audio"
    assert [item.id for item in storage.get_audio_items("project-1")] == ["json-audio"]
    assert storage.get_video_item("json-video").id == "json-video"
    assert [item.id for item in storage.get_video_items("project-1")] == ["json-video"]
    assert storage.get_text_item("json-text").id == "json-text"
    assert [item.id for item in storage.get_text_items("project-1")] == ["json-text"]


def test_media_metadata_read_switch_raises_when_fallback_disabled(tmp_path, monkeypatch):
    _enable_read_switch(monkeypatch, fallback=False)
    media_repo = _ReadMediaRepository(fail=True)
    text_repo = _ReadTextRepository()
    _patch_read_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")
    storage.save_gallery_image(_gallery_image("json-image"))

    try:
        storage.get_gallery_image("json-image")
    except RuntimeError as exc:
        assert "postgres media read unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL read errors should propagate when fallback is disabled")
