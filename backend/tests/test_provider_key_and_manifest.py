import json
from pathlib import Path

import pytest

from app.config import (
    config_manager,
    get_provider_api_key,
    get_provider_key_profile,
    set_provider_key_profile_override,
    set_user_config_dir,
)
from app.services.user_service import get_user_service
from app.services.video_adapters import DashScopeGenericVideoService
from app.services.video_model_testing import generate_model_test_manifest


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_settings_support_dual_api_keys_and_provider_profiles(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={
            "test_api_key": "test-key-12345678",
            "production_api_key": "prod-key-87654321",
            "wan_key_profile": "test",
            "happyhorse_key_profile": "production",
            "kling_key_profile": "production",
            "vidu_key_profile": "test",
        },
    )
    assert resp.status_code == 200

    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()
    assert data["is_test_api_key_set"] is True
    assert data["is_production_api_key_set"] is True
    assert data["wan_key_profile"] == "test"
    assert data["happyhorse_key_profile"] == "production"
    assert data["kling_key_profile"] == "production"
    assert data["vidu_key_profile"] == "test"
    assert data["api_key_masked"]
    assert data["production_api_key_masked"]


def test_settings_supports_independent_volcengine_api_key(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={
            "test_api_key": "dashscope-test-key",
            "production_api_key": "dashscope-prod-key",
            "volcengine_api_key": "volc-ak-12345678",
        },
    )
    assert resp.status_code == 200

    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()
    assert data["is_volcengine_api_key_set"] is True
    assert data["volcengine_api_key_masked"] == "volc********5678"


def test_settings_supports_independent_google_api_key(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={
            "test_api_key": "dashscope-test-key",
            "production_api_key": "dashscope-prod-key",
            "google_api_key": "goog-ak-12345678",
        },
    )
    assert resp.status_code == 200

    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()
    assert data["is_google_api_key_set"] is True
    assert data["google_api_key_masked"] == "goog********5678"


def test_blank_volcengine_key_update_keeps_existing_key(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={"volcengine_api_key": "volc-ak-keep-12345678"},
    )
    assert resp.status_code == 200

    blank_resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={"volcengine_api_key": "   "},
    )
    assert blank_resp.status_code == 200

    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()
    assert data["is_volcengine_api_key_set"] is True
    assert data["volcengine_api_key_masked"] == "volc*************5678"


def test_blank_google_key_update_keeps_existing_key(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={"google_api_key": "goog-ak-keep-12345678"},
    )
    assert resp.status_code == 200

    blank_resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={"google_api_key": "   "},
    )
    assert blank_resp.status_code == 200

    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()
    assert data["is_google_api_key_set"] is True
    assert data["google_api_key_masked"] == "goog*************5678"


def test_settings_persists_happyhorse_test_profile_after_refresh(client, auth_header):
    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={
            "test_api_key": "test-key-12345678",
            "production_api_key": "prod-key-87654321",
            "wan_key_profile": "production",
            "happyhorse_key_profile": "test",
            "kling_key_profile": "test",
            "vidu_key_profile": "production",
        },
    )
    assert resp.status_code == 200

    first_read = client.get("/api/settings", headers=auth_header)
    second_read = client.get("/api/settings", headers=auth_header)

    assert first_read.status_code == 200
    assert second_read.status_code == 200
    assert first_read.json()["happyhorse_key_profile"] == "test"
    assert second_read.json()["happyhorse_key_profile"] == "test"
    assert second_read.json()["wan_key_profile"] == "production"
    assert second_read.json()["kling_key_profile"] == "test"
    assert second_read.json()["vidu_key_profile"] == "production"


def test_settings_exposes_us_virginia_region(client, auth_header):
    settings = client.get("/api/settings", headers=auth_header)
    assert settings.status_code == 200
    data = settings.json()

    assert data["available_regions"]["us_virginia"] == {
        "name": "美国（弗吉尼亚）",
        "base_url": "https://dashscope-us.aliyuncs.com/api/v1",
    }

    resp = client.put(
        "/api/settings",
        headers=auth_header,
        json={"api_region": "us_virginia"},
    )
    assert resp.status_code == 200

    updated = client.get("/api/settings", headers=auth_header)
    assert updated.status_code == 200
    assert updated.json()["api_region"] == "us_virginia"
    assert updated.json()["base_url"] == "https://dashscope-us.aliyuncs.com/api/v1"


def test_get_provider_api_key_respects_profiles(registered_user):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        dashscope_api_key="legacy-prod-key",
        production_api_key="prod-key",
        test_api_key="test-key",
        wan_key_profile="test",
        happyhorse_key_profile="production",
        kling_key_profile="production",
        vidu_key_profile="test",
    )

    assert get_provider_key_profile("wan") == "test"
    assert get_provider_key_profile("happyhorse") == "production"
    assert get_provider_key_profile("kling") == "production"
    assert get_provider_key_profile("vidu") == "test"
    assert get_provider_api_key("wan") == "test-key"
    assert get_provider_api_key("happyhorse") == "prod-key"
    assert get_provider_api_key("kling") == "prod-key"
    assert get_provider_api_key("vidu") == "test-key"


