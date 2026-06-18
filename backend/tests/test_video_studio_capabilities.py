import asyncio
import pytest
from datetime import datetime, timedelta

from app.models.media import VideoStudioTask
from app.routers import video_studio as video_studio_router
from app.services.video_adapters import (
    DashScopeGenericVideoService,
    KlingVideoAdapter,
    NormalizedVideoTaskRequest,
    VideoProviderError,
    WanVideoAdapter,
    ViduVideoAdapter,
    get_video_adapter,
    infer_provider,
)
from app.services.video_capabilities import get_video_capabilities
from app.services.storage import set_current_user, storage_service


DATA_INSPECTION_DISABLED_HEADER = '{"input":"disable","output":"disable"}'


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "能力测试项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(video_studio_router.asyncio, "create_task", fake_create_task)


class FakeInflightLease:
    acquired = True

    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


def _clear_video_studio_inflight_leases():
    for lease in list(video_studio_router._video_studio_inflight_leases.values()):
        lease.release()
    video_studio_router._video_studio_inflight_leases.clear()
    video_studio_router._video_studio_inflight_task_ids.clear()
    for background_task in list(video_studio_router._video_studio_background_tasks.values()):
        if not background_task.done():
            background_task.cancel()
    video_studio_router._video_studio_background_tasks.clear()


