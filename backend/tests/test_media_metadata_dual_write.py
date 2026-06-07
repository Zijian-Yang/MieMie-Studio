from datetime import datetime

from app.models.gallery import GalleryImage
from app.models.media import AudioItem, TextItem, VideoItem
from app.services.storage import StorageService


def _gallery_image(image_id: str = "image-1") -> GalleryImage:
    return GalleryImage(
        id=image_id,
        project_id="project-1",
        name="image",
        description="description",
        url="https://example.test/image.png",
        source="upload",
        created_at=datetime(2026, 6, 7, 15, 0, 0),
        updated_at=datetime(2026, 6, 7, 15, 1, 0),
    )


def _audio_item(audio_id: str = "audio-1") -> AudioItem:
    return AudioItem(
        id=audio_id,
        project_id="project-1",
        name="audio",
        description="description",
        url="https://example.test/audio.mp3",
        file_type="mp3",
        file_size=123,
        duration=1.5,
        created_at=datetime(2026, 6, 7, 15, 2, 0),
        updated_at=datetime(2026, 6, 7, 15, 3, 0),
    )


def _video_item(video_id: str = "video-1") -> VideoItem:
    return VideoItem(
        id=video_id,
        project_id="project-1",
        name="video",
        description="description",
        url="https://example.test/video.mp4",
        file_type="mp4",
        file_size=456,
        duration=2.5,
        width=1280,
        height=720,
        fps=24,
        created_at=datetime(2026, 6, 7, 15, 4, 0),
        updated_at=datetime(2026, 6, 7, 15, 5, 0),
    )


def _text_item(text_id: str = "text-1") -> TextItem:
    return TextItem(
        id=text_id,
        project_id="project-1",
        name="text",
        content="content",
        category="prompt",
        created_at=datetime(2026, 6, 7, 15, 6, 0),
        updated_at=datetime(2026, 6, 7, 15, 7, 0),
    )


class _MediaShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.gallery_saved = []
        self.audio_saved = []
        self.video_saved = []
        self.deleted = []

    def save_gallery_image(self, image):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.gallery_saved.append(image.model_copy(deep=True))

    def save_audio_item(self, audio):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.audio_saved.append(audio.model_copy(deep=True))

    def save_video_item(self, video):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.video_saved.append(video.model_copy(deep=True))

    def mark_deleted(self, asset_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append(asset_id)


class _TextShadowRepository:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def save(self, item):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.saved.append(item.model_copy(deep=True))

    def mark_deleted(self, item_id):
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.deleted.append(item_id)


def _enable_dual_write(monkeypatch, *, strict=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_DUAL_WRITE_DOMAINS", "media_metadata")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_RECONCILE_STRICT", "true" if strict else "false")


def _patch_shadow_repositories(monkeypatch, media_shadow, text_shadow, seen_user_ids=None):
    if seen_user_ids is None:
        seen_user_ids = []

    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_media_asset_shadow_repository",
        lambda user_id: seen_user_ids.append(("media", user_id)) or media_shadow,
    )
    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_text_item_shadow_repository",
        lambda user_id: seen_user_ids.append(("text", user_id)) or text_shadow,
    )
    return seen_user_ids


def test_media_metadata_dual_write_is_disabled_by_default(tmp_path, monkeypatch):
    media_shadow = _MediaShadowRepository()
    text_shadow = _TextShadowRepository()
    _patch_shadow_repositories(monkeypatch, media_shadow, text_shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_audio_item(_audio_item())
    storage.save_video_item(_video_item())
    storage.save_text_item(_text_item())
    storage.delete_gallery_image("image-1")
    storage.delete_audio_item("audio-1")
    storage.delete_video_item("video-1")
    storage.delete_text_item("text-1")

    assert media_shadow.gallery_saved == []
    assert media_shadow.audio_saved == []
    assert media_shadow.video_saved == []
    assert media_shadow.deleted == []
    assert text_shadow.saved == []
    assert text_shadow.deleted == []


def test_media_metadata_dual_write_saves_and_marks_deleted_when_enabled(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    media_shadow = _MediaShadowRepository()
    text_shadow = _TextShadowRepository()
    seen_user_ids = _patch_shadow_repositories(monkeypatch, media_shadow, text_shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_audio_item(_audio_item())
    storage.save_video_item(_video_item())
    storage.save_text_item(_text_item())
    storage.delete_gallery_image("image-1")
    storage.delete_audio_item("audio-1")
    storage.delete_video_item("video-1")
    storage.delete_text_item("text-1")

    assert seen_user_ids == [
        ("media", "user-1"),
        ("media", "user-1"),
        ("media", "user-1"),
        ("text", "user-1"),
        ("media", "user-1"),
        ("media", "user-1"),
        ("media", "user-1"),
        ("text", "user-1"),
    ]
    assert [image.id for image in media_shadow.gallery_saved] == ["image-1"]
    assert [audio.id for audio in media_shadow.audio_saved] == ["audio-1"]
    assert [video.id for video in media_shadow.video_saved] == ["video-1"]
    assert [text.id for text in text_shadow.saved] == ["text-1"]
    assert media_shadow.deleted == ["image-1", "audio-1", "video-1"]
    assert text_shadow.deleted == ["text-1"]
    assert storage.get_gallery_image("image-1") is None
    assert storage.get_audio_item("audio-1") is None
    assert storage.get_video_item("video-1") is None
    assert storage.get_text_item("text-1") is None


def test_media_metadata_shadow_failure_does_not_break_json_primary(tmp_path, monkeypatch):
    _enable_dual_write(monkeypatch)
    media_shadow = _MediaShadowRepository(fail=True)
    text_shadow = _TextShadowRepository(fail=True)
    _patch_shadow_repositories(monkeypatch, media_shadow, text_shadow)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_text_item(_text_item())

    assert storage.get_gallery_image("image-1") is not None
    assert storage.get_text_item("text-1") is not None
