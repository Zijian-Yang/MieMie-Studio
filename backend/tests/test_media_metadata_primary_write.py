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
        created_at=datetime(2026, 6, 7, 17, 0, 0),
        updated_at=datetime(2026, 6, 7, 17, 1, 0),
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
        created_at=datetime(2026, 6, 7, 17, 2, 0),
        updated_at=datetime(2026, 6, 7, 17, 3, 0),
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
        created_at=datetime(2026, 6, 7, 17, 4, 0),
        updated_at=datetime(2026, 6, 7, 17, 5, 0),
    )


def _text_item(text_id: str = "text-1") -> TextItem:
    return TextItem(
        id=text_id,
        project_id="project-1",
        name="text",
        content="content",
        category="prompt",
        created_at=datetime(2026, 6, 7, 17, 6, 0),
        updated_at=datetime(2026, 6, 7, 17, 7, 0),
    )


class _PrimaryMediaRepository:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.gallery_saved = []
        self.audio_saved = []
        self.video_saved = []
        self.deleted = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres media primary unavailable")

    def save_gallery_image(self, image):
        self._maybe_fail()
        self.gallery_saved.append(image.model_copy(deep=True))

    def save_audio_item(self, audio):
        self._maybe_fail()
        self.audio_saved.append(audio.model_copy(deep=True))

    def save_video_item(self, video):
        self._maybe_fail()
        self.video_saved.append(video.model_copy(deep=True))

    def mark_deleted(self, asset_id):
        self._maybe_fail()
        self.deleted.append(asset_id)


class _PrimaryTextRepository:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.saved = []
        self.deleted = []

    def _maybe_fail(self):
        if self.fail:
            raise RuntimeError("postgres text primary unavailable")

    def save(self, item):
        self._maybe_fail()
        self.saved.append(item.model_copy(deep=True))

    def mark_deleted(self, item_id):
        self._maybe_fail()
        self.deleted.append(item_id)


def _enable_primary_write(monkeypatch, *, archive=False):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS", "media_metadata")
    monkeypatch.setenv("MIEMIE_DATABASE_JSON_ARCHIVE_WRITES", "true" if archive else "false")


def _patch_primary_repositories(monkeypatch, media_repo, text_repo):
    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_media_asset_primary_repository",
        lambda user_id: media_repo,
    )
    monkeypatch.setattr(
        "app.repositories.media_asset_runtime.build_text_item_primary_repository",
        lambda user_id: text_repo,
    )


def test_media_metadata_primary_write_is_disabled_by_default(tmp_path, monkeypatch):
    media_repo = _PrimaryMediaRepository()
    text_repo = _PrimaryTextRepository()
    _patch_primary_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_text_item(_text_item())

    assert media_repo.gallery_saved == []
    assert text_repo.saved == []
    assert storage.get_gallery_image("image-1") is not None
    assert storage.get_text_item("text-1") is not None


def test_media_metadata_primary_write_saves_postgres_without_json_archive(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=False)
    media_repo = _PrimaryMediaRepository()
    text_repo = _PrimaryTextRepository()
    _patch_primary_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_audio_item(_audio_item())
    storage.save_video_item(_video_item())
    storage.save_text_item(_text_item())
    storage.delete_gallery_image("image-1")
    storage.delete_audio_item("audio-1")
    storage.delete_video_item("video-1")
    storage.delete_text_item("text-1")

    assert [image.id for image in media_repo.gallery_saved] == ["image-1"]
    assert media_repo.gallery_saved[0].updated_at != datetime(2026, 6, 7, 17, 1, 0)
    assert [audio.id for audio in media_repo.audio_saved] == ["audio-1"]
    assert [video.id for video in media_repo.video_saved] == ["video-1"]
    assert [item.id for item in text_repo.saved] == ["text-1"]
    assert media_repo.deleted == ["image-1", "audio-1", "video-1"]
    assert text_repo.deleted == ["text-1"]
    assert storage._get_gallery_image_from_file("image-1") is None
    assert storage._get_audio_item_from_file("audio-1") is None
    assert storage._get_video_item_from_file("video-1") is None
    assert storage._get_text_item_from_file("text-1") is None


def test_media_metadata_primary_write_can_keep_json_archive_mirror(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    media_repo = _PrimaryMediaRepository()
    text_repo = _PrimaryTextRepository()
    _patch_primary_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    storage.save_gallery_image(_gallery_image())
    storage.save_text_item(_text_item())
    assert storage._get_gallery_image_from_file("image-1") is not None
    assert storage._get_text_item_from_file("text-1") is not None

    storage.delete_gallery_image("image-1")
    storage.delete_text_item("text-1")

    assert media_repo.deleted == ["image-1"]
    assert text_repo.deleted == ["text-1"]
    assert storage._get_gallery_image_from_file("image-1") is None
    assert storage._get_text_item_from_file("text-1") is None


def test_media_metadata_primary_write_failure_does_not_write_json(tmp_path, monkeypatch):
    _enable_primary_write(monkeypatch, archive=True)
    media_repo = _PrimaryMediaRepository(fail=True)
    text_repo = _PrimaryTextRepository(fail=True)
    _patch_primary_repositories(monkeypatch, media_repo, text_repo)
    storage = StorageService(str(tmp_path), owner_user_id="user-1")

    try:
        storage.save_gallery_image(_gallery_image())
    except RuntimeError as exc:
        assert "postgres media primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    try:
        storage.save_text_item(_text_item())
    except RuntimeError as exc:
        assert "postgres text primary unavailable" in str(exc)
    else:
        raise AssertionError("PostgreSQL primary write failures should propagate")

    assert storage._get_gallery_image_from_file("image-1") is None
    assert storage._get_text_item_from_file("text-1") is None