def test_get_capabilities_endpoint_returns_multi_provider_schema(client, auth_header):
    resp = client.get("/api/video-studio/capabilities", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    task_kind_ids = {item["id"] for item in data["task_kinds"]}
    assert {"text_to_video", "video_edit_global", "video_edit_local", "video_repainting", "video_extension"} <= task_kind_ids

    models = data["models"]
    assert "kling/kling-v3-video-generation" in models
    assert "kling/kling-v3-omni-video-generation" in models
    assert "vidu/viduq3-turbo_text2video" in models
    assert "wanx2.1-vace-plus" in models
    assert "wan2.7-t2v" in models
    assert "wan2.7-r2v" in models
    assert "wan2.7-i2v" in models
    assert "wan2.7-i2v-2026-04-25" in models
    assert "wan2.7-videoedit" in models
    assert data["legacy_task_kind_map"]["video_edit"] == "video_edit_local"
    task_kind_defaults = {item["id"]: item["default_model_id"] for item in data["task_kinds"]}
    assert task_kind_defaults["text_to_video"] == "wan2.7-t2v"
    assert task_kind_defaults["reference_to_video"] == "wan2.7-r2v"
    assert task_kind_defaults["video_extension"] == "wan2.7-i2v"
    kling_edit_params = {
        item["name"]
        for item in models["kling/kling-v3-omni-video-generation"]["task_profiles"]["video_edit_global"]["parameters"]
    }
    assert {"audio", "keep_original_sound", "element_ids"} <= kling_edit_params
    wan27_text_params = {
        item["name"]
        for item in models["wan2.7-t2v"]["task_profiles"]["text_to_video"]["parameters"]
    }
    assert {"resolution", "ratio", "duration"} <= wan27_text_params
    assert "shot_type" not in wan27_text_params
    wan27_reference_profile = models["wan2.7-r2v"]["task_profiles"]["reference_to_video"]
    assert "first_frame" in wan27_reference_profile["input_roles"]
    assert wan27_reference_profile["ui_hints"]["supports_reference_voice"] is True
    wan27_extension_profile = models["wan2.7-i2v"]["task_profiles"]["video_extension"]
    assert "first_clip" in wan27_extension_profile["input_roles"]
    wan27_snapshot_profile = models["wan2.7-i2v-2026-04-25"]["task_profiles"]["video_extension"]
    assert "first_clip" in wan27_snapshot_profile["input_roles"]
    wan27_videoedit_params = {
        item["name"]
        for item in models["wan2.7-videoedit"]["task_profiles"]["video_edit_global"]["parameters"]
    }
    assert {"ratio", "audio_setting"} <= wan27_videoedit_params


def test_video_capabilities_expose_async_rate_limits_and_shared_pools(client, auth_header):
    resp = client.get("/api/video-studio/capabilities", headers=auth_header)
    assert resp.status_code == 200
    models = resp.json()["models"]

    wan = models["wan2.7-i2v"]["capabilities"]
    assert wan["api_mode"] == "async"
    assert wan["submit_rate_limit"] == {"count": 5, "period_seconds": 1}
    assert wan["max_concurrent"] == 5
    assert wan["concurrency_scope"] == "model"

    snapshot = models["wan2.7-i2v-2026-04-25"]["capabilities"]
    assert snapshot["max_concurrent"] == 5

    kling = models["kling/kling-v3-video-generation"]["capabilities"]
    assert kling["api_mode"] == "async"
    assert kling["max_concurrent"] == 10
    assert kling["concurrency_scope"] == "shared_pool"
    assert kling["concurrency_pool_id"] == "aliyun:kling:video-image"

    vidu = models["vidu/viduq3-turbo_img2video"]["capabilities"]
    assert vidu["api_mode"] == "async"
    assert vidu["max_concurrent"] == 5
    assert vidu["concurrency_scope"] == "shared_pool"
    assert vidu["concurrency_pool_id"] == "aliyun:vidu:video"


def test_video_capability_schema_exposes_structured_help_content():
    capabilities = get_video_capabilities()
    models = capabilities["models"]

    kling_text_profile = models["kling/kling-v3-omni-video-generation"]["task_profiles"]["text_to_video"]
    narrative_param = next(param for param in kling_text_profile["parameters"] if param["name"] == "narrative_mode")
    assert narrative_param["help"]["summary"]
    assert kling_text_profile["ui_hints"]["prompt_help"]["summary"]

    vidu_profile = models["vidu/viduq3-turbo_text2video"]["task_profiles"]["text_to_video"]
    resolution_param = next(param for param in vidu_profile["parameters"] if param["name"] == "resolution")
    assert resolution_param["help"]["summary"]
    assert resolution_param["help"]["how_to_choose"]

    wan_vace_profile = models["wanx2.1-vace-plus"]["task_profiles"]["video_edit_local"]
    mask_type_param = next(param for param in wan_vace_profile["parameters"] if param["name"] == "mask_type")
    assert mask_type_param["help"]["summary"]
    assert mask_type_param["help"]["examples"]
    assert wan_vace_profile["ui_hints"]["asset_help"]["mask_image"]["limits"]

    wan27_extension_profile = models["wan2.7-i2v"]["task_profiles"]["video_extension"]
    assert wan27_extension_profile["ui_hints"]["asset_help"]["first_clip"]["limits"]
    assert wan27_extension_profile["ui_hints"]["prompt_help"]["notes"]

    wan27_text_profile = models["wan2.7-t2v"]["task_profiles"]["text_to_video"]
    ratio_param = next(param for param in wan27_text_profile["parameters"] if param["name"] == "ratio")
    assert ratio_param["help"]["summary"]
    assert ratio_param["constraint"]["options"]

    wan27_reference_profile = models["wan2.7-r2v"]["task_profiles"]["reference_to_video"]
    assert wan27_reference_profile["ui_hints"]["prompt_help"]["notes"]
    assert wan27_reference_profile["ui_hints"]["asset_help"]["audio"]["limits"]

    wan27_videoedit_profile = models["wan2.7-videoedit"]["task_profiles"]["video_edit_global"]
    ratio_param = next(param for param in wan27_videoedit_profile["parameters"] if param["name"] == "ratio")
    assert ratio_param["help"]["summary"]
    assert ratio_param["constraint"]["options"]


def test_video_capability_schema_exposes_reference_token_policies():
    capabilities = get_video_capabilities()
    models = capabilities["models"]

    wan26_profile = models["wan2.6-r2v-flash"]["task_profiles"]["reference_to_video"]
    assert wan26_profile["ui_hints"]["reference_token_policy"] == {
        "mode": "media_reference_tokens",
        "index_base": 1,
        "numbering_scope": "combined",
        "reference_order": ["reference_video", "reference_image"],
        "tokens": {
            "reference_image": {"template": "character{index}"},
            "reference_video": {"template": "character{index}"},
        },
    }

    wan27_profile = models["wan2.7-r2v"]["task_profiles"]["reference_to_video"]
    assert wan27_profile["ui_hints"]["reference_token_policy"] == {
        "mode": "media_reference_tokens",
        "index_base": 1,
        "numbering_scope": "by_type",
        "tokens": {
            "reference_image": {
                "template": "图{index}",
                "variants": [{"key": "en", "label": "Image {index}", "template": "Image {index}"}],
            },
            "reference_video": {
                "template": "视频{index}",
                "variants": [{"key": "en", "label": "Video {index}", "template": "Video {index}"}],
            },
        },
    }

    happyhorse_profile = models["happyhorse-1.0-r2v"]["task_profiles"]["reference_to_video"]
    assert happyhorse_profile["ui_hints"]["reference_token_policy"] == {
        "mode": "media_reference_tokens",
        "index_base": 1,
        "numbering_scope": "by_type",
        "tokens": {
            "reference_image": {"template": "[Image {index}]"},
        },
    }

    kling_reference_profile = models["kling/kling-v3-omni-video-generation"]["task_profiles"]["reference_to_video"]
    assert kling_reference_profile["ui_hints"]["reference_token_policy"]["tokens"] == {
        "reference_image": {"template": "<<<image_{index}>>>"},
        "reference_video": {"template": "<<<video_{index}>>>"},
    }

    kling_edit_profile = models["kling/kling-v3-omni-video-generation"]["task_profiles"]["video_edit_global"]
    assert kling_edit_profile["ui_hints"]["reference_token_policy"]["tokens"]["reference_image"] == {
        "template": "<<<image_{index}>>>"
    }

    vidu_profile = models["vidu/viduq2-pro_reference2video"]["task_profiles"]["reference_to_video"]
    assert vidu_profile["ui_hints"]["reference_token_policy"]["tokens"] == {
        "reference_image": {"template": "图{index}"},
        "reference_video": {"template": "视频{index}"},
    }


def test_create_task_with_canonical_kling_fields(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    _patch_async_create_task(monkeypatch)

    resp = client.post(
        "/api/video-studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_video",
            "provider": "kling",
            "model_id": "kling/kling-v3-omni-video-generation",
            "model": "kling/kling-v3-omni-video-generation",
            "narrative_mode": "multi_shot_intelligence",
            "prompt": "机械臂在工厂车间中打开柜门，镜头推进",
            "input_assets": {},
            "normalized_params": {
                "mode": "std",
                "aspect_ratio": "16:9",
                "duration": 5,
                "audio": False,
                "watermark": True,
            },
            "group_count": 2,
        },
    )
    assert resp.status_code == 200

    task = resp.json()["task"]
    assert task["task_type"] == "text_to_video"
    assert task["task_kind"] == "text_to_video"
    assert task["provider"] == "kling"
    assert task["model_id"] == "kling/kling-v3-omni-video-generation"
    assert task["model"] == "kling/kling-v3-omni-video-generation"
    assert task["narrative_mode"] == "multi_shot_intelligence"
    assert task["normalized_params"]["aspect_ratio"] == "16:9"
    assert task["group_count"] == 2


def test_update_task_with_canonical_fields_persists_normalized_state(client, auth_header, registered_user):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(project_id=project_id, name="旧任务", task_type="image_to_video", status="pending")
    storage_service.save_video_studio_task(task)

    resp = client.put(
        f"/api/video-studio/{task.id}",
        headers=auth_header,
        json={
            "task_kind": "text_to_video",
            "provider": "kling",
            "model_id": "kling/kling-v3-omni-video-generation",
            "narrative_mode": "multi_shot_intelligence",
            "input_assets": {},
            "normalized_params": {
                "mode": "std",
                "aspect_ratio": "16:9",
                "duration": 5,
                "watermark": True,
            },
            "prompt": "工业机械臂巡视仓库，镜头跟随推进",
            "negative_prompt": "",
            "group_count": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_kind"] == "text_to_video"
    assert data["provider"] == "kling"
    assert data["model_id"] == "kling/kling-v3-omni-video-generation"
    assert data["model"] == "kling/kling-v3-omni-video-generation"
    assert data["normalized_params"]["aspect_ratio"] == "16:9"
    assert data["group_count"] == 2


@pytest.mark.asyncio
async def test_wan_submit_result_keeps_request_id_and_provider_payload(monkeypatch):
    adapter = WanVideoAdapter()

    async def fake_create_task(self, *args, **kwargs):
        self.last_request_id = "req-wan-submit-1"
        return "task-wan-submit-1"

    monkeypatch.setattr("app.services.video_adapters.TextToVideoService.create_task", fake_create_task)

    result = await adapter.submit(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="wan",
            model_id="wan2.6-t2v",
            prompt="机械臂打开仓库柜门",
            normalized_params={
                "size": "1920*1080",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        )
    )

    assert result.task_id == "task-wan-submit-1"
    assert result.request_id == "req-wan-submit-1"
    assert result.provider_payload is not None
    assert result.provider_payload["model"] == "wan2.6-t2v"


def test_wan27_t2v_builds_new_protocol_payload():
    adapter = WanVideoAdapter()
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="wan",
            model_id="wan2.7-t2v",
            prompt="机械臂在仓库中打开柜门并缓慢推进",
            input_assets={"audio": ["https://oss.example.com/voice.mp3"]},
            normalized_params={
                "resolution": "1080P",
                "ratio": "9:16",
                "duration": 8,
                "prompt_extend": True,
                "watermark": False,
                "seed": 123,
            },
        )
    )

    assert payload["model"] == "wan2.7-t2v"
    assert payload["input"]["audio_url"] == "https://oss.example.com/voice.mp3"
    assert payload["parameters"]["resolution"] == "1080P"
    assert payload["parameters"]["ratio"] == "9:16"
    assert "size" not in payload["parameters"]
    assert "shot_type" not in payload["parameters"]


@pytest.mark.asyncio
async def test_wan27_video_extension_requires_first_clip():
    adapter = WanVideoAdapter()

    with pytest.raises(ValueError, match="首段视频"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_extension",
                provider="wan",
                model_id="wan2.7-i2v",
                prompt="续写机械臂打开柜门后的动作",
                input_assets={},
                normalized_params={
                    "resolution": "1080P",
                    "duration": 5,
                    "prompt_extend": True,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_wan27_videoedit_rejects_more_than_three_reference_images(monkeypatch):
    adapter = WanVideoAdapter()

    async def fake_validate_video(url: str, label: str):
        return {"duration": 4.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_video", fake_validate_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)

    with pytest.raises(ValueError, match="最多支持3张参考图"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_edit_global",
                provider="wan",
                model_id="wan2.7-videoedit",
                prompt="把机械臂替换成参考图中的型号",
                input_assets={
                    "base_video": ["https://oss.example.com/base.mp4"],
                    "reference_images": [
                        "https://oss.example.com/ref1.png",
                        "https://oss.example.com/ref2.png",
                        "https://oss.example.com/ref3.png",
                        "https://oss.example.com/ref4.png",
                    ],
                },
                normalized_params={
                    "resolution": "1080P",
                    "duration": 0,
                    "audio_setting": "auto",
                    "prompt_extend": True,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_wan27_videoedit_accepts_duration_zero_and_builds_provider_payload(monkeypatch):
    adapter = WanVideoAdapter()

    async def fake_validate_video(url: str, label: str):
        return {"duration": 4.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_video", fake_validate_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)

    request = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="video_edit_global",
        provider="wan",
        model_id="wan2.7-videoedit",
        prompt="保留动作和镜头，把机械臂替换成参考图中的白色型号",
        input_assets={
            "base_video": ["https://oss.example.com/base.mp4"],
            "reference_images": ["https://oss.example.com/ref1.png", "https://oss.example.com/ref2.png"],
        },
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 0,
            "audio_setting": "origin",
            "prompt_extend": True,
            "watermark": False,
            "seed": 12,
        },
    )

    await adapter.validate(request)
    payload = adapter.build_provider_payload(request)

    assert payload["model"] == "wan2.7-videoedit"
    assert payload["parameters"]["duration"] == 0
    assert payload["parameters"]["ratio"] == "16:9"
    assert payload["parameters"]["audio_setting"] == "origin"
    assert payload["input"]["media"][0]["type"] == "video"
    assert [item["type"] for item in payload["input"]["media"][1:]] == ["reference_image", "reference_image"]


def test_wan27_i2v_builds_driving_audio_payload():
    adapter = WanVideoAdapter()
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="image_to_video",
            provider="wan",
            model_id="wan2.7-i2v",
            prompt="机械臂跟随节奏打开柜门",
            input_assets={
                "first_frame": ["https://oss.example.com/first.png"],
                "audio": ["https://oss.example.com/drive.mp3"],
            },
            normalized_params={
                "resolution": "1080P",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        )
    )

    assert payload["model"] == "wan2.7-i2v"
    assert payload["input"]["media"][0]["type"] == "first_frame"
    assert payload["input"]["media"][1]["type"] == "driving_audio"
    assert payload["parameters"]["resolution"] == "1080P"


def test_wan27_i2v_snapshot_builds_distinct_provider_payload():
    adapter = WanVideoAdapter()
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="keyframe_to_video",
            provider="wan",
            model_id="wan2.7-i2v-2026-04-25",
            prompt="从开门动作自然过渡到尾帧姿态",
            input_assets={
                "first_frame": ["https://oss.example.com/first.png"],
                "last_frame": ["https://oss.example.com/last.png"],
                "audio": ["https://oss.example.com/drive.mp3"],
            },
            normalized_params={
                "resolution": "720P",
                "duration": 10,
                "prompt_extend": False,
                "watermark": True,
                "seed": 42,
            },
        )
    )

    assert payload["model"] == "wan2.7-i2v-2026-04-25"
    assert [item["type"] for item in payload["input"]["media"]] == ["first_frame", "last_frame", "driving_audio"]
    assert payload["parameters"] == {
        "resolution": "720P",
        "duration": 10,
        "prompt_extend": False,
        "watermark": True,
        "seed": 42,
    }


def test_preview_payload_returns_wan27_provider_payload(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_video(url: str, label: str):
        return {"duration": 4.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_video", fake_validate_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "video_extension",
            "provider": "wan",
            "model_id": "wan2.7-i2v",
            "model": "wan2.7-i2v",
            "prompt": "续写机械臂打开柜门后的推进镜头",
            "input_assets": {
                "first_clip": ["https://oss.example.com/clip.mp4"],
                "last_frame": ["https://oss.example.com/last.png"],
            },
            "normalized_params": {
                "resolution": "1080P",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "video_extension"
    assert data["provider_payload"]["model"] == "wan2.7-i2v"
    media = data["provider_payload"]["input"]["media"]
    assert media[0]["type"] == "first_clip"
    assert media[1]["type"] == "last_frame"


def test_preview_payload_returns_wan27_snapshot_provider_payload(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_video(url: str, label: str):
        return {"duration": 4.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_video", fake_validate_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "video_extension",
            "provider": "wan",
            "model_id": "wan2.7-i2v-2026-04-25",
            "model": "wan2.7-i2v-2026-04-25",
            "prompt": "续写机械臂打开柜门后的推进镜头",
            "input_assets": {
                "first_clip": ["https://oss.example.com/clip.mp4"],
                "last_frame": ["https://oss.example.com/last.png"],
            },
            "normalized_params": {
                "resolution": "1080P",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["model_id"] == "wan2.7-i2v-2026-04-25"
    assert data["provider_payload"]["model"] == "wan2.7-i2v-2026-04-25"
    media = data["provider_payload"]["input"]["media"]
    assert media[0]["type"] == "first_clip"
    assert media[1]["type"] == "last_frame"


@pytest.mark.asyncio
async def test_wan27_r2v_builds_ordered_media_payload_and_ignores_ratio_with_first_frame(monkeypatch):
    adapter = WanVideoAdapter()

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    async def fake_validate_reference_video(url: str, label: str):
        return {"duration": 5.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_reference_voice(url: str, label: str):
        return {"duration": 3.0, "format": "mp3", "file_size": 1024}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_video", fake_validate_reference_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_voice", fake_validate_reference_voice)

    request = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="reference_to_video",
        provider="wan",
        model_id="wan2.7-r2v",
        prompt="视频1和图片1在咖啡馆里交流，图片2放在桌上",
        input_assets={
            "first_frame": ["https://oss.example.com/first.png"],
            "reference_media": [
                {"type": "reference_video", "url": "https://oss.example.com/actor.mp4", "reference_voice": "https://oss.example.com/actor.mp3"},
                {"type": "reference_image", "url": "https://oss.example.com/cat.png"},
                {"type": "reference_image", "url": "https://oss.example.com/cup.png", "reference_voice": "https://oss.example.com/cup.mp3"},
            ],
        },
        normalized_params={
            "resolution": "1080P",
            "ratio": "3:4",
            "duration": 8,
            "prompt_extend": True,
            "watermark": False,
        },
    )

    await adapter.validate(request)
    payload = adapter.build_provider_payload(request)

    assert payload["model"] == "wan2.7-r2v"
    assert "ratio" not in payload["parameters"]
    assert [item["type"] for item in payload["input"]["media"]] == [
        "first_frame",
        "reference_video",
        "reference_image",
        "reference_image",
    ]
    assert payload["input"]["media"][1]["reference_voice"] == "https://oss.example.com/actor.mp3"
    assert payload["input"]["media"][3]["reference_voice"] == "https://oss.example.com/cup.mp3"


@pytest.mark.asyncio
async def test_wan27_r2v_rejects_invalid_reference_voice(monkeypatch):
    adapter = WanVideoAdapter()

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    async def fake_validate_reference_voice(url: str, label: str):
        raise ValueError("参考音频时长需在1到10秒之间")

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_voice", fake_validate_reference_voice)

    with pytest.raises(ValueError, match="参考音频时长需在1到10秒之间"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="reference_to_video",
                provider="wan",
                model_id="wan2.7-r2v",
                prompt="图片1在窗边看书",
                input_assets={
                    "reference_media": [
                        {"type": "reference_image", "url": "https://oss.example.com/ref.png", "reference_voice": "https://oss.example.com/ref.mp3"},
                    ],
                },
                normalized_params={
                    "resolution": "1080P",
                    "ratio": "16:9",
                    "duration": 5,
                    "prompt_extend": True,
                    "watermark": False,
                },
            )
        )


def test_create_task_defaults_to_wan27_models(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    _patch_async_create_task(monkeypatch)

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)

    text_resp = client.post(
        "/api/video-studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_video",
            "prompt": "机械臂在仓库中开门",
            "input_assets": {},
            "normalized_params": {
                "resolution": "1080P",
                "ratio": "16:9",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert text_resp.status_code == 200
    assert text_resp.json()["task"]["model_id"] == "wan2.7-t2v"

    ref_resp = client.post(
        "/api/video-studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "reference_to_video",
            "prompt": "图片1在咖啡馆里喝咖啡",
            "input_assets": {
                "reference_media": [
                    {"type": "reference_image", "url": "https://oss.example.com/ref.png"},
                ],
            },
            "normalized_params": {
                "resolution": "1080P",
                "ratio": "16:9",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["task"]["model_id"] == "wan2.7-r2v"


def test_preview_payload_returns_wan27_r2v_provider_payload_with_reference_voice(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    async def fake_validate_reference_video(url: str, label: str):
        return {"duration": 5.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_reference_voice(url: str, label: str):
        return {"duration": 3.0, "format": "mp3", "file_size": 1024}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_video", fake_validate_reference_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_voice", fake_validate_reference_voice)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "reference_to_video",
            "provider": "wan",
            "model_id": "wan2.7-r2v",
            "model": "wan2.7-r2v",
            "prompt": "视频1看向图片1",
            "input_assets": {
                "reference_media": [
                    {"type": "reference_video", "url": "https://oss.example.com/ref.mp4", "reference_voice": "https://oss.example.com/ref.mp3"},
                    {"type": "reference_image", "url": "https://oss.example.com/ref.png"},
                ],
            },
            "normalized_params": {
                "resolution": "1080P",
                "ratio": "9:16",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["input_assets"]["reference_media"][0]["reference_voice"] == "https://oss.example.com/ref.mp3"
    assert data["provider_payload"]["model"] == "wan2.7-r2v"
    assert data["provider_payload"]["input"]["media"][0]["type"] == "reference_video"
    assert data["provider_payload"]["input"]["media"][0]["reference_voice"] == "https://oss.example.com/ref.mp3"


def test_update_task_round_trips_reference_media(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])

    async def fake_validate_image(url: str, label: str):
        return {"width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "PNG", "file_size": 1024, "has_alpha": False}

    async def fake_validate_reference_video(url: str, label: str):
        return {"duration": 5.0, "width": 1280, "height": 720, "aspect_ratio": 16 / 9, "format": "mp4", "file_size": 1024}

    async def fake_validate_reference_voice(url: str, label: str):
        return {"duration": 3.0, "format": "mp3", "file_size": 1024}

    monkeypatch.setattr("app.services.video_adapters._validate_wan27_image", fake_validate_image)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_video", fake_validate_reference_video)
    monkeypatch.setattr("app.services.video_adapters._validate_wan27_reference_voice", fake_validate_reference_voice)

    task = VideoStudioTask(
        project_id=project_id,
        name="参考生视频任务",
        task_type="reference_to_video",
        task_kind="reference_to_video",
        provider="wan",
        model_id="wan2.7-r2v",
        model="wan2.7-r2v",
        prompt="图片1在窗边看书",
        input_assets={
            "reference_media": [
                {"type": "reference_image", "url": "https://oss.example.com/reader.png", "reference_voice": "https://oss.example.com/reader.mp3"},
            ],
        },
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 5,
            "prompt_extend": True,
            "watermark": False,
        },
        status="pending",
    )
    storage_service.save_video_studio_task(task)

    resp = client.put(
        f"/api/video-studio/{task.id}",
        headers=auth_header,
        json={
            "prompt": "图片1在窗边看书，视频1走近她",
            "input_assets": {
                "reference_media": [
                    {"type": "reference_image", "url": "https://oss.example.com/reader.png", "reference_voice": "https://oss.example.com/reader.mp3"},
                    {"type": "reference_video", "url": "https://oss.example.com/walker.mp4"},
                ],
                "first_frame": ["https://oss.example.com/first.png"],
            },
            "normalized_params": {
                "resolution": "1080P",
                "ratio": "3:4",
                "duration": 8,
                "prompt_extend": True,
                "watermark": False,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["input_assets"]["reference_media"][0]["reference_voice"] == "https://oss.example.com/reader.mp3"
    assert data["input_assets"]["reference_media"][1]["type"] == "reference_video"
    assert data["reference_video_urls"] == [
        "https://oss.example.com/reader.png",
        "https://oss.example.com/walker.mp4",
    ]


@pytest.mark.asyncio
async def test_background_submit_failure_keeps_raw_provider_error(registered_user, monkeypatch):
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="HH 提交失败任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        model="happyhorse-1.0-t2v",
        prompt="一只机械马在霓虹街道中奔跑",
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
        },
        input_assets={},
        status="processing",
    )
    normalized = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        key_profile="test",
        prompt=task.prompt,
        normalized_params=task.normalized_params,
    )
    provider_payload = {
        "model": "happyhorse-1.0-t2v",
        "input": {"prompt": task.prompt},
        "parameters": {"resolution": "1080P", "ratio": "16:9", "duration": 5, "watermark": False},
    }
    provider_headers = {"X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER}

    class FakeAdapter:
        async def submit(self, request, seed_offset=0):
            raise VideoProviderError(
                code="Model.AccessDenied",
                message="Model access denied.",
                request_id="req-denied-1",
                raw_response={
                    "request_id": "req-denied-1",
                    "code": "Model.AccessDenied",
                    "message": "Model access denied.",
                    "details": {"model": "happyhorse-1.0-t2v"},
                },
                provider="happyhorse",
                key_profile="test",
                provider_payload=provider_payload,
                provider_headers=provider_headers,
            )

    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())

    await video_studio_router._background_create_video_tasks(task, normalized, user["id"], None)

    saved = storage_service.get_video_studio_task(task.id)
    assert saved.status == "failed"
    assert saved.error_message == "Model.AccessDenied - Model access denied."
    assert saved.request_ids == ["req-denied-1"]
    assert saved.provider_payload_snapshot == provider_payload
    submit_meta = saved.provider_result_meta["submit_error"]
    assert submit_meta["provider"] == "happyhorse"
    assert submit_meta["key_profile"] == "test"
    assert submit_meta["request_id"] == "req-denied-1"
    assert submit_meta["error_code"] == "Model.AccessDenied"
    assert submit_meta["provider_headers"] == provider_headers
    assert submit_meta["raw_response"]["details"]["model"] == "happyhorse-1.0-t2v"


@pytest.mark.asyncio
async def test_background_submit_success_keeps_safe_provider_headers(registered_user, monkeypatch):
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="HH 关闭绿网任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        model="happyhorse-1.0-t2v",
        prompt="一只机械马在霓虹街道中奔跑",
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
            "disable_data_inspection": True,
        },
        input_assets={},
        status="processing",
    )
    storage_service.save_video_studio_task(task)
    normalized = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        key_profile="test",
        prompt=task.prompt,
        normalized_params=task.normalized_params,
    )
    provider_payload = {
        "model": "happyhorse-1.0-t2v",
        "input": {"prompt": task.prompt},
        "parameters": {"resolution": "1080P", "ratio": "16:9", "duration": 5, "watermark": False},
    }
    provider_headers = {"X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER}

    class FakeResult:
        def __init__(self):
            self.task_id = "task-happyhorse-header"
            self.request_id = "req-happyhorse-header"
            self.provider_payload = provider_payload
            self.provider_headers = provider_headers
            self.key_profile = "test"

    class FakeAdapter:
        async def submit(self, request, seed_offset=0):
            return FakeResult()

    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())

    await video_studio_router._background_create_video_tasks(task, normalized, user["id"], None)

    saved = storage_service.get_video_studio_task(task.id)
    assert saved.provider_payload_snapshot == provider_payload
    submit_meta = saved.provider_result_meta["task-happyhorse-header"]
    assert submit_meta["provider_headers"] == provider_headers


def test_get_failed_submit_task_backfills_developer_error_meta(client, auth_header, registered_user):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id=project_id,
        name="HH 提交失败旧任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        model="happyhorse-1.0-t2v",
        prompt="一只机械马在霓虹街道中奔跑",
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
        },
        input_assets={},
        status="failed",
        error_message="Model.AccessDenied - Model access denied.",
    )
    storage_service.save_video_studio_task(task)

    resp = client.get(f"/api/video-studio/{task.id}", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload_snapshot"]["model"] == "happyhorse-1.0-t2v"
    submit_meta = data["provider_result_meta"]["submit_error"]
    assert submit_meta["phase"] == "submit"
    assert submit_meta["error_code"] == "Model.AccessDenied"
    assert submit_meta["error_message"] == "Model access denied."
    assert submit_meta["raw_response"] == {
        "code": "Model.AccessDenied",
        "message": "Model access denied.",
    }


def test_get_task_backfills_provider_payload_snapshot(client, auth_header, registered_user):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id=project_id,
        name="缺少开发者快照的任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.6-t2v",
        model="wan2.6-t2v",
        prompt="机械臂在仓库中开门",
        normalized_params={
            "size": "1920*1080",
            "duration": 5,
            "prompt_extend": True,
            "watermark": False,
        },
        input_assets={},
        task_ids=["api-task-1"],
        provider_result_meta={
            "api-task-1": {
                "provider": "wan",
                "key_profile": "test",
                "request_id": "req-from-meta",
            }
        },
        status="succeeded",
    )
    storage_service.save_video_studio_task(task)

    resp = client.get(f"/api/video-studio/{task.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload_snapshot"]["model"] == "wan2.6-t2v"
    assert data["request_ids"] == ["req-from-meta"]


def test_delete_video_studio_task_releases_inflight_leases(client, auth_header, registered_user):
    _clear_video_studio_inflight_leases()
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id=project_id,
        name="待删除提交任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        model="wan2.7-videoedit",
        prompt="机械臂转身",
        status="processing",
        task_ids=["api-task-delete-1"],
        submit_state="submitted",
    )
    storage_service.save_video_studio_task(task)
    lease = FakeInflightLease()
    video_studio_router._video_studio_inflight_leases["api-task-delete-1"] = lease

    resp = client.delete(f"/api/video-studio/{task.id}", headers=auth_header)

    assert resp.status_code == 200
    assert lease.released is True
    assert "api-task-delete-1" not in video_studio_router._video_studio_inflight_leases


@pytest.mark.asyncio
async def test_background_submit_does_not_resurrect_deleted_task(registered_user, monkeypatch):
    _clear_video_studio_inflight_leases()
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="迟到提交任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        model="wan2.7-videoedit",
        prompt="机械臂转身",
        status="processing",
        group_count=1,
        submit_state="submitting",
        submit_started_at=datetime.now(),
        submit_attempt_id="attempt-deleted",
    )
    storage_service.save_video_studio_task(task)
    storage_service.delete_video_studio_task(task.id)
    lease = FakeInflightLease()

    async def fake_acquire(model_id):
        return lease

    async def fake_wait(model_id):
        return None

    class FakeResult:
        task_id = "api-task-late"
        request_id = "req-late"
        provider_payload = {"model": "wan2.7-videoedit"}
        provider_headers = {}
        key_profile = "test"

    class FakeAdapter:
        async def submit(self, request, seed_offset=0):
            return FakeResult()

    monkeypatch.setattr(video_studio_router, "acquire_model_inflight_lease", fake_acquire)
    monkeypatch.setattr(video_studio_router, "wait_for_model_submit", fake_wait)
    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())
    normalized = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        key_profile="test",
        prompt=task.prompt,
        normalized_params={},
    )

    await video_studio_router._background_create_video_tasks(task, normalized, user["id"], None)

    assert storage_service.get_video_studio_task(task.id) is None
    assert lease.released is True
    assert "api-task-late" not in video_studio_router._video_studio_inflight_leases


def test_regenerate_releases_old_leases_and_starts_new_attempt(client, auth_header, registered_user, monkeypatch):
    _clear_video_studio_inflight_leases()
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    old_started_at = datetime.now() - timedelta(minutes=10)
    task = VideoStudioTask(
        project_id=project_id,
        name="重新生成任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        model="wan2.7-videoedit",
        prompt="机械臂转身",
        status="processing",
        task_ids=["api-task-old"],
        request_ids=["req-old"],
        submit_state="submitted",
        submit_started_at=old_started_at,
        submit_attempt_id="attempt-old",
    )
    storage_service.save_video_studio_task(task)
    old_lease = FakeInflightLease()
    video_studio_router._video_studio_inflight_leases["api-task-old"] = old_lease
    _patch_async_create_task(monkeypatch)

    resp = client.post(f"/api/video-studio/{task.id}/regenerate", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()["task"]
    assert old_lease.released is True
    assert "api-task-old" not in video_studio_router._video_studio_inflight_leases
    assert data["status"] == "processing"
    assert data["task_ids"] == []
    assert data["request_ids"] == []
    assert data["submit_state"] == "submitting"
    assert data["submit_attempt_id"] and data["submit_attempt_id"] != "attempt-old"
    assert data["submit_started_at"] != old_started_at.isoformat()


def test_status_marks_stale_submit_without_provider_ids_failed(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    monkeypatch.setenv("MIEMIE_VIDEO_STUDIO_SUBMIT_STALE_AFTER_SECONDS", "60")
    task = VideoStudioTask(
        project_id=project_id,
        name="陈旧提交任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        model="wan2.7-videoedit",
        prompt="机械臂转身",
        status="processing",
        task_ids=[],
        request_ids=[],
        submit_state="submitting",
        submit_started_at=datetime.now() - timedelta(minutes=5),
        submit_attempt_id="attempt-stale",
    )
    storage_service.save_video_studio_task(task)

    resp = client.get(f"/api/video-studio/{task.id}/status", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()["task"]
    assert data["status"] == "failed"
    assert data["submit_state"] == "failed"
    assert "提交超时" in data["error_message"]
    submit_error = data["provider_result_meta"]["submit_error"]
    assert submit_error["error_code"] == "SubmitTimeout"
    assert submit_error["phase"] == "submit"


@pytest.mark.asyncio
async def test_cancelled_background_submit_releases_acquired_lease(registered_user, monkeypatch):
    _clear_video_studio_inflight_leases()
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="取消提交任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-videoedit",
        model="wan2.7-videoedit",
        prompt="机械臂转身",
        status="processing",
        group_count=1,
        submit_state="submitting",
        submit_started_at=datetime.now(),
        submit_attempt_id="attempt-cancel",
    )
    storage_service.save_video_studio_task(task)
    lease = FakeInflightLease()

    async def fake_acquire(model_id):
        return lease

    async def fake_wait(model_id):
        raise asyncio.CancelledError()

    monkeypatch.setattr(video_studio_router, "acquire_model_inflight_lease", fake_acquire)
    monkeypatch.setattr(video_studio_router, "wait_for_model_submit", fake_wait)

    with pytest.raises(asyncio.CancelledError):
        await video_studio_router._submit_api_tasks(task, video_studio_router._normalized_request_from_task(task))

    assert lease.released is True


def test_regenerate_legacy_video_edit_task_uses_canonical_mapping(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    set_current_user(user["id"])
    task = VideoStudioTask(
        project_id=project_id,
        name="旧局部编辑任务",
        task_type="video_edit",
        model="wanx2.1-vace-plus",
        prompt="把机械臂替换成白色工业机械臂",
        source_video_url="https://oss.example.com/source.mp4",
        mask_image_url="https://oss.example.com/mask.png",
        mask_frame_id=1,
        status="failed",
    )
    storage_service.save_video_studio_task(task)

    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(video_studio_router.oss_service, "is_enabled", lambda: True)

    async def fake_validate_source(self, video_url: str):
        return {"width": 1280, "height": 720, "fps": 24.0, "duration": 4.0}

    async def fake_validate_mask(self, mask_image_url: str, expected_width: int, expected_height: int):
        return {"width": expected_width, "height": expected_height}

    monkeypatch.setattr(video_studio_router.VaceVideoEditService, "validate_source_video", fake_validate_source)
    monkeypatch.setattr(video_studio_router.VaceVideoEditService, "validate_mask_image", fake_validate_mask)

    resp = client.post(f"/api/video-studio/{task.id}/regenerate", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()["task"]
    assert data["status"] == "processing"
    assert data["task_type"] == "video_edit"


@pytest.mark.asyncio
async def test_kling_reference_mode_requires_feature_video_for_first_frame():
    adapter = KlingVideoAdapter()

    with pytest.raises(ValueError, match="首帧参考模式需要同时提供参考视频"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="reference_to_video",
                provider="kling",
                model_id="kling/kling-v3-omni-video-generation",
                prompt="参考视频中的镜头运动，参考图片中的机械臂造型",
                input_assets={
                    "reference_images": ["https://oss.example.com/ref.png"],
                    "first_frame": ["https://oss.example.com/first.png"],
                },
                normalized_params={
                    "mode": "std",
                    "duration": 5,
                    "watermark": True,
                },
            )
        )


@pytest.mark.asyncio
async def test_vidu_size_must_match_resolution():
    adapter = ViduVideoAdapter()

    with pytest.raises(ValueError, match="当前分辨率档位下不支持该输出尺寸"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="vidu",
                model_id="vidu/viduq3-turbo_img2video",
                input_assets={"first_frame": ["https://oss.example.com/first.png"]},
                normalized_params={
                    "resolution": "540P",
                    "size": "1280*720",
                    "duration": 5,
                    "watermark": True,
                },
            )
        )


@pytest.mark.asyncio
async def test_kling_video_edit_rejects_base_video_longer_than_10_seconds(monkeypatch):
    adapter = KlingVideoAdapter()

    async def fake_validate_video(url: str, label: str):
        raise ValueError("输入视频时长需在3到10秒之间")

    monkeypatch.setattr("app.services.video_adapters._validate_kling_video", fake_validate_video)

    with pytest.raises(ValueError, match="输入视频时长需在3到10秒之间"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_edit_global",
                provider="kling",
                model_id="kling/kling-v3-omni-video-generation",
                prompt="把机械臂替换成参考图中的型号",
                input_assets={
                    "base_video": ["https://oss.example.com/base.mp4"],
                    "reference_images": ["https://oss.example.com/ref.png"],
                },
                normalized_params={
                    "mode": "std",
                    "duration": 5,
                    "audio": False,
                    "watermark": True,
                },
            )
        )


@pytest.mark.asyncio
async def test_vidu_q2_img2video_rejects_540p():
    adapter = ViduVideoAdapter()

    with pytest.raises(ValueError, match="1080P / 720P|720P / 1080P"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="vidu",
                model_id="vidu/viduq2-pro_img2video",
                input_assets={"first_frame": ["https://oss.example.com/first.png"]},
                normalized_params={
                    "resolution": "540P",
                    "duration": 5,
                    "watermark": True,
                },
            )
        )


@pytest.mark.asyncio
async def test_vidu_q2_reference_does_not_allow_auto_duration():
    adapter = ViduVideoAdapter()

    with pytest.raises(ValueError, match="不支持自动规划时长"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="reference_to_video",
                provider="vidu",
                model_id="vidu/viduq2_reference2video",
                prompt="让角色在雨中慢慢转身",
                input_assets={"reference_images": ["https://oss.example.com/ref.png"]},
                normalized_params={
                    "resolution": "720P",
                    "size": "1280*720",
                    "duration": 0,
                    "watermark": True,
                },
            )
        )


def test_infer_provider_supports_all_current_video_providers():
    assert infer_provider("kling/kling-v3-video-generation", "text_to_video") == "kling"
    assert infer_provider("vidu/viduq3-turbo_text2video", "text_to_video") == "vidu"
    assert infer_provider("happyhorse-1.0-t2v", "text_to_video") == "happyhorse"
    assert infer_provider("happyhorse-1.0-i2v", "image_to_video") == "happyhorse"
    assert infer_provider("happyhorse-1.0-r2v", "reference_to_video") == "happyhorse"
    assert infer_provider("happyhorse-1.0-video-edit", "video_edit_global") == "happyhorse"
    assert infer_provider("happyhorse-1.5-t2v", "text_to_video") == "happyhorse"
    assert infer_provider("happyhorse-1.5-i2v", "image_to_video") == "happyhorse"
    assert infer_provider("happyhorse-1.5-r2v", "reference_to_video") == "happyhorse"
    assert infer_provider("wanx2.1-vace-plus", "video_edit_local") == "wan"



def test_happyhorse_models_are_exposed_without_changing_defaults(client, auth_header):
    resp = client.get("/api/video-studio/capabilities", headers=auth_header)
    assert resp.status_code == 200

    data = resp.json()
    models = data["models"]
    assert "happyhorse-1.0-t2v" in models
    assert "happyhorse-1.0-i2v" in models
    assert "happyhorse-1.0-r2v" in models
    assert "happyhorse-1.0-video-edit" in models
    assert "happyhorse-1.5-t2v" in models
    assert "happyhorse-1.5-i2v" in models
    assert "happyhorse-1.5-r2v" in models
    assert "happyhorse-1.5-video-edit" not in models

    task_kind_defaults = {item["id"]: item["default_model_id"] for item in data["task_kinds"]}
    assert task_kind_defaults["text_to_video"] == "wan2.7-t2v"
    assert task_kind_defaults["image_to_video"] == "wan2.6-i2v-flash"
    assert task_kind_defaults["reference_to_video"] == "wan2.7-r2v"


def test_happyhorse_capability_schema_matches_supported_surface():
    capabilities = get_video_capabilities()
    models = capabilities["models"]

    t2v_model = models["happyhorse-1.0-t2v"]
    assert t2v_model["provider"] == "happyhorse"
    assert t2v_model["supported_task_kinds"] == ["text_to_video"]
    t2v_profile = t2v_model["task_profiles"]["text_to_video"]
    assert t2v_profile["input_roles"] == []
    t2v_params = {item["name"] for item in t2v_profile["parameters"]}
    assert t2v_params == {
        "resolution",
        "ratio",
        "duration",
        "watermark",
        "prompt_extend",
        "disable_data_inspection",
        "seed",
    }
    t2v_prompt_extend = next(item for item in t2v_profile["parameters"] if item["name"] == "prompt_extend")
    assert t2v_prompt_extend["default"] is True
    assert t2v_prompt_extend["advanced"] is True
    t2v_data_inspection = next(item for item in t2v_profile["parameters"] if item["name"] == "disable_data_inspection")
    assert t2v_data_inspection["default"] is False
    assert t2v_data_inspection["advanced"] is True
    t2v_ratio = next(item for item in t2v_profile["parameters"] if item["name"] == "ratio")
    assert {item["value"] for item in t2v_ratio["constraint"]["options"]} == {
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "4:5",
        "5:4",
        "21:9",
        "9:21",
    }
    assert t2v_profile["ui_hints"]["prompt_help"]["summary"]
    assert t2v_profile["ui_hints"]["prompt_length_policy"] == {
        "mode": "cjk_weighted",
        "max_units": 5000,
        "cjk_unit": 2,
        "non_cjk_unit": 1,
        "cjk_equivalent_limit": 2500,
        "non_cjk_equivalent_limit": 5000,
    }
    assert t2v_profile["verification_profiles"] == {
        "smoke": ["basic_prompt"],
        "full": ["basic_prompt", "portrait_ratio", "seeded_generation"],
    }

    i2v_model = models["happyhorse-1.0-i2v"]
    assert i2v_model["provider"] == "happyhorse"
    assert i2v_model["supported_task_kinds"] == ["image_to_video"]
    i2v_profile = i2v_model["task_profiles"]["image_to_video"]
    assert i2v_profile["input_roles"] == ["first_frame"]
    i2v_params = {item["name"] for item in i2v_profile["parameters"]}
    assert i2v_params == {"resolution", "duration", "watermark", "prompt_extend", "disable_data_inspection", "seed"}
    i2v_prompt_extend = next(item for item in i2v_profile["parameters"] if item["name"] == "prompt_extend")
    assert i2v_prompt_extend["default"] is True
    i2v_data_inspection = next(item for item in i2v_profile["parameters"] if item["name"] == "disable_data_inspection")
    assert i2v_data_inspection["default"] is False
    assert i2v_profile["ui_hints"]["asset_help"]["first_frame"]["limits"]
    assert i2v_profile["verification_profiles"] == {
        "smoke": ["single_first_frame"],
        "full": ["single_first_frame", "optional_prompt", "seeded_generation"],
    }

    r2v_model = models["happyhorse-1.0-r2v"]
    assert r2v_model["provider"] == "happyhorse"
    assert r2v_model["supported_task_kinds"] == ["reference_to_video"]
    r2v_profile = r2v_model["task_profiles"]["reference_to_video"]
    assert r2v_profile["input_roles"] == ["reference_image"]
    r2v_params = {item["name"] for item in r2v_profile["parameters"]}
    assert r2v_params == {
        "resolution",
        "ratio",
        "duration",
        "watermark",
        "prompt_extend",
        "disable_data_inspection",
        "seed",
    }
    r2v_prompt_extend = next(item for item in r2v_profile["parameters"] if item["name"] == "prompt_extend")
    assert r2v_prompt_extend["default"] is True
    r2v_data_inspection = next(item for item in r2v_profile["parameters"] if item["name"] == "disable_data_inspection")
    assert r2v_data_inspection["default"] is False
    r2v_ratio = next(item for item in r2v_profile["parameters"] if item["name"] == "ratio")
    assert {item["value"] for item in r2v_ratio["constraint"]["options"]} == {
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "4:5",
        "5:4",
        "21:9",
        "9:21",
    }
    assert r2v_profile["ui_hints"]["max_reference_images"] == 9
    assert r2v_profile["ui_hints"]["max_reference_videos"] == 0
    assert any("Base64" in item for item in r2v_profile["ui_hints"]["asset_help"]["reference_image"]["limits"])
    assert any("20MB" in item for item in r2v_profile["ui_hints"]["asset_help"]["reference_image"]["limits"])
    assert "[Image 1]" in r2v_profile["ui_hints"]["prompt_help"]["notes"][0]
    assert "[Image 2]" in r2v_profile["ui_hints"]["prompt_help"]["how_to_choose"][0]

    video_edit_model = models["happyhorse-1.0-video-edit"]
    assert video_edit_model["provider"] == "happyhorse"
    assert video_edit_model["supported_task_kinds"] == ["video_edit_global"]
    video_edit_profile = video_edit_model["task_profiles"]["video_edit_global"]
    assert video_edit_profile["input_roles"] == ["base_video", "reference_image"]
    video_edit_params = {item["name"] for item in video_edit_profile["parameters"]}
    assert video_edit_params == {
        "resolution",
        "watermark",
        "prompt_extend",
        "disable_data_inspection",
        "audio_setting",
        "seed",
    }
    video_edit_prompt_extend = next(item for item in video_edit_profile["parameters"] if item["name"] == "prompt_extend")
    assert video_edit_prompt_extend["default"] is True
    video_edit_data_inspection = next(item for item in video_edit_profile["parameters"] if item["name"] == "disable_data_inspection")
    assert video_edit_data_inspection["default"] is False
    assert video_edit_profile["ui_hints"]["max_reference_images"] == 5
    assert video_edit_profile["ui_hints"]["max_reference_videos"] == 0
    assert any("Base64" in item for item in video_edit_profile["ui_hints"]["asset_help"]["reference_image"]["limits"])
    assert any("20MB" in item for item in video_edit_profile["ui_hints"]["asset_help"]["reference_image"]["limits"])


def test_happyhorse_15_capability_schema_reuses_supported_surface():
    capabilities = get_video_capabilities()
    models = capabilities["models"]

    expected = {
        "happyhorse-1.5-t2v": ("HappyHorse 1.5 文生视频", ["text_to_video"], "text_to_video"),
        "happyhorse-1.5-i2v": ("HappyHorse 1.5 图生视频", ["image_to_video"], "image_to_video"),
        "happyhorse-1.5-r2v": ("HappyHorse 1.5 参考生视频", ["reference_to_video"], "reference_to_video"),
    }
    for model_id, (name, task_kinds, task_kind) in expected.items():
        model = models[model_id]
        assert model["name"] == name
        assert model["provider"] == "happyhorse"
        assert model["recommended"] is False
        assert model["doc_url"] == "docs/阿里云模型api文档/happyhorse1.5接入文档.md"
        assert model["supported_task_kinds"] == task_kinds
        assert task_kind in model["task_profiles"]

    t2v_profile = models["happyhorse-1.5-t2v"]["task_profiles"]["text_to_video"]
    t2v_ratio = next(item for item in t2v_profile["parameters"] if item["name"] == "ratio")
    assert {"21:9", "9:21"} <= {item["value"] for item in t2v_ratio["constraint"]["options"]}
    assert any("音频" in note for note in t2v_profile["ui_hints"]["prompt_help"]["notes"])

    i2v_profile = models["happyhorse-1.5-i2v"]["task_profiles"]["image_to_video"]
    assert any("BMP" in item for item in i2v_profile["ui_hints"]["asset_help"]["first_frame"]["limits"])

    r2v_profile = models["happyhorse-1.5-r2v"]["task_profiles"]["reference_to_video"]
    assert r2v_profile["ui_hints"]["reference_token_policy"]["tokens"]["reference_image"]["template"] == "[Image {index}]"
    assert any("BMP" in item for item in r2v_profile["ui_hints"]["asset_help"]["reference_image"]["limits"])


def test_happyhorse_t2v_builds_provider_payload():
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-t2v",
            prompt="一只机械马在霓虹街道中奔跑",
            negative_prompt="不要噪点",
            normalized_params={
                "resolution": "1080P",
                "ratio": "9:16",
                "duration": 8,
                "watermark": False,
                "seed": 123,
                "prompt_extend": True,
            },
        )
    )

    assert payload == {
        "model": "happyhorse-1.0-t2v",
        "input": {"prompt": "一只机械马在霓虹街道中奔跑"},
        "parameters": {
            "resolution": "1080P",
            "ratio": "9:16",
            "duration": 8,
            "watermark": False,
            "seed": 123,
        },
    }


