import pytest

from app.routers import video_benchmark as video_benchmark_router
from app.services import video_benchmark_runtime
from app.services.storage import get_current_user_id, set_current_user, storage_service
from app.services.video_adapters import VideoStatusResult, VideoSubmitResult


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "视频测评项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(video_benchmark_router.asyncio, "create_task", fake_create_task)


def _first_frame_payload(project_id: str, *, duration=None):
    item = {
        "name": "首帧样例",
        "prompt": "让画面中的主体自然转身，镜头稳定",
        "negative_prompt": "模糊",
        "tags": ["首帧"],
        "first_frame": {
            "url": "https://oss.example.com/first-frame.png",
            "name": "首帧.png",
        },
    }
    if duration is not None:
        item["duration"] = duration
    return {
        "project_id": project_id,
        "name": "首帧视频数据集",
        "description": "用于首帧生视频测评",
        "items": [item],
    }


class FakeVideoAdapter:
    provider = "wan"

    async def validate(self, request):
        if request.model_id == "wan2.2-s2v" and not (request.input_assets.get("audio") or []):
            raise ValueError("数字人模型需要驱动音频")
        duration = int(request.normalized_params.get("duration") or 0)
        if request.model_id == "wan2.7-i2v" and duration > 15:
            raise ValueError("wan2.7 图生视频时长需在2到15秒之间")

    def build_provider_payload(self, request, seed_offset=0):
        params = dict(request.normalized_params)
        if params.get("seed") is not None:
            params["seed"] = int(params["seed"]) + seed_offset
        return {
            "model": request.model_id,
            "input": {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "media": [
                    {
                        "type": "first_frame",
                        "url": (request.input_assets.get("first_frame") or [None])[0],
                    }
                ],
            },
            "parameters": params,
        }

    async def submit(self, request, seed_offset=0):
        return VideoSubmitResult(
            task_id=f"task-{request.model_id}-{request.normalized_params.get('duration')}-{seed_offset}",
            request_id=f"req-{request.model_id}-{seed_offset}",
            provider_payload=self.build_provider_payload(request, seed_offset),
            key_profile="test",
        )

    async def fetch(self, request, task_id):
        return VideoStatusResult(
            status="SUCCEEDED",
            video_url=f"https://oss.example.com/{task_id}.mp4",
            request_id=f"fetch-{task_id}",
            key_profile="test",
            usage={"duration": request.normalized_params.get("duration")},
            raw_output={"task_id": task_id},
        )


class PartialProgressVideoAdapter(FakeVideoAdapter):
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.partial_seen = False

    async def fetch(self, request, task_id):
        if task_id.endswith("-1"):
            run = storage_service.get_video_benchmark_run(self.run_id)
            cell = run.cell_results[0]
            self.partial_seen = (
                run.status == "running"
                and cell.status == "running"
                and [video.url for video in cell.output_videos] == [
                    "https://oss.example.com/task-wan2.7-i2v-8-0.mp4"
                ]
            )
        return await super().fetch(request, task_id)


class PartialFailureVideoAdapter(FakeVideoAdapter):
    async def fetch(self, request, task_id):
        if task_id.endswith("-1"):
            return VideoStatusResult(
                status="FAILED",
                request_id=f"fetch-{task_id}",
                key_profile="test",
                error_code="MockFailure",
                error_message="第二条视频失败",
                raw_output={"task_id": task_id},
            )
        return await super().fetch(request, task_id)


