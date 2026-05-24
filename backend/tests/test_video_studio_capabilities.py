import pytest
from datetime import datetime, timedelta

from app.models.media import VideoStudioTask
from app.routers import video_studio as video_studio_router
from app.services.video_adapters import (
    DashScopeGenericVideoService,
    KlingVideoAdapter,
    NormalizedVideoTaskRequest,
    VideoProviderError,
    VideoStatusResult,
    WanVideoAdapter,
    ViduVideoAdapter,
    get_video_adapter,
    infer_provider,
)
from app.services.video_capabilities import get_video_capabilities
from app.services.storage import get_user_storage, set_current_user, storage_service


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "能力测试项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(video_studio_router.asyncio, "create_task", fake_create_task)


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


def test_video_studio_status_endpoint_is_pure_read(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    task = VideoStudioTask(
        project_id=project_id,
        name="处理中任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        task_ids=["provider-task-1"],
        request_ids=["provider-req-1"],
    )
    user_storage.save_video_studio_task(task)

    def fail_fetch(*args, **kwargs):
        raise AssertionError("status 接口不应直接触发 provider fetch")

    monkeypatch.setattr(video_studio_router, "get_video_adapter", fail_fetch)

    resp = client.get(f"/api/video-studio/{task.id}/status", headers=auth_header)
    assert resp.status_code == 200
    payload = resp.json()["task"]
    assert payload["id"] == task.id
    assert payload["status"] == "processing"
    assert payload["task_ids"] == ["provider-task-1"]


@pytest.mark.asyncio
async def test_reconcile_video_task_once_updates_terminal_state(monkeypatch):
    task = VideoStudioTask(
        project_id="p1",
        name="待完成任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        task_ids=["provider-task-1"],
        request_ids=["provider-req-1"],
        provider_result_meta={
            "provider-task-1": {
                "submitted_at": "2026-04-21T00:00:00",
                "error_message": "OSS未启用，无法持久化生成视频",
            }
        },
    )

    class FakeAdapter:
        async def fetch(self, request, task_id):
            assert request.task_kind == "text_to_video"
            assert task_id == "provider-task-1"
            return VideoStatusResult(
                status="SUCCEEDED",
                video_url="https://oss.example.com/video.mp4",
                request_id="provider-req-2",
                usage={"tokens": 1},
                raw_output={"task_status": "SUCCEEDED"},
            )

    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())
    monkeypatch.setattr(video_studio_router.oss_service, "should_persist_generated_url", lambda url: False)
    async def fake_extract_thumbnail(video_url, project_id):
        return "https://oss.example.com/thumb.jpg"

    monkeypatch.setattr(video_studio_router, "_extract_video_thumbnail_to_oss", fake_extract_thumbnail)
    saved_tasks = []
    monkeypatch.setattr(video_studio_router.storage_service, "save_video_studio_task", lambda next_task: saved_tasks.append(next_task.model_copy(deep=True)))

    updated = await video_studio_router._reconcile_video_task_once(task)

    assert updated.status == "succeeded"
    assert updated.selected_video_url == "https://oss.example.com/video.mp4"
    assert updated.thumbnail_url == "https://oss.example.com/thumb.jpg"
    assert updated.video_urls == ["https://oss.example.com/video.mp4"]
    assert updated.provider_result_meta["provider-task-1"]["request_id"] == "provider-req-2"
    assert updated.provider_result_meta["provider-task-1"]["error_message"] is None
    assert updated.provider_result_meta["provider-task-1"]["raw_output"]["task_status"] == "SUCCEEDED"
    assert saved_tasks