def test_happyhorse_i2v_builds_first_frame_media_payload():
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="image_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-i2v",
            prompt="让画面慢慢动起来",
            input_assets={"first_frame": ["https://oss.example.com/first-frame.png"]},
            normalized_params={
                "resolution": "720P",
                "duration": 5,
                "watermark": False,
                "seed": 7,
                "ratio": "16:9",
            },
        )
    )

    assert payload == {
        "model": "happyhorse-1.0-i2v",
        "input": {
            "prompt": "让画面慢慢动起来",
            "media": [{"type": "first_frame", "url": "https://oss.example.com/first-frame.png"}],
        },
        "parameters": {
            "resolution": "720P",
            "duration": 5,
            "watermark": False,
            "seed": 7,
        },
    }


def test_happyhorse_r2v_builds_reference_image_media_payload():
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="reference_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-r2v",
            prompt="[Image 1]中的骑手骑着[Image 2]中的马在草地上奔跑",
            input_assets={
                "reference_media": [
                    {"type": "reference_image", "url": "https://oss.example.com/rider.png"},
                    {"type": "reference_image", "url": "https://oss.example.com/horse.webp"},
                ],
                "reference_videos": ["https://oss.example.com/ignored.mp4"],
            },
            normalized_params={
                "resolution": "720P",
                "ratio": "16:9",
                "duration": 5,
                "watermark": False,
                "seed": 9,
                "prompt_extend": True,
            },
        )
    )

    assert payload == {
        "model": "happyhorse-1.0-r2v",
        "input": {
            "prompt": "[Image 1]中的骑手骑着[Image 2]中的马在草地上奔跑",
            "media": [
                {"type": "reference_image", "url": "https://oss.example.com/rider.png"},
                {"type": "reference_image", "url": "https://oss.example.com/horse.webp"},
            ],
        },
        "parameters": {
            "resolution": "720P",
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
            "seed": 9,
        },
    }