@pytest.mark.asyncio
async def test_video_benchmark_capabilities_only_include_image_to_video_models():
    capabilities = await video_benchmark_runtime.get_video_benchmark_capabilities()

    assert capabilities["task_kinds"] == [{"id": "image_to_video", "label": "首帧生视频"}]
    assert "wan2.7-i2v" in capabilities["models"]
    assert "kling/kling-v3-video-generation" in capabilities["models"]
    assert "vidu/viduq3-turbo_img2video" in capabilities["models"]
    assert "wan2.7-t2v" not in capabilities["models"]
    assert set(capabilities["models"]["wan2.7-i2v"]["supported_task_kinds"]) == {"image_to_video"}
    assert capabilities["models"]["wan2.7-i2v"]["task_profiles"]["image_to_video"]["parameters"]
    group_count_param = next(
        param
        for param in capabilities["models"]["wan2.7-i2v"]["configurable_parameters"]
        if param["name"] == "group_count"
    )
    assert group_count_param["label"] == "生成数量"
    assert group_count_param["default"] == 1
    assert group_count_param["constraint"]["max_value"] == 5
    kling_group_count_param = next(
        param
        for param in capabilities["models"]["kling/kling-v3-video-generation"]["configurable_parameters"]
        if param["name"] == "group_count"
    )
    assert kling_group_count_param["constraint"]["max_value"] == 10


def test_dataset_create_export_and_import_preserves_case_duration(client, auth_header):
    project_id = _create_project(client, auth_header)

    create_resp = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=6),
    )

    assert create_resp.status_code == 200
    dataset = create_resp.json()["dataset"]
    assert dataset["task_kind"] == "image_to_video"
    assert dataset["schema_version"] == "1.0"
    assert dataset["items"][0]["duration"] == 6
    assert dataset["items"][0]["first_frame"]["url"] == "https://oss.example.com/first-frame.png"

    export_resp = client.get(f"/api/video-benchmark/datasets/{dataset['id']}/export", headers=auth_header)
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["type"] == "video_benchmark_dataset"
    assert exported["items"][0]["duration"] == 6

    import_resp = client.post(
        "/api/video-benchmark/datasets/import",
        headers=auth_header,
        json={"project_id": project_id, "data": exported, "name": "导入视频数据集"},
    )
    assert import_resp.status_code == 200
    imported = import_resp.json()["dataset"]
    assert imported["name"] == "导入视频数据集"
    assert imported["items"][0]["duration"] == 6


def test_dataset_allows_missing_first_frame_and_reports_blocking_issue(client, auth_header):
    project_id = _create_project(client, auth_header)

    resp = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "缺首帧数据集",
            "items": [{"name": "坏样例", "prompt": "动起来"}],
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["dataset"]["items"][0]["first_frame"] is None
    assert payload["warnings"][0]["missing_fields"] == ["first_frame"]
    assert "首帧" in payload["blocking_issues"][0]["message"]


def test_run_suite_blocks_dataset_items_without_first_frame(client, auth_header, monkeypatch):
    _patch_async_create_task(monkeypatch)
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "缺首帧数据集",
            "items": [{"name": "坏样例", "prompt": "动起来"}],
        },
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "缺首帧测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
        },
    ).json()["suite"]

    resp = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header)

    assert resp.status_code == 400
    body = resp.json()
    assert "缺首帧" in body["detail"]
    assert body["blocking_issues"][0]["item_id"] == dataset["items"][0]["id"]
    assert body["blocking_issues"][0]["missing_fields"] == ["first_frame"]
    suite_after = client.get(f"/api/video-benchmark/suites/{suite['id']}", headers=auth_header).json()["suite"]
    assert suite_after["latest_run_id"] is None


def test_preview_cell_blocks_missing_first_frame(client, auth_header):
    project_id = _create_project(client, auth_header)

    resp = client.post(
        "/api/video-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "model_id": "wan2.7-i2v",
            "case_data": {
                "name": "缺首帧样例",
                "prompt": "动起来",
            },
            "baseline_params": {"duration": 5, "resolution": "720P"},
        },
    )

    assert resp.status_code == 400
    assert "首帧" in resp.json()["detail"]


def test_create_suite_rejects_models_without_image_to_video_support(client, auth_header):
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id),
    ).json()["dataset"]

    resp = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "非法模型测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-t2v"],
        },
    )

    assert resp.status_code == 400
    assert "不支持首帧生视频" in resp.json()["detail"]


