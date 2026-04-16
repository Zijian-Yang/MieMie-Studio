from types import SimpleNamespace

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