def test_get_provider_api_key_returns_independent_volcengine_key(registered_user):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        production_api_key="dashscope-prod-key",
        test_api_key="dashscope-test-key",
        volcengine_api_key="volc-ak-independent",
        wan_key_profile="test",
    )

    assert get_provider_api_key("wan") == "dashscope-test-key"
    assert get_provider_api_key("volcengine") == "volc-ak-independent"


def test_get_provider_api_key_returns_independent_google_key(registered_user):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        production_api_key="dashscope-prod-key",
        test_api_key="dashscope-test-key",
        google_api_key="goog-ak-independent",
        wan_key_profile="test",
    )

    assert get_provider_api_key("wan") == "dashscope-test-key"
    assert get_provider_api_key("google") == "goog-ak-independent"


def test_provider_profile_override_supports_happyhorse_independently(registered_user):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        production_api_key="prod-key",
        test_api_key="test-key",
        wan_key_profile="production",
        happyhorse_key_profile="production",
    )

    set_provider_key_profile_override({"wan": "test", "happyhorse": "production"})
    try:
        assert get_provider_key_profile("wan") == "test"
        assert get_provider_key_profile("happyhorse") == "production"
        assert get_provider_api_key("wan") == "test-key"
        assert get_provider_api_key("happyhorse") == "prod-key"
    finally:
        set_provider_key_profile_override(None)


def test_happyhorse_generic_service_uses_its_configured_key_profile(registered_user):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        production_api_key="prod-key",
        test_api_key="test-key",
        wan_key_profile="test",
        happyhorse_key_profile="production",
    )

    service = DashScopeGenericVideoService("happyhorse")

    assert service.key_profile == "production"
    assert service.api_key == "prod-key"


@pytest.mark.asyncio
async def test_generate_model_test_manifest_prefers_persistent_oss_assets(registered_user, monkeypatch):
    _, user = registered_user
    user_dir = get_user_service().get_user_data_path(user["id"])
    set_user_config_dir(str(user_dir))
    config_manager.update(
        production_api_key="prod-key",
        test_api_key="test-key",
        oss={
            "enabled": True,
            "bucket_name": "demo-bucket",
            "endpoint": "https://oss-cn-beijing.aliyuncs.com",
            "prefix": "aistudio/",
        },
    )

    persistent_base = "https://demo-bucket.oss-cn-beijing.aliyuncs.com/aistudio"
    temp_base = "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp"

    _write_json(
        user_dir / "gallery" / "img1.json",
        {"id": "img1", "project_id": "p1", "name": "首帧", "url": f"{persistent_base}/image/first.png"},
    )
    _write_json(
        user_dir / "gallery" / "temp.json",
        {"id": "temp", "project_id": "p1", "name": "临时图", "url": f"{temp_base}/temp.png"},
    )
    _write_json(
        user_dir / "video_library" / "video1.json",
        {"id": "video1", "project_id": "p1", "name": "视频", "url": f"{persistent_base}/video/base.mp4"},
    )
    _write_json(
        user_dir / "audio" / "audio1.json",
        {"id": "audio1", "project_id": "p1", "name": "音频", "url": f"{persistent_base}/audio/driver.mp3"},
    )
    _write_json(
        user_dir / "video_studio" / "task1.json",
        {
            "id": "task1",
            "project_id": "p1",
            "name": "局部编辑素材",
            "first_frame_url": f"{persistent_base}/image/first.png",
            "last_frame_url": f"{persistent_base}/image/last.png",
            "reference_video_urls": [f"{persistent_base}/video/ref.mp4"],
            "source_video_url": f"{persistent_base}/video/source.mp4",
            "mask_image_url": f"{persistent_base}/image/mask.png",
            "reference_image_url": f"{persistent_base}/image/ref.png",
            "audio_url": f"{persistent_base}/audio/driver.mp3",
        },
    )

    async def fake_validate_image(url: str):
        return {"url": url, "width": 1280, "height": 720, "format": "PNG", "file_size": 1234}

    async def fake_validate_video(url: str):
        return {
            "url": url,
            "width": 1280,
            "height": 720,
            "fps": 24.0,
            "duration": 4.0,
            "frame_count": 96,
            "file_size": 2048,
            "format": "mp4",
            "warnings": [],
        }

    async def fake_validate_audio(url: str):
        return {"url": url, "duration": 3.2, "file_size": 512, "format": "mp3"}

    async def fake_validate_mask(self, mask_image_url: str, expected_width: int, expected_height: int):
        return {"width": expected_width, "height": expected_height}

    monkeypatch.setattr("app.services.video_model_testing._validate_image_url", fake_validate_image)
    monkeypatch.setattr("app.services.video_model_testing._validate_video_url", fake_validate_video)
    monkeypatch.setattr("app.services.video_model_testing._validate_audio_url", fake_validate_audio)
    monkeypatch.setattr(
        "app.services.video_model_testing.VaceVideoEditService.validate_mask_image",
        fake_validate_mask,
    )

    manifest = await generate_model_test_manifest(user["id"], refresh=True)
    assert manifest["roles"]["first_frame_image"]["url"].startswith(persistent_base)
    assert manifest["roles"]["driver_audio"]["url"].startswith(persistent_base)
    assert manifest["roles"]["local_edit_mask_image"]["url"] == f"{persistent_base}/image/mask.png"
    assert all("dashscope-result" not in item["url"] for item in manifest["roles"]["reference_images"])