def test_preview_cell_builds_wan_kling_and_vidu_payloads(client, auth_header, monkeypatch):
    async def fake_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 768,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)
    project_id = _create_project(client, auth_header)
    case_data = _first_frame_payload(project_id, duration=4)["items"][0]

    for model_id in [
        "wan2.7-i2v",
        "kling/kling-v3-video-generation",
        "vidu/viduq3-turbo_img2video",
    ]:
        resp = client.post(
            "/api/video-benchmark/preview-cell",
            headers=auth_header,
            json={
                "project_id": project_id,
                "model_id": model_id,
                "case_data": case_data,
                "baseline_params": {"duration": 5, "resolution": "720P", "watermark": False},
                "override_params": {"duration": 6},
            },
        )
        assert resp.status_code == 200
        payload = resp.json()["provider_payload"]
        assert payload["model"] == model_id
        assert payload["parameters"]["duration"] == 4
        assert "group_count" not in payload["parameters"]
        assert resp.json()["effective_params"]["duration"] == 4
        assert "media" in payload["input"]


def test_preview_cell_exposes_group_count_as_benchmark_parameter(client, auth_header, monkeypatch):
    async def fake_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 768,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)
    project_id = _create_project(client, auth_header)
    case_data = _first_frame_payload(project_id, duration=4)["items"][0]

    resp = client.post(
        "/api/video-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "model_id": "wan2.7-i2v",
            "case_data": case_data,
            "baseline_params": {"duration": 5, "resolution": "720P", "group_count": 2},
            "override_params": {"group_count": 3},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["effective_params"]["group_count"] == 3
    assert body["canonical_request"]["normalized_params"]["group_count"] == 3
    assert "group_count" not in body["provider_payload"]["parameters"]


def test_preview_cell_rejects_invalid_group_count(client, auth_header, monkeypatch):
    async def fake_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 768,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.services.video_adapters.inspect_remote_image", fake_inspect_remote_image)
    project_id = _create_project(client, auth_header)
    case_data = _first_frame_payload(project_id, duration=4)["items"][0]

    resp = client.post(
        "/api/video-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "model_id": "wan2.7-i2v",
            "case_data": case_data,
            "baseline_params": {"duration": 5, "resolution": "720P", "group_count": 6},
        },
    )

    assert resp.status_code == 400
    assert "生成数量" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_suite_saves_video_results_and_case_duration_override(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(video_benchmark_runtime, "get_video_adapter", lambda _provider: FakeVideoAdapter())
    monkeypatch.setattr(video_benchmark_runtime.oss_service, "should_persist_generated_url", lambda _url: False)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=8),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "首帧测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
            "baseline_params": {"duration": 5, "resolution": "720P", "watermark": False},
            "model_overrides": {"wan2.7-i2v": {"duration": 6, "seed": 123, "group_count": 3}},
        },
    ).json()["suite"]

    run_resp = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run"]["id"]
    assert run_resp.json()["run"]["cell_results"][0]["status"] == "pending"
    assert run_resp.json()["run"]["stats"]["pending_count"] == 1

    await video_benchmark_router._background_run_suite(run_id, suite["id"], user["id"], None)

    set_current_user(user["id"])
    try:
        run = storage_service.get_video_benchmark_run(run_id)
    finally:
        set_current_user(None)

    assert run.status == "completed"
    assert run.stats["success_count"] == 1
    assert run.cell_results[0].effective_params["duration"] == 8
    assert run.cell_results[0].effective_params["seed"] == 123
    assert run.cell_results[0].effective_params["group_count"] == 3
    assert run.cell_results[0].provider_payload["parameters"]["duration"] == 8
    assert "group_count" not in run.cell_results[0].provider_payload["parameters"]
    assert run.cell_results[0].task_ids == [
        "task-wan2.7-i2v-8-0",
        "task-wan2.7-i2v-8-1",
        "task-wan2.7-i2v-8-2",
    ]
    assert run.cell_results[0].request_ids == [
        "req-wan2.7-i2v-0",
        "req-wan2.7-i2v-1",
        "req-wan2.7-i2v-2",
        "fetch-task-wan2.7-i2v-8-0",
        "fetch-task-wan2.7-i2v-8-1",
        "fetch-task-wan2.7-i2v-8-2",
    ]
    assert [video.url for video in run.cell_results[0].output_videos] == [
        "https://oss.example.com/task-wan2.7-i2v-8-0.mp4",
        "https://oss.example.com/task-wan2.7-i2v-8-1.mp4",
        "https://oss.example.com/task-wan2.7-i2v-8-2.mp4",
    ]
    assert run.cell_results[0].provider_result_meta["usage"]["duration"] == 8
    assert run.cell_results[0].provider_result_meta["group_count"] == 3
    assert run.stats["pending_count"] == 0
    assert run.stats["running_count"] == 0
    assert run.stats["completed_count"] == 1