@pytest.mark.asyncio
async def test_reconcile_video_task_once_keeps_provider_url_when_oss_disabled(monkeypatch):
    provider_video_url = "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/result.mp4"
    task = VideoStudioTask(
        project_id="p1",
        name="无 OSS 真实供应商任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="小猫眨眼",
        status="processing",
        task_ids=["provider-task-1"],
        request_ids=["provider-req-1"],
        provider_result_meta={
            "provider-task-1": {
                "submitted_at": "2026-04-21T00:00:00",
                "error_message": "OSS未启用，无法持久化生成视频",
            }
        },
    )

    class FakeAdapter:
        async def fetch(self, request, task_id):
            return VideoStatusResult(
                status="SUCCEEDED",
                video_url=provider_video_url,
                request_id="provider-req-2",
                raw_output={"task_status": "SUCCEEDED"},
            )

    async def fake_ensure_video_persisted(url, project_id="", strict=False, max_retries=3):
        if strict:
            raise RuntimeError("OSS未启用，无法持久化生成视频")
        return url

    async def fake_extract_thumbnail(video_url, project_id):
        raise RuntimeError("OSS未启用，无法生成缩略图")

    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())
    monkeypatch.setattr(video_studio_router.oss_service, "should_persist_generated_url", lambda url: True)
    monkeypatch.setattr(video_studio_router.oss_service, "is_enabled", lambda: False)
    monkeypatch.setattr(video_studio_router.oss_service, "ensure_video_persisted_async", fake_ensure_video_persisted)
    monkeypatch.setattr(video_studio_router, "_extract_video_thumbnail_to_oss", fake_extract_thumbnail)

    saved_tasks = []
    monkeypatch.setattr(video_studio_router.storage_service, "save_video_studio_task", lambda next_task: saved_tasks.append(next_task.model_copy(deep=True)))

    updated = await video_studio_router._reconcile_video_task_once(task)

    assert updated.status == "succeeded"
    assert updated.video_urls == [provider_video_url]
    assert updated.selected_video_url == provider_video_url
    assert updated.thumbnail_url is None
    assert updated.error_message is None
    assert updated.provider_result_meta["provider-task-1"]["error_message"] is None
    assert saved_tasks