@pytest.mark.parametrize(
    ("task_kind", "model_id", "prompt", "input_assets", "normalized_params", "expected_input"),
    [
        (
            "text_to_video",
            "happyhorse-1.5-t2v",
            "一匹白马穿过超宽银幕风格的峡谷",
            {},
            {"resolution": "720P", "ratio": "21:9", "duration": 5, "watermark": False},
            {"prompt": "一匹白马穿过超宽银幕风格的峡谷"},
        ),
        (
            "image_to_video",
            "happyhorse-1.5-i2v",
            "让画面中的角色挥手",
            {"first_frame": ["https://oss.example.com/first.bmp"]},
            {"resolution": "720P", "duration": 5, "watermark": False},
            {
                "prompt": "让画面中的角色挥手",
                "media": [{"type": "first_frame", "url": "https://oss.example.com/first.bmp"}],
            },
        ),
        (
            "reference_to_video",
            "happyhorse-1.5-r2v",
            "[Image 1]中的角色在竖向长画幅中转身",
            {"reference_images": ["https://oss.example.com/ref.bmp"]},
            {"resolution": "720P", "ratio": "9:21", "duration": 5, "watermark": False},
            {
                "prompt": "[Image 1]中的角色在竖向长画幅中转身",
                "media": [{"type": "reference_image", "url": "https://oss.example.com/ref.bmp"}],
            },
        ),
    ],
)
def test_happyhorse_15_payload_keeps_selected_model_id(
    task_kind,
    model_id,
    prompt,
    input_assets,
    normalized_params,
    expected_input,
):
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind=task_kind,
            provider="happyhorse",
            model_id=model_id,
            prompt=prompt,
            input_assets=input_assets,
            normalized_params=normalized_params,
        )
    )

    assert payload["model"] == model_id
    assert payload["input"] == expected_input
    assert payload["parameters"]["watermark"] is False