@pytest.mark.asyncio
async def test_video_benchmark_persists_each_output_while_cell_is_running(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=8),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "首帧实时测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
            "model_overrides": {"wan2.7-i2v": {"duration": 8, "group_count": 3}},
        },
    ).json()["suite"]
    run_resp = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header)
    run_id = run_resp.json()["run"]["id"]
    adapter = PartialProgressVideoAdapter(run_id)
    monkeypatch.setattr(video_benchmark_runtime, "get_video_adapter", lambda _provider: adapter)
    monkeypatch.setattr(video_benchmark_runtime.oss_service, "should_persist_generated_url", lambda _url: False)

    await video_benchmark_router._background_run_suite(run_id, suite["id"], user["id"], None)

    set_current_user(user["id"])
    try:
        run = storage_service.get_video_benchmark_run(run_id)
    finally:
        set_current_user(None)

    assert adapter.partial_seen is True
    assert run.status == "completed"
    assert len(run.cell_results[0].output_videos) == 3


@pytest.mark.asyncio
async def test_video_benchmark_keeps_partial_outputs_when_later_group_fails(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(video_benchmark_runtime, "get_video_adapter", lambda _provider: PartialFailureVideoAdapter())
    monkeypatch.setattr(video_benchmark_runtime.oss_service, "should_persist_generated_url", lambda _url: False)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=8),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "部分失败测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
            "model_overrides": {"wan2.7-i2v": {"duration": 8, "group_count": 3}},
        },
    ).json()["suite"]
    run_resp = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header)
    run_id = run_resp.json()["run"]["id"]

    await video_benchmark_router._background_run_suite(run_id, suite["id"], user["id"], None)

    set_current_user(user["id"])
    try:
        run = storage_service.get_video_benchmark_run(run_id)
    finally:
        set_current_user(None)

    cell = run.cell_results[0]
    assert cell.status == "failed"
    assert cell.error_message == "第二条视频失败"
    assert [video.url for video in cell.output_videos] == [
        "https://oss.example.com/task-wan2.7-i2v-8-0.mp4"
    ]


@pytest.mark.asyncio
async def test_case_duration_invalid_for_one_model_marks_unsupported_without_blocking_others(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(video_benchmark_runtime, "get_video_adapter", lambda _provider: FakeVideoAdapter())
    monkeypatch.setattr(video_benchmark_runtime.oss_service, "should_persist_generated_url", lambda _url: False)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=20),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "混合结果测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v", "vidu/viduq3-turbo_img2video"],
            "baseline_params": {"duration": 5, "resolution": "720P"},
        },
    ).json()["suite"]

    run_resp = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run"]["id"]

    await video_benchmark_router._background_run_suite(run_id, suite["id"], user["id"], None)

    set_current_user(user["id"])
    try:
        run = storage_service.get_video_benchmark_run(run_id)
    finally:
        set_current_user(None)

    cells = {cell.model_id: cell for cell in run.cell_results}
    assert cells["wan2.7-i2v"].status == "unsupported"
    assert cells["wan2.7-i2v"].effective_params["duration"] == 20
    assert cells["wan2.7-i2v"].canonical_request["model_id"] == "wan2.7-i2v"
    assert cells["vidu/viduq3-turbo_img2video"].status == "completed"
    assert run.status == "completed"
    assert run.stats["success_count"] == 1
    assert run.stats["unsupported_count"] == 1


