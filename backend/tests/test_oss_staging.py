from types import SimpleNamespace

import pytest

from app.config import OSSConfig
from app.services.oss import OSSService, _StagedFile


def _enabled_config():
    return OSSConfig(
        enabled=True,
        access_key_id="ak",
        access_key_secret="sk",
        bucket_name="bucket",
        endpoint="https://oss-cn-beijing.aliyuncs.com",
        prefix="aistudio/",
    )


def test_upload_from_url_skips_local_staging_when_oss_disabled(monkeypatch):
    service = OSSService()
    monkeypatch.setattr(service, "is_enabled", lambda: False)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("OSS 未启用时不应下载到本地暂存")

    monkeypatch.setattr(service, "_download_url_to_staging_sync", fail_if_called)

    success, result = service.upload_from_url("https://dashscope-result.example.com/tmp/a.png")

    assert success is True
    assert result == "https://dashscope-result.example.com/tmp/a.png"


def test_upload_from_url_cleans_staging_after_oss_success(tmp_path, monkeypatch):
    service = OSSService()
    staged_path = tmp_path / "staged.png"
    staged_path.write_bytes(b"image-bytes")

    class FakeBucket:
        def put_object(self, object_key, data):
            assert object_key.startswith("aistudio/image/project-1/")
            assert staged_path.exists()
            assert data.read() == b"image-bytes"
            return SimpleNamespace(status=200)

    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "_get_config", _enabled_config)
    monkeypatch.setattr(service, "_init_client", lambda: (True, FakeBucket()))
    monkeypatch.setattr(
        service,
        "_download_url_to_staging_sync",
        lambda *_args, **_kwargs: (
            True,
            _StagedFile(
                path=staged_path,
                local_url="/assets/oss_staging/image/project-1/staged.png",
                extension="png",
            ),
        ),
    )

    success, result = service.upload_from_url(
        "https://dashscope-result.example.com/tmp/a.png",
        "image",
        "png",
        "project-1",
    )

    assert success is True
    assert result.startswith("https://bucket.oss-cn-beijing.aliyuncs.com/aistudio/image/project-1/")
    assert not staged_path.exists()


def test_upload_from_url_keeps_staging_when_oss_upload_fails(tmp_path, monkeypatch):
    service = OSSService()
    staged_path = tmp_path / "staged.png"
    staged_path.write_bytes(b"image-bytes")

    class FakeBucket:
        def put_object(self, object_key, data):
            assert object_key.startswith("aistudio/image/project-1/")
            assert staged_path.exists()
            return SimpleNamespace(status=500)

    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "_get_config", _enabled_config)
    monkeypatch.setattr(service, "_init_client", lambda: (True, FakeBucket()))
    monkeypatch.setattr(
        service,
        "_download_url_to_staging_sync",
        lambda *_args, **_kwargs: (
            True,
            _StagedFile(
                path=staged_path,
                local_url="/assets/oss_staging/image/project-1/staged.png",
                extension="png",
            ),
        ),
    )

    success, result = service.upload_from_url(
        "https://dashscope-result.example.com/tmp/a.png",
        "image",
        "png",
        "project-1",
    )

    assert success is False
    assert "本地暂存: /assets/oss_staging/image/project-1/staged.png" in result
    assert staged_path.exists()


@pytest.mark.asyncio
async def test_persist_generated_image_with_fallback_cleans_staging_after_retry_success(tmp_path, monkeypatch):
    service = OSSService()
    staged_path = tmp_path / "staged.png"
    staged_path.write_bytes(b"image-bytes")

    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "should_persist_generated_url", lambda _url: True)
    monkeypatch.setattr(
        service,
        "_download_url_to_staging_sync",
        lambda *_args, **_kwargs: (
            True,
            _StagedFile(
                path=staged_path,
                local_url="/assets/oss_staging/image/project-1/staged.png",
                extension="png",
            ),
        ),
    )

    attempts = {"count": 0}

    def fake_upload(_staged_file, _file_type="image", _project_id=""):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return False, "上传失败: timeout"
        return True, "https://bucket.oss-cn-beijing.aliyuncs.com/aistudio/image/project-1/final.png"

    monkeypatch.setattr(service, "_upload_staged_file_sync", fake_upload)

    result = await service.persist_generated_image_with_fallback_async(
        "https://dashscope-result.example.com/tmp/a.png",
        "project-1",
        max_retries=3,
    )

    assert result.storage_source == "oss"
    assert result.url.endswith("/final.png")
    assert result.warning is None
    assert attempts["count"] == 3
    assert not staged_path.exists()