def test_happyhorse_video_edit_builds_video_and_reference_image_payload():
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="video_edit_global",
            provider="happyhorse",
            model_id="happyhorse-1.0-video-edit",
            prompt="让视频中的角色穿上参考图里的条纹毛衣",
            negative_prompt="不要闪烁",
            input_assets={
                "base_video": ["https://oss.example.com/base.mp4"],
                "source_video": ["https://oss.example.com/source-ignored.mp4"],
                "reference_images": [
                    "https://oss.example.com/clothes.webp",
                    "https://oss.example.com/pattern.png",
                ],
            },
            normalized_params={
                "resolution": "720P",
                "duration": 12,
                "ratio": "16:9",
                "watermark": False,
                "audio_setting": "origin",
                "seed": 42,
                "prompt_extend": True,
            },
        )
    )

    assert payload == {
        "model": "happyhorse-1.0-video-edit",
        "input": {
            "prompt": "让视频中的角色穿上参考图里的条纹毛衣",
            "media": [
                {"type": "video", "url": "https://oss.example.com/base.mp4"},
                {"type": "reference_image", "url": "https://oss.example.com/clothes.webp"},
                {"type": "reference_image", "url": "https://oss.example.com/pattern.png"},
            ],
        },
        "parameters": {
            "resolution": "720P",
            "watermark": False,
            "audio_setting": "origin",
            "seed": 42,
        },
    }