@pytest.mark.asyncio
async def test_dashscope_generic_video_status_keeps_provider_url_when_oss_disabled(monkeypatch):
    provider_video_url = "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/result.mp4"

    class FakeResponse:
        def json(self):
            return {
                "request_id": "provider-req-1",
                "output": {
                    "task_status": "SUCCEEDED",
                    "video_url": provider_video_url,
                },
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.services.video_adapters.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("app.services.video_adapters.oss_service.is_enabled", lambda: False)

    service = DashScopeGenericVideoService("wan")
    result = await service.get_task_status("provider-task-1", "p1")

    assert result.status == "SUCCEEDED"
    assert result.video_url == provider_video_url
    assert result.request_id == "provider-req-1"
    assert result.error_message is None


@pytest.mark.asyncio
async def test_start_pending_video_task_reconcilers_only_recovers_processing_tasks(monkeypatch, client, registered_user, auth_header):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    processing_task = VideoStudioTask(
        project_id=project_id,
        name="处理中任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        task_ids=["provider-task-1"],
    )
    completed_task = VideoStudioTask(
        project_id=project_id,
        name="已完成任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="succeeded",
        task_ids=["provider-task-2"],
    )
    pending_without_provider_task = VideoStudioTask(
        project_id=project_id,
        name="未提交任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        task_ids=[],
    )
    user_storage.save_video_studio_task(processing_task)
    user_storage.save_video_studio_task(completed_task)
    user_storage.save_video_studio_task(pending_without_provider_task)

    dispatched = []

    def fake_dispatch(task, user_id, user_config_dir):
        dispatched.append((task.id, user_id, user_config_dir, task.submit_attempt_id))
        return {"dispatcher": "celery", "task_id": "celery-video-recovery"}

    monkeypatch.setattr(
        video_studio_router,
        "_dispatch_video_background_submit",
        fake_dispatch,
    )

    await video_studio_router.start_pending_video_task_reconcilers()

    assert len(dispatched) == 1
    assert dispatched[0][0] == processing_task.id
    assert dispatched[0][1] == user["id"]
    assert dispatched[0][3]
    recovered = user_storage.get_video_studio_task(processing_task.id)
    assert recovered.provider_result_meta["worker_attempt"]["status"] == "recovering"
    assert recovered.provider_result_meta["worker_attempt"]["celery_task_id"] == "celery-video-recovery"


def test_create_task_dispatches_video_worker_attempt(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    dispatched = []

    def fake_dispatch(task, user_id, user_config_dir):
        dispatched.append((task.id, task.submit_attempt_id, user_id, user_config_dir))
        return {"dispatcher": "celery", "task_id": "celery-video-1"}

    monkeypatch.setattr(video_studio_router, "_dispatch_video_background_submit", fake_dispatch)

    resp = client.post(
        "/api/video-studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "视频 worker 入队",
            "task_kind": "text_to_video",
            "provider": "wan",
            "model_id": "wan2.7-t2v",
            "model": "wan2.7-t2v",
            "prompt": "机械臂在仓库中巡视",
            "normalized_params": {
                "resolution": "720P",
                "ratio": "16:9",
                "duration": 5,
                "prompt_extend": False,
            },
            "group_count": 1,
        },
    )

    assert resp.status_code == 200
    task = resp.json()["task"]
    attempt = task["provider_result_meta"]["worker_attempt"]
    assert task["status"] == "processing"
    assert task["submit_state"] == "submitting"
    assert task["submit_attempt_id"]
    assert attempt["attempt_id"] == task["submit_attempt_id"]
    assert attempt["status"] == "queued"
    assert attempt["dispatcher"] == "celery"
    assert attempt["celery_task_id"] == "celery-video-1"
    assert len(dispatched) == 1
    assert dispatched[0][0] == task["id"]
    assert dispatched[0][1] == task["submit_attempt_id"]


def test_stale_video_submit_without_provider_task_is_failed_on_get(client, auth_header, registered_user, monkeypatch):
    monkeypatch.setenv("MIEMIE_VIDEO_STUDIO_SUBMIT_STALE_AFTER_SECONDS", "30")
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    old_time = datetime.now() - timedelta(minutes=5)
    task = VideoStudioTask(
        project_id=project_id,
        name="提交阶段 stale",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        submit_state="submitting",
        submit_started_at=old_time,
        submit_attempt_id="video-submit-old",
        provider_result_meta={
            "worker_attempt": {
                "attempt_id": "video-submit-old",
                "status": "running",
                "heartbeat_at": old_time.isoformat(),
            }
        },
    )
    user_storage.save_video_studio_task(task)

    resp = client.get(f"/api/video-studio/{task.id}", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["submit_state"] == "failed"
    assert data["provider_result_meta"]["submit_error"]["error_code"] == "SubmitTimeout"
    assert data["provider_result_meta"]["worker_attempt"]["failure_reason"] == "submit_timeout"


def test_stale_video_worker_with_provider_task_dispatches_recovery(client, auth_header, registered_user, monkeypatch):
    monkeypatch.setenv("MIEMIE_VIDEO_STUDIO_WORKER_STALE_SECONDS", "30")
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    old_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    task = VideoStudioTask(
        project_id=project_id,
        name="worker stale recovery",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        status="processing",
        task_ids=["provider-task-1"],
        submit_state="submitted",
        submit_attempt_id="attempt-video-current",
        provider_result_meta={
            "worker_attempt": {
                "attempt_id": "attempt-video-current",
                "status": "running",
                "heartbeat_at": old_time,
            }
        },
    )
    user_storage.save_video_studio_task(task)
    dispatched = []

    def fake_dispatch(task, user_id, user_config_dir):
        dispatched.append((task.id, task.task_ids, task.submit_attempt_id, user_id, user_config_dir))
        return {"dispatcher": "celery", "task_id": "celery-video-recover-1"}

    monkeypatch.setattr(video_studio_router, "_dispatch_video_background_submit", fake_dispatch)

    resp = client.get(f"/api/video-studio/{task.id}", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()
    attempt = data["provider_result_meta"]["worker_attempt"]
    assert data["status"] == "processing"
    assert data["task_ids"] == ["provider-task-1"]
    assert len(dispatched) == 1
    assert dispatched[0][1] == ["provider-task-1"]
    assert attempt["status"] == "recovering"
    assert attempt["celery_task_id"] == "celery-video-recover-1"


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
    user_storage = get_user_storage(user["id"])

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
    user_storage.save_video_studio_task(task)

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
    video_studio_router._begin_video_submit_attempt(task)
    get_user_storage(user["id"]).save_video_studio_task(task)
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
            )

    monkeypatch.setattr(video_studio_router, "get_video_adapter", lambda provider: FakeAdapter())

    await video_studio_router._background_create_video_tasks(task, normalized, user["id"], None)

    saved = get_user_storage(user["id"]).get_video_studio_task(task.id)
    assert saved.status == "failed"
    assert saved.error_message == "Model.AccessDenied - Model access denied."
    assert saved.request_ids == ["req-denied-1"]
    assert saved.provider_payload_snapshot == provider_payload
    submit_meta = saved.provider_result_meta["submit_error"]
    worker_attempt = saved.provider_result_meta["worker_attempt"]
    assert saved.submit_state == "failed"
    assert worker_attempt["attempt_id"] == task.submit_attempt_id
    assert worker_attempt["status"] == "failed"
    assert submit_meta["provider"] == "happyhorse"
    assert submit_meta["key_profile"] == "test"
    assert submit_meta["request_id"] == "req-denied-1"
    assert submit_meta["error_code"] == "Model.AccessDenied"
    assert submit_meta["raw_response"]["details"]["model"] == "happyhorse-1.0-t2v"


@pytest.mark.asyncio
async def test_background_submit_ignores_stale_attempt(registered_user, monkeypatch):
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="旧 attempt 不覆盖",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        normalized_params={"resolution": "720P", "ratio": "16:9", "duration": 5},
        input_assets={},
        status="processing",
        submit_state="submitting",
        submit_attempt_id="current-attempt",
        provider_result_meta={"worker_attempt": {"attempt_id": "current-attempt", "status": "queued"}},
    )
    user_storage.save_video_studio_task(task)

    async def fail_submit(*args, **kwargs):
        raise AssertionError("stale attempt should not submit provider task")

    monkeypatch.setattr(video_studio_router, "_submit_api_tasks", fail_submit)

    normalized = NormalizedVideoTaskRequest(
        project_id="p1",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        prompt=task.prompt,
        normalized_params=task.normalized_params,
    )

    await video_studio_router._background_create_video_tasks(
        task,
        normalized,
        user["id"],
        None,
        "old-attempt",
    )

    latest = user_storage.get_video_studio_task(task.id)
    assert latest.status == "processing"
    assert latest.submit_attempt_id == "current-attempt"
    assert latest.task_ids == []
    assert latest.provider_result_meta["worker_attempt"]["status"] == "queued"


@pytest.mark.asyncio
async def test_deleted_video_task_is_not_resurrected_by_worker(registered_user, monkeypatch):
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
    task = VideoStudioTask(
        project_id="p1",
        name="已删除任务",
        task_type="text_to_video",
        task_kind="text_to_video",
        provider="wan",
        model_id="wan2.7-t2v",
        model="wan2.7-t2v",
        prompt="机械臂巡视仓库",
        normalized_params={"resolution": "720P", "ratio": "16:9", "duration": 5},
        input_assets={},
        status="processing",
        submit_state="submitting",
        submit_attempt_id="deleted-attempt",
    )
    user_storage.save_video_studio_task(task)
    user_storage.delete_video_studio_task(task.id)

    def fail_get_adapter(provider):
        raise AssertionError("deleted task should not reach provider adapter")

    monkeypatch.setattr(video_studio_router, "get_video_adapter", fail_get_adapter)

    await video_studio_router._background_create_video_tasks_by_id(
        task.id,
        user["id"],
        None,
        "deleted-attempt",
    )

    assert user_storage.get_video_studio_task(task.id) is None


def test_get_failed_submit_task_backfills_developer_error_meta(client, auth_header, registered_user):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
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
    user_storage.save_video_studio_task(task)

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
    user_storage = get_user_storage(user["id"])
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
    user_storage.save_video_studio_task(task)

    resp = client.get(f"/api/video-studio/{task.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload_snapshot"]["model"] == "wan2.6-t2v"
    assert data["request_ids"] == ["req-from-meta"]


def test_regenerate_legacy_video_edit_task_uses_canonical_mapping(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    user_storage = get_user_storage(user["id"])
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
    user_storage.save_video_studio_task(task)

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
    assert t2v_params == {"resolution", "ratio", "duration", "watermark", "seed"}
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
    assert i2v_params == {"resolution", "duration", "watermark", "seed"}
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
    assert r2v_params == {"resolution", "ratio", "duration", "watermark", "seed"}
    assert r2v_profile["ui_hints"]["max_reference_images"] == 9
    assert r2v_profile["ui_hints"]["max_reference_videos"] == 0
    assert "[Image 1]" in r2v_profile["ui_hints"]["prompt_help"]["notes"][0]
    assert "[Image 2]" in r2v_profile["ui_hints"]["prompt_help"]["how_to_choose"][0]

    video_edit_model = models["happyhorse-1.0-video-edit"]
    assert video_edit_model["provider"] == "happyhorse"
    assert video_edit_model["supported_task_kinds"] == ["video_edit_global"]
    video_edit_profile = video_edit_model["task_profiles"]["video_edit_global"]
    assert video_edit_profile["input_roles"] == ["base_video", "reference_image"]
    video_edit_params = {item["name"] for item in video_edit_profile["parameters"]}
    assert video_edit_params == {"resolution", "watermark", "audio_setting", "seed"}
    assert video_edit_profile["ui_hints"]["max_reference_images"] == 5
    assert video_edit_profile["ui_hints"]["max_reference_videos"] == 0


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
        },
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