@pytest.mark.asyncio
async def test_retry_failures_only_retries_failed_and_unsupported_cells(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(video_benchmark_runtime, "get_video_adapter", lambda _provider: FakeVideoAdapter())
    monkeypatch.setattr(video_benchmark_runtime.oss_service, "should_persist_generated_url", lambda _url: False)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=20),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "重试测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v", "vidu/viduq3-turbo_img2video"],
            "baseline_params": {"duration": 5, "resolution": "720P"},
        },
    ).json()["suite"]
    first_run = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header).json()["run"]
    await video_benchmark_router._background_run_suite(first_run["id"], suite["id"], user["id"], None)

    retry_resp = client.post(f"/api/video-benchmark/runs/{first_run['id']}/retry-failures", headers=auth_header)
    assert retry_resp.status_code == 200
    retry_run = retry_resp.json()["run"]
    assert retry_run["retry_source_run_id"] == first_run["id"]
    assert retry_run["retry_targets"] == [{"case_id": dataset["items"][0]["id"], "model_id": "wan2.7-i2v"}]


def test_export_reports_include_video_urls_without_inline_assets(client, auth_header, registered_user):
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=6),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "报告测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
            "baseline_params": {"duration": 6, "resolution": "720P"},
        },
    ).json()["suite"]

    from app.models.video_benchmark import VideoBenchmarkCellResult, VideoBenchmarkOutputVideo, VideoBenchmarkRun

    set_current_user(user["id"])
    try:
        run = VideoBenchmarkRun(
            suite_id=suite["id"],
            project_id=project_id,
            dataset_id=dataset["id"],
            status="completed",
            dataset_snapshot=dataset,
            model_snapshots=[{"id": "wan2.7-i2v", "name": "万相 2.7 图生视频"}],
            cell_results=[
                VideoBenchmarkCellResult(
                    case_id=dataset["items"][0]["id"],
                    case_name="首帧样例",
                    model_id="wan2.7-i2v",
                    model_name="万相 2.7 图生视频",
                    status="completed",
                    output_videos=[VideoBenchmarkOutputVideo(url="https://oss.example.com/output.mp4")],
                    effective_params={"duration": 6},
                )
            ],
            stats={"success_count": 1},
        )
        storage_service.save_video_benchmark_run(run)
    finally:
        set_current_user(None)

    md_resp = client.post(f"/api/video-benchmark/runs/{run.id}/export-md-file", headers=auth_header)
    assert md_resp.status_code == 200
    assert "https://oss.example.com/output.mp4" in md_resp.text
    assert "data:video" not in md_resp.text

    html_resp = client.post(f"/api/video-benchmark/runs/{run.id}/export-html-file", headers=auth_header)
    assert html_resp.status_code == 200
    assert "<video controls preload=\"metadata\"" in html_resp.text
    assert "https://oss.example.com/output.mp4" in html_resp.text


def test_delete_project_cleans_video_benchmark_artifacts(client, auth_header, registered_user, monkeypatch):
    _patch_async_create_task(monkeypatch)
    _token, user = registered_user
    project_id = _create_project(client, auth_header)
    dataset = client.post(
        "/api/video-benchmark/datasets",
        headers=auth_header,
        json=_first_frame_payload(project_id, duration=6),
    ).json()["dataset"]
    suite = client.post(
        "/api/video-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "级联删除测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-i2v"],
            "baseline_params": {"duration": 6, "resolution": "720P"},
        },
    ).json()["suite"]
    run = client.post(f"/api/video-benchmark/suites/{suite['id']}/run", headers=auth_header).json()["run"]

    delete_resp = client.delete(f"/api/projects/{project_id}", headers=auth_header)

    assert delete_resp.status_code == 200
    set_current_user(user["id"])
    try:
        assert storage_service.get_video_benchmark_dataset(dataset["id"]) is None
        assert storage_service.get_video_benchmark_suite(suite["id"]) is None
        assert storage_service.get_video_benchmark_run(run["id"]) is None
        assert storage_service.get_video_benchmark_datasets(project_id) == []
        assert storage_service.get_video_benchmark_suites(project_id) == []
        assert storage_service.get_video_benchmark_runs_by_project(project_id) == []
    finally:
        set_current_user(None)