@pytest.mark.parametrize(
    ("task_kind", "model_id", "prompt", "input_assets", "normalized_params"),
    [
        (
            "text_to_video",
            "happyhorse-1.0-t2v",
            "一只机械马在霓虹街道中奔跑",
            {},
            {
                "resolution": "1080P",
                "ratio": "16:9",
                "duration": 5,
                "watermark": False,
                "prompt_extend": False,
            },
        ),
        (
            "image_to_video",
            "happyhorse-1.0-i2v",
            "让首帧缓慢动起来",
            {"first_frame": ["https://oss.example.com/first-frame.png"]},
            {
                "resolution": "720P",
                "duration": 5,
                "watermark": False,
                "prompt_extend": False,
            },
        ),
        (
            "reference_to_video",
            "happyhorse-1.0-r2v",
            "[Image 1]中的角色挥手",
            {"reference_images": ["https://oss.example.com/ref.png"]},
            {
                "resolution": "720P",
                "ratio": "4:5",
                "duration": 6,
                "watermark": False,
                "prompt_extend": False,
            },
        ),
        (
            "video_edit_global",
            "happyhorse-1.0-video-edit",
            "把视频改成水彩风格",
            {"base_video": ["https://oss.example.com/base.mp4"]},
            {
                "resolution": "720P",
                "watermark": False,
                "audio_setting": "auto",
                "prompt_extend": False,
            },
        ),
    ],
)
def test_happyhorse_prompt_extend_false_is_sent_for_all_task_kinds(
    task_kind,
    model_id,
    prompt,
    input_assets,
    normalized_params,
):
    adapter = get_video_adapter("happyhorse")
    payload = adapter.build_provider_payload(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind=task_kind,
            provider="happyhorse",
            model_id=model_id,
            prompt=prompt,
            input_assets=input_assets,
            normalized_params=normalized_params,
        )
    )

    assert payload["parameters"]["prompt_extend"] is False
    assert "disable_data_inspection" not in payload["parameters"]