@pytest.mark.asyncio
async def test_persist_generated_image_with_fallback_returns_local_url_after_retry_exhaustion(tmp_path, monkeypatch):
    service = OSSService()
    staged_path = tmp_path / "staged.png"
    staged_path.write_bytes(b"image-bytes")

    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "should_persist_generated_url", lambda _url: True)
    monkeypatch.setattr(
        service,
        "_download_url_to_staging_sync",
        lambda *_args, **_kwargs: (
            True,
            _StagedFile(
                path=staged_path,
                local_url="/assets/oss_staging/image/project-1/staged.png",
                extension="png",
            ),
        ),
    )
    monkeypatch.setattr(
        service,
        "_upload_staged_file_sync",
        lambda _staged_file, _file_type="image", _project_id="": (False, "上传失败: timeout"),
    )

    result = await service.persist_generated_image_with_fallback_async(
        "https://dashscope-result.example.com/tmp/a.png",
        "project-1",
        max_retries=3,
    )

    assert result.storage_source == "local_fallback"
    assert result.url == "/assets/oss_staging/image/project-1/staged.png"
    assert "暂时回落到本地文件" in (result.warning or "")
    assert staged_path.exists()


@pytest.mark.asyncio
async def test_persist_generated_image_with_fallback_cleans_staging_on_non_retryable_failure(tmp_path, monkeypatch):
    service = OSSService()
    staged_path = tmp_path / "staged.png"
    staged_path.write_bytes(b"image-bytes")

    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(service, "should_persist_generated_url", lambda _url: True)
    monkeypatch.setattr(
        service,
        "_download_url_to_staging_sync",
        lambda *_args, **_kwargs: (
            True,
            _StagedFile(
                path=staged_path,
                local_url="/assets/oss_staging/image/project-1/staged.png",
                extension="png",
            ),
        ),
    )
    monkeypatch.setattr(
        service,
        "_upload_staged_file_sync",
        lambda _staged_file, _file_type="image", _project_id="": (False, "上传失败: HTTP 403"),
    )

    with pytest.raises(RuntimeError, match="HTTP 403"):
        await service.persist_generated_image_with_fallback_async(
            "https://dashscope-result.example.com/tmp/a.png",
            "project-1",
            max_retries=2,
        )

    assert not staged_path.exists()


@pytest.mark.asyncio
async def test_retry_local_fallback_image_to_oss_async_cleans_file_after_success(tmp_path, monkeypatch):
    service = OSSService()
    assets_dir = tmp_path / "assets"
    staged_path = assets_dir / "oss_staging" / "image" / "project-1" / "staged.png"
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(b"image-bytes")

    monkeypatch.setattr(service, "_assets_dir", lambda: assets_dir)
    monkeypatch.setattr(service, "is_enabled", lambda: True)
    monkeypatch.setattr(
        service,
        "_upload_staged_file_sync",
        lambda _staged_file, _file_type="image", _project_id="": (True, "https://bucket.oss-cn-beijing.aliyuncs.com/aistudio/image/project-1/final.png"),
    )

    result = await service.retry_local_fallback_image_to_oss_async(
        "/assets/oss_staging/image/project-1/staged.png",
        "project-1",
    )

    assert result.storage_source == "oss"
    assert result.url.endswith("/final.png")
    assert not staged_path.exists()


@pytest.mark.asyncio
async def test_retry_local_fallback_image_to_oss_async_marks_missing_file_expired(tmp_path, monkeypatch):
    service = OSSService()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(service, "_assets_dir", lambda: assets_dir)
    monkeypatch.setattr(service, "is_enabled", lambda: True)

    result = await service.retry_local_fallback_image_to_oss_async(
        "/assets/oss_staging/image/project-1/missing.png",
        "project-1",
    )

    assert result.storage_source == "local_expired"
    assert result.retryable is False
    assert "不存在" in (result.error or "")