def test_happyhorse_data_inspection_header_is_separate_from_payload():
    adapter = get_video_adapter("happyhorse")
    request = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="text_to_video",
        provider="happyhorse",
        model_id="happyhorse-1.0-t2v",
        prompt="一只机械马在霓虹街道中奔跑",
        normalized_params={
            "resolution": "1080P",
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
            "disable_data_inspection": True,
        },
    )

    assert adapter.build_provider_headers(request) == {
        "X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER,
    }
    payload = adapter.build_provider_payload(request)
    assert "disable_data_inspection" not in payload["parameters"]


@pytest.mark.asyncio
async def test_happyhorse_submit_passes_data_inspection_header(monkeypatch):
    adapter = get_video_adapter("happyhorse")
    captured = {}

    async def fake_create_task(self, request_body, extra_headers=None):
        captured["request_body"] = request_body
        captured["extra_headers"] = extra_headers or {}

        class FakeResult:
            task_id = "task-happyhorse-header"
            request_id = "req-happyhorse-header"
            provider_payload = request_body
            provider_headers = extra_headers or {}
            key_profile = "test"

        return FakeResult()

    monkeypatch.setattr("app.services.video_adapters.DashScopeGenericVideoService.create_task", fake_create_task)

    result = await adapter.submit(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-t2v",
            key_profile="test",
            prompt="一只机械马在霓虹街道中奔跑",
            normalized_params={
                "resolution": "1080P",
                "ratio": "16:9",
                "duration": 5,
                "watermark": False,
                "disable_data_inspection": True,
            },
        )
    )

    assert captured["extra_headers"] == {
        "X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER,
    }
    assert result.provider_headers == captured["extra_headers"]
    assert "disable_data_inspection" not in captured["request_body"]["parameters"]


@pytest.mark.asyncio
async def test_generic_dashscope_video_service_merges_extra_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"output": {"task_id": "task-extra-header"}, "request_id": "req-extra-header"}

    class MockAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["json"] = json or {}
            return FakeResponse()

    monkeypatch.setattr("app.services.video_adapters.httpx.AsyncClient", MockAsyncClient)

    service = DashScopeGenericVideoService("happyhorse", key_profile="test")
    result = await service.create_task(
        {"model": "happyhorse-1.0-t2v", "input": {"prompt": "test"}, "parameters": {}},
        extra_headers={"X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER},
    )

    assert captured["headers"]["X-DashScope-Async"] == "enable"
    assert captured["headers"]["X-DashScope-DataInspection"] == DATA_INSPECTION_DISABLED_HEADER
    assert captured["json"]["model"] == "happyhorse-1.0-t2v"
    assert result.provider_headers == {
        "X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER,
    }


@pytest.mark.asyncio
async def test_happyhorse_t2v_validate_rejects_blank_prompt():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="提示词不能为空"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="text_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-t2v",
                prompt="   ",
                normalized_params={
                    "resolution": "1080P",
                    "ratio": "16:9",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_prompt_length_uses_cjk_weighted_units():
    adapter = get_video_adapter("happyhorse")

    async def validate_prompt(prompt: str):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="text_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-t2v",
                prompt=prompt,
                normalized_params={
                    "resolution": "1080P",
                    "ratio": "16:9",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )

    await validate_prompt("马" * 2500)
    await validate_prompt("a" * 5000)
    await validate_prompt(("马" * 2499) + "ab")

    with pytest.raises(ValueError, match="2500个中文字符或5000个非中文字符"):
        await validate_prompt("马" * 2501)
    with pytest.raises(ValueError, match="2500个中文字符或5000个非中文字符"):
        await validate_prompt("a" * 5001)
    with pytest.raises(ValueError, match="2500个中文字符或5000个非中文字符"):
        await validate_prompt(("马" * 2499) + "abc")


@pytest.mark.asyncio
async def test_happyhorse_t2v_and_r2v_validate_accept_new_ratios(monkeypatch):
    adapter = get_video_adapter("happyhorse")

    async def fake_validate_reference_image(url: str, label: str):
        return {"url": url, "label": label}

    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_reference_image", fake_validate_reference_image)

    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-t2v",
            prompt="一只机械马在书店门口停下",
            normalized_params={
                "resolution": "720P",
                "ratio": "4:5",
                "duration": 5,
                "watermark": False,
            },
        )
    )
    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="reference_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-r2v",
            prompt="[Image 1]中的角色转身挥手",
            input_assets={"reference_images": ["https://oss.example.com/ref.png"]},
            normalized_params={
                "resolution": "720P",
                "ratio": "5:4",
                "duration": 5,
                "watermark": False,
            },
        )
    )
    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="text_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.5-t2v",
            prompt="一只机械马在超宽银幕峡谷中奔跑",
            normalized_params={
                "resolution": "720P",
                "ratio": "21:9",
                "duration": 5,
                "watermark": False,
            },
        )
    )
    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="reference_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.5-r2v",
            prompt="[Image 1]中的角色在极竖画幅中转身",
            input_assets={"reference_images": ["https://oss.example.com/ref.bmp"]},
            normalized_params={
                "resolution": "720P",
                "ratio": "9:21",
                "duration": 5,
                "watermark": False,
            },
        )
    )


@pytest.mark.asyncio
async def test_happyhorse_rejects_model_task_kind_mismatch():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="不支持任务类型"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_edit_global",
                provider="happyhorse",
                model_id="happyhorse-1.5-t2v",
                prompt="把视频改成水彩风格",
                input_assets={"base_video": ["https://oss.example.com/base.mp4"]},
                normalized_params={
                    "resolution": "720P",
                    "watermark": False,
                    "audio_setting": "auto",
                },
            )
        )
    with pytest.raises(ValueError, match="不支持任务类型"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.5-r2v",
                prompt="让首帧动起来",
                input_assets={"first_frame": ["https://oss.example.com/first.png"]},
                normalized_params={
                    "resolution": "720P",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_i2v_validate_rejects_multiple_first_frames():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="仅支持1张首帧图"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-i2v",
                prompt="让画面动起来",
                input_assets={
                    "first_frame": [
                        "https://oss.example.com/first-1.png",
                        "https://oss.example.com/first-2.png",
                    ]
                },
                normalized_params={
                    "resolution": "720P",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_image_validation_allows_twenty_mb_data_uri(monkeypatch):
    adapter = get_video_adapter("happyhorse")
    data_uri = "data:image/png;base64," + ("A" * 32)

    async def fake_inspect_remote_image(url: str):
        assert url == data_uri
        return {
            "format": "PNG",
            "file_size": 20 * 1024 * 1024,
            "width": 512,
            "height": 512,
            "aspect_ratio": 1.0,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)

    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="image_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.0-i2v",
            prompt="让画面慢慢动起来",
            input_assets={"first_frame": [data_uri]},
            normalized_params={
                "resolution": "720P",
                "duration": 5,
                "watermark": False,
            },
        )
    )


@pytest.mark.asyncio
async def test_happyhorse_image_validation_allows_bmp(monkeypatch):
    adapter = get_video_adapter("happyhorse")

    async def fake_inspect_remote_image(url: str):
        return {
            "format": "BMP",
            "file_size": 1024,
            "width": 512,
            "height": 512,
            "aspect_ratio": 1.0,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)

    await adapter.validate(
        NormalizedVideoTaskRequest(
            project_id="p1",
            task_kind="image_to_video",
            provider="happyhorse",
            model_id="happyhorse-1.5-i2v",
            prompt="让画面慢慢动起来",
            input_assets={"first_frame": ["https://oss.example.com/first.bmp"]},
            normalized_params={
                "resolution": "720P",
                "duration": 5,
                "watermark": False,
            },
        )
    )


@pytest.mark.asyncio
async def test_happyhorse_image_validation_rejects_over_twenty_mb(monkeypatch):
    adapter = get_video_adapter("happyhorse")

    async def fake_inspect_remote_image(url: str):
        return {
            "format": "PNG",
            "file_size": (20 * 1024 * 1024) + 1,
            "width": 512,
            "height": 512,
            "aspect_ratio": 1.0,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)

    with pytest.raises(ValueError, match="20MB"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-i2v",
                prompt="让画面慢慢动起来",
                input_assets={"first_frame": ["https://oss.example.com/first.png"]},
                normalized_params={
                    "resolution": "720P",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_i2v_validate_rejects_invalid_image_metadata(monkeypatch):
    adapter = get_video_adapter("happyhorse")

    async def fake_inspect_remote_image(url: str):
        return {
            "format": "GIF",
            "file_size": 1024,
            "width": 512,
            "height": 512,
            "aspect_ratio": 1.0,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)

    with pytest.raises(ValueError, match="格式仅支持"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="image_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-i2v",
                prompt="让画面动起来",
                input_assets={"first_frame": ["https://oss.example.com/first.png"]},
                normalized_params={
                    "resolution": "720P",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_r2v_validate_rejects_reference_video():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="仅支持参考图"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="reference_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-r2v",
                prompt="character1 在森林里奔跑",
                input_assets={
                    "reference_media": [
                        {"type": "reference_video", "url": "https://oss.example.com/ref.mp4"},
                    ],
                },
                normalized_params={
                    "resolution": "720P",
                    "ratio": "16:9",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_r2v_validate_rejects_too_many_reference_images():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="1到9张参考图"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="reference_to_video",
                provider="happyhorse",
                model_id="happyhorse-1.0-r2v",
                prompt="character1 到 character10 排队走过镜头",
                input_assets={
                    "reference_images": [
                        f"https://oss.example.com/ref-{index}.png"
                        for index in range(10)
                    ],
                },
                normalized_params={
                    "resolution": "720P",
                    "ratio": "16:9",
                    "duration": 5,
                    "watermark": False,
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_video_edit_validate_rejects_invalid_video_metadata(monkeypatch):
    adapter = get_video_adapter("happyhorse")

    async def fake_validate_video(url: str, label: str):
        raise ValueError("待编辑视频帧率必须大于8FPS")

    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_video_edit_video", fake_validate_video)

    with pytest.raises(ValueError, match="帧率必须大于8FPS"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_edit_global",
                provider="happyhorse",
                model_id="happyhorse-1.0-video-edit",
                prompt="让视频变成水彩风格",
                input_assets={"base_video": ["https://oss.example.com/base.mp4"]},
                normalized_params={
                    "resolution": "720P",
                    "watermark": False,
                    "audio_setting": "auto",
                },
            )
        )


@pytest.mark.asyncio
async def test_happyhorse_video_edit_validate_rejects_too_many_reference_images():
    adapter = get_video_adapter("happyhorse")

    with pytest.raises(ValueError, match="最多支持5张参考图"):
        await adapter.validate(
            NormalizedVideoTaskRequest(
                project_id="p1",
                task_kind="video_edit_global",
                provider="happyhorse",
                model_id="happyhorse-1.0-video-edit",
                prompt="让角色穿上参考图里的衣服",
                input_assets={
                    "base_video": ["https://oss.example.com/base.mp4"],
                    "reference_images": [
                        f"https://oss.example.com/ref-{index}.png"
                        for index in range(6)
                    ],
                },
                normalized_params={
                    "resolution": "720P",
                    "watermark": False,
                    "audio_setting": "auto",
                },
            )
        )


def test_preview_payload_returns_happyhorse_provider_payload(client, auth_header):
    project_id = _create_project(client, auth_header)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_video",
            "provider": "happyhorse",
            "model_id": "happyhorse-1.0-t2v",
            "model": "happyhorse-1.0-t2v",
            "prompt": "一只机械马在霓虹街道中奔跑",
            "normalized_params": {
                "resolution": "1080P",
                "ratio": "9:16",
                "duration": 8,
                "watermark": False,
                "seed": 123,
                "prompt_extend": False,
                "disable_data_inspection": True,
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"] == {
        "model": "happyhorse-1.0-t2v",
        "input": {"prompt": "一只机械马在霓虹街道中奔跑"},
        "parameters": {
            "resolution": "1080P",
            "ratio": "9:16",
            "duration": 8,
            "watermark": False,
            "seed": 123,
            "prompt_extend": False,
        },
    }
    assert data["provider_headers"] == {
        "X-DashScope-DataInspection": DATA_INSPECTION_DISABLED_HEADER,
    }


def test_preview_payload_returns_happyhorse_r2v_provider_payload(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_reference_image(url: str, label: str):
        return {"width": 1024, "height": 768, "format": "PNG", "file_size": 1024, "aspect_ratio": 4 / 3}

    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_reference_image", fake_validate_reference_image)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "reference_to_video",
            "provider": "happyhorse",
            "model_id": "happyhorse-1.0-r2v",
            "model": "happyhorse-1.0-r2v",
            "prompt": "character1 举起 character2",
            "input_assets": {
                "reference_media": [
                    {"type": "reference_image", "url": "https://oss.example.com/person.png"},
                    {"type": "reference_image", "url": "https://oss.example.com/prop.webp"},
                ],
            },
            "normalized_params": {
                "resolution": "720P",
                "ratio": "4:3",
                "duration": 6,
                "watermark": False,
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["validation_warnings"] == []
    assert data["provider_payload"]["model"] == "happyhorse-1.0-r2v"
    assert data["provider_payload"]["input"]["media"] == [
        {"type": "reference_image", "url": "https://oss.example.com/person.png"},
        {"type": "reference_image", "url": "https://oss.example.com/prop.webp"},
    ]
    assert "prompt_extend" not in data["provider_payload"]["parameters"]


def test_preview_payload_returns_happyhorse_15_provider_payload(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_reference_image(url: str, label: str):
        return {"width": 1024, "height": 768, "format": "BMP", "file_size": 1024, "aspect_ratio": 4 / 3}

    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_reference_image", fake_validate_reference_image)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "reference_to_video",
            "provider": "happyhorse",
            "model_id": "happyhorse-1.5-r2v",
            "model": "happyhorse-1.5-r2v",
            "prompt": "[Image 1]中的角色转身",
            "input_assets": {
                "reference_media": [
                    {"type": "reference_image", "url": "https://oss.example.com/person.bmp"},
                ],
            },
            "normalized_params": {
                "resolution": "720P",
                "ratio": "9:21",
                "duration": 6,
                "watermark": False,
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["validation_warnings"] == []
    assert data["provider_payload"]["model"] == "happyhorse-1.5-r2v"
    assert data["provider_payload"]["parameters"]["ratio"] == "9:21"


def test_preview_payload_returns_happyhorse_video_edit_provider_payload(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)

    async def fake_validate_video(url: str, label: str):
        return {"duration": 8.0, "width": 1280, "height": 720, "fps": 24.0, "format": "mp4", "file_size": 1024, "aspect_ratio": 16 / 9}

    async def fake_validate_image(url: str, label: str):
        return {"width": 1024, "height": 768, "format": "PNG", "file_size": 1024, "aspect_ratio": 4 / 3}

    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_video_edit_video", fake_validate_video)
    monkeypatch.setattr("app.services.video_adapters._validate_happyhorse_video_edit_reference_image", fake_validate_image)

    resp = client.post(
        "/api/video-studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "video_edit_global",
            "provider": "happyhorse",
            "model_id": "happyhorse-1.0-video-edit",
            "model": "happyhorse-1.0-video-edit",
            "prompt": "让视频中的角色穿上参考图里的条纹毛衣",
            "negative_prompt": "不要闪烁",
            "input_assets": {
                "base_video": ["https://oss.example.com/base.mp4"],
                "reference_images": ["https://oss.example.com/clothes.webp"],
            },
            "normalized_params": {
                "resolution": "720P",
                "duration": 12,
                "ratio": "16:9",
                "watermark": False,
                "audio_setting": "origin",
                "seed": 42,
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["validation_warnings"] == []
    assert data["provider_payload"] == {
        "model": "happyhorse-1.0-video-edit",
        "input": {
            "prompt": "让视频中的角色穿上参考图里的条纹毛衣",
            "media": [
                {"type": "video", "url": "https://oss.example.com/base.mp4"},
                {"type": "reference_image", "url": "https://oss.example.com/clothes.webp"},
            ],
        },
        "parameters": {
            "resolution": "720P",
            "watermark": False,
            "audio_setting": "origin",
            "seed": 42,
        },
    }
