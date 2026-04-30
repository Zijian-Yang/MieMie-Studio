import asyncio

import pytest

from app.models.image_benchmark import ImageBenchmarkCellResult, ImageBenchmarkOutputImage, ImageBenchmarkRun
from app.routers import image_benchmark as image_benchmark_router
from app.services import image_benchmark_runtime
from app.services.storage import set_current_user, storage_service


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "图片测评项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(image_benchmark_router.asyncio, "create_task", fake_create_task)


def _create_suite_with_public_run(client, auth_header, user_id: str):
    project_id = _create_project(client, auth_header)
    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "公开分享数据集",
            "task_kind": "text_to_image",
            "items": [{"name": "样例1", "prompt": "一张海报", "negative_prompt": "", "tags": []}],
        },
    )
    assert dataset_resp.status_code == 200
    dataset = dataset_resp.json()["dataset"]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "公开分享测评",
            "description": "给外部查看",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-image-pro"],
            "baseline_params": {"n": 1},
        },
    )
    assert suite_resp.status_code == 200
    suite = suite_resp.json()["suite"]

    set_current_user(user_id)
    try:
        run = ImageBenchmarkRun(
            suite_id=suite["id"],
            project_id=project_id,
            dataset_id=dataset["id"],
            task_kind="text_to_image",
            status="completed",
            dataset_snapshot=dataset,
            model_snapshots=[{"id": "wan2.7-image-pro", "name": "万相 2.7 Image Pro"}],
            cell_results=[
                ImageBenchmarkCellResult(
                    case_id=dataset["items"][0]["id"],
                    case_name="样例1",
                    model_id="wan2.7-image-pro",
                    model_name="万相 2.7 Image Pro",
                    status="completed",
                    output_images=[ImageBenchmarkOutputImage(url="https://oss.example.com/output.png", prompt_used="一张海报")],
                    request_ids=["req-secret"],
                    task_ids=["task-secret"],
                    canonical_request={"secret": "canonical"},
                    provider_payload={"secret": "provider"},
                    effective_params={"n": 1},
                )
            ],
            stats={"case_count": 1, "model_count": 1, "success_count": 1, "failure_count": 0},
        )
        storage_service.save_image_benchmark_run(run)
        stored_suite = storage_service.get_image_benchmark_suite(suite["id"])
        stored_suite.latest_run_id = run.id
        stored_suite.status = "completed"
        storage_service.save_image_benchmark_suite(stored_suite)
    finally:
        set_current_user(None)

    return suite, run


def test_dataset_create_export_and_import_with_new_schema(client, auth_header):
    project_id = _create_project(client, auth_header)

    create_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "海报文生图集",
            "description": "文生图数据集",
            "task_kind": "text_to_image",
            "items": [
                {"name": "样例1", "prompt": "电影感海报", "negative_prompt": "模糊", "tags": ["海报"]},
                {"name": "样例2", "prompt": "机甲角色立绘", "negative_prompt": "", "tags": ["角色"]},
            ],
        },
    )
    assert create_resp.status_code == 200
    dataset = create_resp.json()["dataset"]
    assert dataset["task_kind"] == "text_to_image"
    assert dataset["schema_version"] == "2.0"
    assert dataset["max_image_slot_index"] == 0

    export_resp = client.get(f"/api/image-benchmark/datasets/{dataset['id']}/export", headers=auth_header)
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["type"] == "image_benchmark_dataset"
    assert exported["task_kind"] == "text_to_image"
    assert exported["max_image_slot_index"] == 0
    assert "image_slots" in exported["items"][0]

    import_resp = client.post(
        "/api/image-benchmark/datasets/import",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "导入副本",
            "data": exported,
        },
    )
    assert import_resp.status_code == 200
    imported = import_resp.json()["dataset"]
    assert imported["name"] == "导入副本"
    assert imported["items"][0]["prompt"] == "电影感海报"


@pytest.mark.asyncio
async def test_image_benchmark_capabilities_include_seedream_without_sequential(auth_header):
    capabilities = await image_benchmark_runtime.get_image_benchmark_capabilities()

    assert "doubao-seedream-5.0-lite" in capabilities["models"]
    assert "doubao-seedream-4.5" in capabilities["models"]
    assert capabilities["models"]["doubao-seedream-5.0-lite"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
    ]
    assert "sequential_generation" not in capabilities["models"]["doubao-seedream-4.5"]["supported_task_kinds"]


@pytest.mark.asyncio
async def test_image_benchmark_capabilities_include_nano_banana_models(auth_header):
    capabilities = await image_benchmark_runtime.get_image_benchmark_capabilities()

    assert "nano-banana-2" in capabilities["models"]
    assert "nano-banana-pro" in capabilities["models"]
    assert capabilities["models"]["nano-banana-2"]["provider"] == "google"
    assert capabilities["models"]["nano-banana-pro"]["provider"] == "google"
    assert capabilities["models"]["nano-banana-2"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
    ]
    assert capabilities["models"]["nano-banana-pro"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
    ]
    params = {
        param["name"]
        for param in capabilities["models"]["nano-banana-2"]["configurable_parameters"]
    }
    assert {"aspect_ratio", "image_size", "google_search_mode", "thinking_level"}.issubset(params)
    assert "sequential_generation" not in capabilities["models"]["nano-banana-2"]["supported_task_kinds"]


@pytest.mark.asyncio
async def test_image_benchmark_executes_nano_banana_and_preserves_provider_meta(monkeypatch):
    from app.services.image_benchmark_runtime import _execute_benchmark_cell_once

    model_meta = {
        "id": "nano-banana-2",
        "name": "Nano Banana 2",
        "provider": "google",
        "supported_task_kinds": ["text_to_image", "image_edit"],
        "parameters": [
            {"name": "aspect_ratio", "default": "1:1"},
            {"name": "image_size", "default": "1K"},
            {"name": "google_search_mode", "default": "web"},
            {"name": "thinking_level", "default": "minimal"},
        ],
    }

    async def fake_generate_with_nano_banana_image(**kwargs):
        return (
            [image_benchmark_runtime.StudioTaskImage(group_index=0, url="https://oss.example.com/nano.png")],
            ["google-req-123"],
            {
                "google-req-123": {
                    "provider": "google",
                    "usage": {"totalTokenCount": 123},
                    "grounding_metadata": [{"groundingChunks": []}],
                    "grounding_source_links": [
                        {
                            "uri": "https://example.com/source",
                            "title": "Source",
                            "source_type": "web",
                            "image_uri": None,
                        }
                    ],
                    "raw_response": {"ok": True},
                }
            },
        )

    monkeypatch.setattr(
        "app.services.image_benchmark_runtime.studio_router.generate_with_nano_banana_image",
        fake_generate_with_nano_banana_image,
    )
    monkeypatch.setattr("app.services.image_benchmark_runtime.oss_service.is_enabled", lambda: False)

    result = await _execute_benchmark_cell_once(
        project_id="p1",
        task_kind="text_to_image",
        model_meta=model_meta,
        case_data={"id": "case-1", "name": "样例", "prompt": "生成海报"},
        effective_params={
            "aspect_ratio": "16:9",
            "image_size": "2K",
            "google_search_mode": "web",
            "thinking_level": "minimal",
        },
    )

    assert result.status == "completed"
    assert result.request_ids == ["google-req-123"]
    assert result.output_images[0].url == "https://oss.example.com/nano.png"
    assert result.provider_payload["model"] == "gemini-3.1-flash-image-preview"
    assert result.provider_payload["generationConfig"]["imageConfig"] == {
        "aspectRatio": "16:9",
        "imageSize": "2K",
    }
    assert result.provider_result_meta["google-req-123"]["provider"] == "google"
    assert result.provider_result_meta["google-req-123"]["usage"]["totalTokenCount"] == 123
    assert result.provider_result_meta["google-req-123"]["grounding_source_links"][0]["uri"] == "https://example.com/source"


def test_dataset_import_migrates_legacy_input_images_schema(client, auth_header):
    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/datasets/import",
        headers=auth_header,
        json={
            "project_id": project_id,
            "data": {
                "schema_version": "1.0",
                "type": "image_benchmark_dataset",
                "task_kind": "image_edit",
                "name": "旧版图片编辑集",
                "description": "",
                "items": [
                    {
                        "name": "旧样例",
                        "prompt": "旧 prompt",
                        "negative_prompt": "",
                        "tags": ["旧"],
                        "input_images": [
                            {"url": "https://oss.example.com/ref1.png", "name": "图1"},
                            {"url": "https://oss.example.com/ref2.png", "name": "图2"},
                        ],
                    }
                ],
            },
        },
    )
    assert resp.status_code == 200
    dataset = resp.json()["dataset"]
    assert dataset["max_image_slot_index"] == 2
    assert dataset["items"][0]["image_slots"][0]["position"] == 1
    assert dataset["items"][0]["image_slots"][1]["position"] == 2


def test_dataset_import_can_rehost_images_to_current_oss(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    upload_calls = []

    async def fake_upload_from_url_async(url, file_type="image", extension="png", project_id=""):
        upload_calls.append((url, file_type, extension, project_id))
        return True, url.replace("https://old.example.com", "https://new-oss.example.com")

    monkeypatch.setattr(image_benchmark_router.oss_service, "is_enabled", lambda: True)
    monkeypatch.setattr(image_benchmark_router.oss_service, "upload_from_url_async", fake_upload_from_url_async)

    resp = client.post(
        "/api/image-benchmark/datasets/import",
        headers=auth_header,
        json={
            "project_id": project_id,
            "migrate_images_to_oss": True,
            "data": {
                "schema_version": "2.0",
                "type": "image_benchmark_dataset",
                "task_kind": "image_edit",
                "name": "跨环境图片编辑集",
                "items": [
                    {
                        "name": "样例1",
                        "prompt": "把图2换成图1的人物",
                        "image_slots": [
                            {
                                "position": 1,
                                "image": {"url": "https://old.example.com/ref1.png", "name": "图1"},
                            },
                            {
                                "position": 2,
                                "image": {"url": "https://old.example.com/ref2.png", "name": "图2"},
                            },
                        ],
                    },
                    {
                        "name": "样例2",
                        "prompt": "复用第一张图",
                        "image_slots": [
                            {
                                "position": 1,
                                "image": {"url": "https://old.example.com/ref1.png", "name": "图1"},
                            },
                        ],
                    },
                ],
            },
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["migration_report"]["attempted"] == 2
    assert data["migration_report"]["succeeded"] == 2
    assert data["migration_report"]["failed"] == 0
    assert len(upload_calls) == 2
    first_item_slots = data["dataset"]["items"][0]["image_slots"]
    second_item_slots = data["dataset"]["items"][1]["image_slots"]
    assert first_item_slots[0]["image"]["url"] == "https://new-oss.example.com/ref1.png"
    assert first_item_slots[1]["image"]["url"] == "https://new-oss.example.com/ref2.png"
    assert second_item_slots[0]["image"]["url"] == "https://new-oss.example.com/ref1.png"


def test_dataset_export_and_import_preserves_interactive_bbox(client, auth_header):
    project_id = _create_project(client, auth_header)
    create_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "交互式编辑集",
            "task_kind": "interactive_edit",
            "items": [
                {
                    "name": "框选样例",
                    "prompt": "把图1的闹钟放到图2框选位置",
                    "image_slots": [
                        {"position": 1, "image": {"url": "https://oss.example.com/ref1.png", "name": "图1"}},
                        {"position": 2, "image": {"url": "https://oss.example.com/ref2.png", "name": "图2"}},
                    ],
                    "bbox_list": [[], [[10, 20, 100, 140]]],
                }
            ],
        },
    )
    assert create_resp.status_code == 200
    dataset = create_resp.json()["dataset"]
    assert dataset["task_kind"] == "interactive_edit"
    assert dataset["items"][0]["bbox_list"] == [[], [[10, 20, 100, 140]]]

    export_resp = client.get(f"/api/image-benchmark/datasets/{dataset['id']}/export", headers=auth_header)
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["items"][0]["bbox_list"] == [[], [[10, 20, 100, 140]]]

    import_resp = client.post(
        "/api/image-benchmark/datasets/import",
        headers=auth_header,
        json={"project_id": project_id, "data": exported, "name": "导入交互式编辑集"},
    )
    assert import_resp.status_code == 200
    imported = import_resp.json()["dataset"]
    assert imported["task_kind"] == "interactive_edit"
    assert imported["items"][0]["bbox_list"] == [[], [[10, 20, 100, 140]]]


def test_dataset_save_allows_sparse_slots_and_returns_warnings(client, auth_header):
    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "稀疏数据集",
            "task_kind": "image_edit",
            "max_image_slot_index": 3,
            "items": [
                {
                    "name": "样例1",
                    "prompt": "先填第2张和第3张图",
                    "image_slots": [
                        {"position": 2, "image": {"url": "https://oss.example.com/ref2.png", "name": "图2"}},
                        {"position": 3, "image": {"url": "https://oss.example.com/ref3.png", "name": "图3"}},
                    ],
                }
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["warnings"]
    assert data["warnings"][0]["missing_positions"] == [1]
    assert data["dataset"]["items"][0]["image_slots"][0]["position"] == 2
    assert data["dataset"]["items"][0]["image_slots"][1]["position"] == 3


def test_validate_and_run_block_when_dataset_has_slot_gaps(client, auth_header):
    project_id = _create_project(client, auth_header)
    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "阻止运行数据集",
            "task_kind": "image_edit",
            "max_image_slot_index": 3,
            "items": [
                {
                    "name": "样例1",
                    "prompt": "缺少第一张图",
                    "image_slots": [
                        {"position": 2, "image": {"url": "https://oss.example.com/ref2.png", "name": "图2"}},
                        {"position": 3, "image": {"url": "https://oss.example.com/ref3.png", "name": "图3"}},
                    ],
                }
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]

    validate_resp = client.post(f"/api/image-benchmark/datasets/{dataset['id']}/validate", headers=auth_header)
    assert validate_resp.status_code == 200
    assert validate_resp.json()["blocking_issues"][0]["missing_positions"] == [1]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "阻止运行测评",
            "dataset_id": dataset["id"],
            "selected_models": ["qwen-image-2.0-pro"],
            "baseline_params": {"n": 1, "size": "1024*1024"},
        },
    )
    suite = suite_resp.json()["suite"]

    run_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 400
    assert "blocking_issues" in run_resp.json()
    assert run_resp.json()["blocking_issues"][0]["missing_positions"] == [1]


def test_run_suite_migrates_dataset_snapshot_images_to_current_oss(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "运行前迁移数据集",
            "task_kind": "image_edit",
            "items": [
                {
                    "name": "样例1",
                    "prompt": "把图1做成海报",
                    "image_slots": [
                        {
                            "position": 1,
                            "image": {
                                "url": "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/ref.png",
                                "name": "图1",
                            },
                        }
                    ],
                }
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "迁移快照测评",
            "dataset_id": dataset["id"],
            "selected_models": ["qwen-image-2.0-pro"],
            "baseline_params": {"n": 1},
        },
    )
    suite = suite_resp.json()["suite"]

    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(image_benchmark_router.oss_service, "is_enabled", lambda: True)

    async def fake_ensure_image_persisted_async(url, project_id="", strict=False, max_retries=3):
        return url.replace("https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp", "https://current-oss.example.com")

    monkeypatch.setattr(
        image_benchmark_router.oss_service,
        "ensure_image_persisted_async",
        fake_ensure_image_persisted_async,
    )

    run_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 200
    run = run_resp.json()["run"]
    slot_image = run["dataset_snapshot"]["items"][0]["image_slots"][0]["image"]
    assert slot_image["url"] == "https://current-oss.example.com/ref.png"

    stored_dataset = client.get(f"/api/image-benchmark/datasets/{dataset['id']}", headers=auth_header).json()["dataset"]
    assert stored_dataset["items"][0]["image_slots"][0]["image"]["url"] == "https://current-oss.example.com/ref.png"


@pytest.mark.asyncio
async def test_image_benchmark_persists_pending_matrix_and_completed_cells_incrementally(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user
    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "实时图片测评数据集",
            "task_kind": "text_to_image",
            "items": [
                {"name": "样例1", "prompt": "海报 1", "tags": []},
                {"name": "样例2", "prompt": "海报 2", "tags": []},
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]
    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "实时图片测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-image-pro"],
            "baseline_params": {"n": 1},
        },
    )
    suite = suite_resp.json()["suite"]

    _patch_async_create_task(monkeypatch)
    run_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run"]["id"]
    assert [cell["status"] for cell in run_resp.json()["run"]["cell_results"]] == ["pending", "pending"]
    assert run_resp.json()["run"]["stats"]["pending_count"] == 2

    partial_seen = {"value": False}

    async def fake_execute_benchmark_cell(**kwargs):
        if kwargs["case_data"]["name"] == "样例2":
            for _ in range(20):
                run = storage_service.get_image_benchmark_run(run_id)
                first_cell = next(cell for cell in run.cell_results if cell.case_name == "样例1")
                if run.status == "running" and first_cell.status == "completed":
                    partial_seen["value"] = True
                    break
                await asyncio.sleep(0)
        return ImageBenchmarkCellResult(
            case_id=kwargs["case_data"]["id"],
            case_name=kwargs["case_data"]["name"],
            model_id=kwargs["model_meta"]["id"],
            model_name=kwargs["model_meta"]["name"],
            status="completed",
            output_images=[{"url": f"https://oss.example.com/{kwargs['case_data']['id']}.png"}],
            effective_params=kwargs["effective_params"],
        )

    monkeypatch.setattr(image_benchmark_router, "execute_benchmark_cell", fake_execute_benchmark_cell)
    await image_benchmark_router._background_run_suite(run_id, suite["id"], user["id"], None)

    saved_run = client.get(f"/api/image-benchmark/runs/{run_id}", headers=auth_header).json()["run"]
    assert partial_seen["value"] is True
    assert saved_run["status"] == "completed"
    assert [cell["status"] for cell in saved_run["cell_results"]] == ["completed", "completed"]
    assert saved_run["stats"]["pending_count"] == 0
    assert saved_run["stats"]["completed_count"] == 2


def test_preview_cell_merges_baseline_and_override(client, auth_header):
    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_image",
            "model_id": "wan2.5-t2i-preview",
            "case_data": {
                "name": "海报",
                "prompt": "赛博朋克海报",
                "negative_prompt": "低清晰度",
                "image_slots": [],
            },
            "baseline_params": {
                "n": 1,
                "size_mode": "preset",
                "size_preset": "1024*1024",
                "prompt_extend": True,
            },
            "override_params": {
                "seed": 123,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["effective_params"]["n"] == 1
    assert data["effective_params"]["seed"] == 123
    assert data["provider_payload"]["parameters"]["size"] == "1024*1024"


def test_preview_cell_builds_wan27_interactive_edit_payload(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(url):
        if url.endswith("ref1.png"):
            return {
                "format": "PNG",
                "width": 320,
                "height": 320,
                "aspect_ratio": 1.0,
                "file_size": 1024,
                "has_alpha": False,
            }
        return {
            "format": "PNG",
            "width": 320,
            "height": 240,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "interactive_edit",
            "model_id": "wan2.7-image-pro",
            "case_data": {
                "name": "交互式样例",
                "prompt": "把图1放到图2框选位置",
                "image_slots": [
                    {"position": 1, "image": {"url": "https://oss.example.com/ref1.png", "name": "图1"}},
                    {"position": 2, "image": {"url": "https://oss.example.com/ref2.png", "name": "图2"}},
                ],
                "bbox_list": [[], [[500, 400, -10, 20]]],
            },
            "baseline_params": {"n": 1, "size_preset": "2K", "size_mode": "preset"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "interactive_edit"
    assert data["canonical_request"]["normalized_params"]["bbox_list"] == [[], [[0, 20, 320, 240]]]
    assert data["provider_payload"]["parameters"]["bbox_list"] == [[], [[0, 20, 320, 240]]]


def test_preview_cell_filters_benchmark_managed_wan27_params(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 320,
            "height": 240,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "interactive_edit",
            "model_id": "wan2.7-image-pro",
            "case_data": {
                "name": "交互式样例",
                "prompt": "把图1放到框选位置",
                "image_slots": [
                    {"position": 1, "image": {"url": "https://oss.example.com/ref.png", "name": "图1"}},
                ],
                "bbox_list": [[[10, 20, 100, 140]]],
            },
            "baseline_params": {
                "n": 1,
                "thinking_mode": True,
                "enable_sequential": True,
                "bbox_list": [[]],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "thinking_mode" not in data["effective_params"]
    assert "enable_sequential" not in data["effective_params"]
    assert "bbox_list" not in data["effective_params"]
    assert data["provider_payload"]["parameters"]["bbox_list"] == [[[10, 20, 100, 140]]]
    assert "thinking_mode" not in data["provider_payload"]["parameters"]
    assert "enable_sequential" not in data["provider_payload"]["parameters"]


def test_preview_cell_ignores_legacy_bbox_for_wan27_image_edit(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 320,
            "height": 240,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": True,
        }

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "image_edit",
            "model_id": "wan2.7-image-pro",
            "case_data": {
                "name": "图片编辑样例",
                "prompt": "把图1做成海报",
                "image_slots": [
                    {"position": 1, "image": {"url": "https://oss.example.com/transparent.png", "name": "图1"}},
                ],
                "bbox_list": [[]],
            },
            "baseline_params": {"n": 1, "size_preset": "2K", "size_mode": "preset"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "image_edit"
    assert "bbox_list" not in data["canonical_request"]["normalized_params"]
    assert "bbox_list" not in data["provider_payload"]["parameters"]


@pytest.mark.asyncio
async def test_execute_cell_ignores_legacy_bbox_for_wan27_image_edit(monkeypatch):
    from app.models.studio import StudioTaskImage
    from app.services.image_benchmark_runtime import _execute_benchmark_cell_once

    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 320,
            "height": 240,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": True,
        }

    captured = {}

    async def fake_generate_with_wan27_image(**kwargs):
        captured["bbox_list"] = kwargs.get("bbox_list")
        captured["task_kind"] = kwargs["task"].task_kind
        return (
            [StudioTaskImage(url="https://oss.example.com/output.png", prompt_used="prompt")],
            ["task-1"],
            ["req-1"],
            {"task-1": {"request_id": "req-1"}},
        )

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)
    monkeypatch.setattr("app.services.image_benchmark_runtime.studio_router.generate_with_wan27_image", fake_generate_with_wan27_image)
    monkeypatch.setattr("app.services.image_benchmark_runtime.oss_service.is_enabled", lambda: False)

    result = await _execute_benchmark_cell_once(
        project_id="p1",
        task_kind="image_edit",
        model_meta={"id": "wan2.7-image-pro", "name": "万相 2.7 Image Pro"},
        case_data={
            "id": "case-1",
            "name": "图片编辑样例",
            "prompt": "把图1做成海报",
            "image_slots": [
                {"position": 1, "image": {"url": "https://oss.example.com/transparent.png", "name": "图1"}},
            ],
            "bbox_list": [[]],
        },
        effective_params={"n": 1, "size_mode": "preset", "size_preset": "2K"},
    )

    assert result.status == "completed"
    assert captured["task_kind"] == "image_edit"
    assert captured["bbox_list"] is None
    assert "bbox_list" not in result.provider_payload["parameters"]


@pytest.mark.asyncio
async def test_execute_cell_passes_normalized_bbox_for_wan27_interactive_edit(monkeypatch):
    from app.models.studio import StudioTaskImage
    from app.services.image_benchmark_runtime import _execute_benchmark_cell_once

    async def mock_inspect_remote_image(url):
        if url.endswith("ref1.png"):
            return {
                "format": "PNG",
                "width": 320,
                "height": 320,
                "aspect_ratio": 1.0,
                "file_size": 1024,
                "has_alpha": False,
            }
        return {
            "format": "PNG",
            "width": 320,
            "height": 240,
            "aspect_ratio": 4 / 3,
            "file_size": 1024,
            "has_alpha": False,
        }

    captured = {}

    async def fake_generate_with_wan27_image(**kwargs):
        captured["bbox_list"] = kwargs.get("bbox_list")
        captured["task_kind"] = kwargs["task"].task_kind
        return (
            [StudioTaskImage(url="https://oss.example.com/output.png", prompt_used="prompt")],
            ["task-1"],
            ["req-1"],
            {"task-1": {"request_id": "req-1"}},
        )

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)
    monkeypatch.setattr("app.services.image_benchmark_runtime.studio_router.generate_with_wan27_image", fake_generate_with_wan27_image)
    monkeypatch.setattr("app.services.image_benchmark_runtime.oss_service.is_enabled", lambda: False)

    result = await _execute_benchmark_cell_once(
        project_id="p1",
        task_kind="interactive_edit",
        model_meta={"id": "wan2.7-image-pro", "name": "万相 2.7 Image Pro"},
        case_data={
            "id": "case-1",
            "name": "交互式样例",
            "prompt": "把图1放到图2框选位置",
            "image_slots": [
                {"position": 1, "image": {"url": "https://oss.example.com/ref1.png", "name": "图1"}},
                {"position": 2, "image": {"url": "https://oss.example.com/ref2.png", "name": "图2"}},
            ],
            "bbox_list": [[], [[500, 400, -10, 20]]],
        },
        effective_params={"n": 1, "size_mode": "preset", "size_preset": "2K"},
    )

    assert result.status == "completed"
    assert captured["task_kind"] == "interactive_edit"
    assert captured["bbox_list"] == [[], [[0, 20, 320, 240]]]
    assert result.provider_payload["parameters"]["bbox_list"] == [[], [[0, 20, 320, 240]]]


def test_preview_cell_applies_wan27_color_palette(client, auth_header):
    project_id = _create_project(client, auth_header)
    color_palette = [
        {"hex": "#C2D1E6", "ratio": "34.00%"},
        {"hex": "#C0B5B4", "ratio": "33.00%"},
        {"hex": "#636574", "ratio": "33.00%"},
    ]
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_image",
            "model_id": "wan2.7-image-pro",
            "case_data": {
                "name": "文生图样例",
                "prompt": "一张品牌海报",
            },
            "baseline_params": {"n": 1, "color_palette": color_palette},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["color_palette"] == color_palette


def test_benchmark_capabilities_expose_wan27_custom_size_params(client, auth_header):
    resp = client.get("/api/image-benchmark/capabilities", headers=auth_header)
    assert resp.status_code == 200
    model = resp.json()["models"]["wan2.7-image-pro"]
    param_names = {param["name"] for param in model["configurable_parameters"]}
    assert "size" not in param_names
    assert {"size_mode", "size_preset", "custom_width", "custom_height"} <= param_names


def test_image_benchmark_capabilities_expose_sync_and_async_rate_limits(client, auth_header):
    resp = client.get("/api/image-benchmark/capabilities", headers=auth_header)
    assert resp.status_code == 200
    models = resp.json()["models"]

    qwen = models["qwen-image-2.0-pro"]["capabilities"]
    assert qwen["api_mode"] == "sync"
    assert qwen["submit_rate_limit"] == {"count": 2, "period_seconds": 60}
    assert qwen["max_concurrent"] is None
    assert qwen["concurrency_scope"] == "unlimited"

    wan = models["wan2.7-image-pro"]["capabilities"]
    assert wan["api_mode"] == "async"
    assert wan["submit_rate_limit"] == {"count": 5, "period_seconds": 1}
    assert wan["max_concurrent"] == 5
    assert wan["concurrency_scope"] == "model"


def test_preview_cell_wan27_custom_size(client, auth_header):
    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_image",
            "model_id": "wan2.7-image-pro",
            "case_data": {
                "name": "文生图样例",
                "prompt": "16:9 海报",
            },
            "baseline_params": {
                "n": 1,
                "size_mode": "custom",
                "custom_width": 3072,
                "custom_height": 1728,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["size"] == "3072*1728"
    assert data["canonical_request"]["normalized_params"]["size"] == "3072*1728"


@pytest.mark.parametrize("model_id", ["wan2.7-image-pro", "wan2.7-image"])
def test_preview_cell_wan27_custom_portrait_size(client, auth_header, model_id):
    project_id = _create_project(client, auth_header)
    resp = client.post(
        "/api/image-benchmark/preview-cell",
        headers=auth_header,
        json={
            "project_id": project_id,
            "task_kind": "text_to_image",
            "model_id": model_id,
            "case_data": {
                "name": "竖版样例",
                "prompt": "9:16 竖版封面",
            },
            "baseline_params": {
                "n": 1,
                "size_mode": "custom",
                "custom_width": 1080,
                "custom_height": 1920,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["size"] == "1080*1920"
    assert data["canonical_request"]["normalized_params"]["size"] == "1080*1920"


def test_public_share_exposes_latest_run_without_auth_and_hides_sensitive_fields(client, auth_header, registered_user):
    _, user = registered_user
    suite, run = _create_suite_with_public_run(client, auth_header, user["id"])

    share_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/share", headers=auth_header)
    assert share_resp.status_code == 200
    token = share_resp.json()["suite"]["share_token"]
    assert share_resp.json()["share_url"] == f"/image-benchmark/share/{token}"

    public_resp = client.get(f"/api/image-benchmark/public/shares/{token}")
    assert public_resp.status_code == 200
    data = public_resp.json()
    assert data["suite"]["name"] == "公开分享测评"
    assert data["run"]["id"] == run.id
    cell = data["run"]["cell_results"][0]
    assert cell["output_images"][0]["url"] == "https://oss.example.com/output.png"
    assert "provider_payload" not in cell
    assert "canonical_request" not in cell
    assert "request_ids" not in cell
    assert "task_ids" not in cell
    assert "effective_params" not in cell


def test_public_share_can_be_disabled(client, auth_header, registered_user):
    _, user = registered_user
    suite, _ = _create_suite_with_public_run(client, auth_header, user["id"])

    share_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/share", headers=auth_header)
    token = share_resp.json()["suite"]["share_token"]

    disable_resp = client.delete(f"/api/image-benchmark/suites/{suite['id']}/share", headers=auth_header)
    assert disable_resp.status_code == 200
    assert disable_resp.json()["suite"]["share_enabled"] is False

    public_resp = client.get(f"/api/image-benchmark/public/shares/{token}")
    assert public_resp.status_code == 404


def test_public_share_tracks_suite_latest_run(client, auth_header, registered_user):
    _, user = registered_user
    suite, first_run = _create_suite_with_public_run(client, auth_header, user["id"])
    share_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/share", headers=auth_header)
    token = share_resp.json()["suite"]["share_token"]

    set_current_user(user["id"])
    try:
        stored_suite = storage_service.get_image_benchmark_suite(suite["id"])
        second_run = ImageBenchmarkRun(
            suite_id=suite["id"],
            project_id=first_run.project_id,
            dataset_id=first_run.dataset_id,
            task_kind="text_to_image",
            status="completed",
            dataset_snapshot=first_run.dataset_snapshot,
            model_snapshots=first_run.model_snapshots,
            cell_results=[],
            stats={"case_count": 1, "model_count": 1, "success_count": 0, "failure_count": 0},
        )
        storage_service.save_image_benchmark_run(second_run)
        stored_suite.latest_run_id = second_run.id
        storage_service.save_image_benchmark_suite(stored_suite)
    finally:
        set_current_user(None)

    public_resp = client.get(f"/api/image-benchmark/public/shares/{token}")
    assert public_resp.status_code == 200
    assert public_resp.json()["run"]["id"] == second_run.id


def test_public_share_markdown_contains_visible_results(client, auth_header, registered_user):
    _, user = registered_user
    suite, _ = _create_suite_with_public_run(client, auth_header, user["id"])
    share_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/share", headers=auth_header)
    token = share_resp.json()["suite"]["share_token"]

    markdown_resp = client.get(f"/api/image-benchmark/public/shares/{token}/markdown")
    assert markdown_resp.status_code == 200
    content = markdown_resp.json()["content"]
    assert "公开分享测评" in content
    assert "一张海报" in content
    assert "https://oss.example.com/output.png" in content
    assert "canonical" not in content
    assert "provider" not in content
    assert "req-secret" not in content


@pytest.mark.asyncio
async def test_execute_benchmark_cell_retries_on_rate_limit(monkeypatch):
    attempts = {"count": 0}
    sleep_calls = []

    async def fake_generate_with_qwen_image_2(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] <= 3:
            raise Exception("API 调用失败 (Throttling.RateQuota): Requests rate limit exceeded")
        from app.models.studio import StudioTaskImage
        return [StudioTaskImage(group_index=0, url="https://oss.example.com/output.png", prompt_used="prompt")], ["req-2"]

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)
        return None

    monkeypatch.setattr("app.services.image_benchmark_runtime.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.routers.studio.generate_with_qwen_image_2", fake_generate_with_qwen_image_2)

    from app.services.image_benchmark_runtime import execute_benchmark_cell

    result = await execute_benchmark_cell(
        project_id="p1",
        task_kind="image_edit",
        model_meta={"id": "qwen-image-2.0-pro", "name": "千问图像 2.0 Pro"},
        case_data={
            "id": "case-1",
            "name": "样例1",
            "prompt": "把图1做成海报",
            "negative_prompt": "",
            "image_slots": [
                {"position": 1, "image": {"url": "https://oss.example.com/ref.png", "name": "图1"}},
            ],
        },
        effective_params={"n": 1, "size": "", "prompt_extend": True, "watermark": False},
    )

    assert attempts["count"] == 4
    assert result.status == "completed"
    assert result.auto_retry_count == 3
    assert result.attempt_count == 4
    assert sleep_calls == [2, 4, 8]
    assert result.output_images[0].url == "https://oss.example.com/output.png"


@pytest.mark.asyncio
async def test_execute_benchmark_cell_rehosts_temporary_output_urls(monkeypatch):
    from app.models.studio import StudioTaskImage

    async def fake_preview_benchmark_cell(**kwargs):
        return (
            {
                "provider": "wan",
                "task_kind": kwargs["task_kind"],
                "input_assets": {},
                "normalized_params": {"size": "1024*1024"},
            },
            {"parameters": {"size": "1024*1024"}},
            [],
        )

    async def fake_generate_with_qwen_image_2(*args, **kwargs):
        return [
            StudioTaskImage(
                group_index=0,
                url="https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/output.png",
                prompt_used="prompt",
            )
        ], ["req-1"]

    persisted_urls = []

    async def fake_ensure_image_persisted_async(url, project_id="", strict=False, max_retries=3):
        persisted_urls.append((url, project_id, strict))
        return "https://current-oss.example.com/output.png"

    monkeypatch.setattr("app.services.image_benchmark_runtime.preview_benchmark_cell", fake_preview_benchmark_cell)
    monkeypatch.setattr("app.routers.studio.generate_with_qwen_image_2", fake_generate_with_qwen_image_2)
    monkeypatch.setattr("app.services.image_benchmark_runtime.oss_service.is_enabled", lambda: True)
    monkeypatch.setattr(
        "app.services.image_benchmark_runtime.oss_service.ensure_image_persisted_async",
        fake_ensure_image_persisted_async,
    )

    from app.services.image_benchmark_runtime import execute_benchmark_cell

    result = await execute_benchmark_cell(
        project_id="p1",
        task_kind="image_edit",
        model_meta={"id": "qwen-image-2.0-pro", "name": "千问图像 2.0 Pro"},
        case_data={
            "id": "case-1",
            "name": "样例1",
            "prompt": "把图1做成海报",
            "negative_prompt": "",
            "image_slots": [{"position": 1, "image": {"url": "https://oss.example.com/ref.png", "name": "图1"}}],
        },
        effective_params={"n": 1},
    )

    assert result.status == "completed"
    assert result.output_images[0].url == "https://current-oss.example.com/output.png"
    assert persisted_urls == [
        (
            "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/output.png",
            "p1",
            True,
        )
    ]


@pytest.mark.asyncio
async def test_execute_benchmark_cell_keeps_ids_across_auto_retries(monkeypatch):
    attempts = {"count": 0}

    async def fake_execute_once(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return ImageBenchmarkCellResult(
                case_id="case-1",
                case_name="样例1",
                model_id="wan2.7-image",
                model_name="万相 2.7 Image",
                status="failed",
                error_message="API 调用失败 (Throttling.RateQuota): Requests rate limit exceeded",
                request_ids=["req-submit-1"],
                task_ids=["task-1"],
            )
        return ImageBenchmarkCellResult(
            case_id="case-1",
            case_name="样例1",
            model_id="wan2.7-image",
            model_name="万相 2.7 Image",
            status="completed",
            request_ids=["req-submit-2", "req-result-2"],
            task_ids=["task-2"],
        )

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr("app.services.image_benchmark_runtime._execute_benchmark_cell_once", fake_execute_once)
    monkeypatch.setattr("app.services.image_benchmark_runtime.asyncio.sleep", fake_sleep)

    from app.services.image_benchmark_runtime import execute_benchmark_cell

    result = await execute_benchmark_cell(
        project_id="p1",
        task_kind="image_edit",
        model_meta={"id": "wan2.7-image", "name": "万相 2.7 Image"},
        case_data={"id": "case-1", "name": "样例1", "prompt": "prompt", "image_slots": []},
        effective_params={"n": 1},
    )

    assert attempts["count"] == 2
    assert result.status == "completed"
    assert result.request_ids == ["req-submit-1", "req-submit-2", "req-result-2"]
    assert result.task_ids == ["task-1", "task-2"]
    assert result.provider_result_meta["auto_retry"]["request_ids"] == result.request_ids
    assert result.provider_result_meta["auto_retry"]["task_ids"] == result.task_ids


@pytest.mark.asyncio
async def test_run_snapshot_is_frozen_and_markdown_export(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user

    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "编辑数据集",
            "task_kind": "image_edit",
            "items": [
                {
                    "name": "图像编辑1",
                    "prompt": "把角色做成海报",
                    "image_slots": [
                        {"position": 1, "image": {"url": "https://oss.example.com/ref.png", "name": "参考图", "source_label": "图库"}},
                    ],
                }
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "编辑测评",
            "dataset_id": dataset["id"],
            "selected_models": ["qwen-image-2.0-pro"],
            "baseline_params": {"n": 1, "size": "1024*1024"},
        },
    )
    suite = suite_resp.json()["suite"]

    _patch_async_create_task(monkeypatch)
    run_resp = client.post(f"/api/image-benchmark/suites/{suite['id']}/run", headers=auth_header)
    assert run_resp.status_code == 200
    run = run_resp.json()["run"]
    assert run["dataset_snapshot"]["items"][0]["prompt"] == "把角色做成海报"

    update_resp = client.put(
        f"/api/image-benchmark/datasets/{dataset['id']}",
        headers=auth_header,
        json={
            "items": [
                {
                    "id": dataset["items"][0]["id"],
                    "name": "图像编辑1",
                    "prompt": "这个 prompt 已经改变",
                    "image_slots": [
                        {"position": 1, "image": {"url": "https://oss.example.com/ref.png", "name": "参考图"}},
                    ],
                }
            ]
        },
    )
    assert update_resp.status_code == 200

    async def fake_execute_benchmark_cell(**kwargs):
        return ImageBenchmarkCellResult(
            case_id=kwargs["case_data"]["id"],
            case_name=kwargs["case_data"]["name"],
            model_id=kwargs["model_meta"]["id"],
            model_name=kwargs["model_meta"]["name"],
            status="completed",
            output_images=[{"url": "https://oss.example.com/output.png", "prompt_used": kwargs["case_data"]["prompt"]}],
            request_ids=["req-1"],
            effective_params=kwargs["effective_params"],
            canonical_request={"prompt": kwargs["case_data"]["prompt"]},
            provider_payload={"model": kwargs["model_meta"]["id"]},
        )

    monkeypatch.setattr(image_benchmark_router, "execute_benchmark_cell", fake_execute_benchmark_cell)
    await image_benchmark_router._background_run_suite(run["id"], suite["id"], user["id"], None)

    saved_run = client.get(f"/api/image-benchmark/runs/{run['id']}", headers=auth_header).json()["run"]
    assert saved_run["dataset_snapshot"]["items"][0]["prompt"] == "把角色做成海报"
    assert saved_run["cell_results"][0]["canonical_request"]["prompt"] == "把角色做成海报"

    async def fake_download_image_as_data_url(url, client=None):
        if url.endswith("/ref.png"):
            return "data:image/png;base64,cmVm"
        return "data:image/png;base64,b3V0"

    monkeypatch.setattr(
        "app.services.image_benchmark_runtime._download_image_as_data_url",
        fake_download_image_as_data_url,
    )

    export_resp = client.post(f"/api/image-benchmark/runs/{run['id']}/export-md", headers=auth_header)
    assert export_resp.status_code == 200
    export_payload = export_resp.json()
    markdown = export_payload["content"]
    assert "# 图片测评报告" in markdown
    assert export_payload["embedded_image_count"] == 2
    assert export_payload["fallback_url_count"] == 0
    assert '<img src="data:image/png;base64,cmVm"' in markdown
    assert '<img src="data:image/png;base64,b3V0"' in markdown

    html_resp = client.post(f"/api/image-benchmark/runs/{run['id']}/export-html", headers=auth_header)
    assert html_resp.status_code == 200
    html_payload = html_resp.json()
    assert html_payload["embedded_image_count"] == 2
    assert html_payload["fallback_url_count"] == 0
    assert html_payload["filename"].endswith(".html")
    assert "data:image/png;base64,cmVm" in html_payload["content"]
    assert "data:image/png;base64,b3V0" in html_payload["content"]
    assert "https://oss.example.com/ref.png" not in html_payload["content"]
    assert "https://oss.example.com/output.png" not in html_payload["content"]

    attempts = {"count": 0}

    async def fake_sleep(_seconds):
        return None

    async def flaky_download_image_as_data_url(url, client=None):
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise image_benchmark_runtime.ImageBenchmarkExportAssetError("下载超时", retryable=True)
        if url.endswith("/ref.png"):
            return "data:image/png;base64,cmVm"
        return "data:image/png;base64,b3V0"

    monkeypatch.setattr(
        "app.services.image_benchmark_runtime._download_image_as_data_url",
        flaky_download_image_as_data_url,
    )
    monkeypatch.setattr("app.services.image_benchmark_runtime.asyncio.sleep", fake_sleep)

    retry_export_resp = client.post(f"/api/image-benchmark/runs/{run['id']}/export-md", headers=auth_header)
    assert retry_export_resp.status_code == 200
    retry_export_payload = retry_export_resp.json()
    assert retry_export_payload["embedded_image_count"] == 2
    assert retry_export_payload["fallback_url_count"] == 0
    assert attempts["count"] >= 4

    def fail_if_called(*args, **kwargs):
        raise AssertionError("快速导出不应尝试下载图片")

    monkeypatch.setattr(
        "app.services.image_benchmark_runtime._download_image_as_data_url",
        fail_if_called,
    )

    quick_md_resp = client.post(
        f"/api/image-benchmark/runs/{run['id']}/export-md",
        headers=auth_header,
        json={"inline_images": False},
    )
    assert quick_md_resp.status_code == 200
    quick_md_payload = quick_md_resp.json()
    assert quick_md_payload["embedded_image_count"] == 0
    assert quick_md_payload["fallback_url_count"] == 0
    assert "https://oss.example.com/ref.png" in quick_md_payload["content"]
    assert "https://oss.example.com/output.png" in quick_md_payload["content"]

    quick_html_resp = client.post(
        f"/api/image-benchmark/runs/{run['id']}/export-html",
        headers=auth_header,
        json={"inline_images": False},
    )
    assert quick_html_resp.status_code == 200
    quick_html_payload = quick_html_resp.json()
    assert quick_html_payload["embedded_image_count"] == 0
    assert quick_html_payload["fallback_url_count"] == 0
    assert "https://oss.example.com/ref.png" in quick_html_payload["content"]
    assert "https://oss.example.com/output.png" in quick_html_payload["content"]

    quick_md_file_resp = client.post(
        f"/api/image-benchmark/runs/{run['id']}/export-md-file",
        headers=auth_header,
        json={"inline_images": False},
    )
    assert quick_md_file_resp.status_code == 200
    assert quick_md_file_resp.headers["content-disposition"].startswith("attachment;")
    assert quick_md_file_resp.headers["x-embedded-image-count"] == "0"
    assert quick_md_file_resp.headers["x-fallback-url-count"] == "0"
    assert quick_md_file_resp.content.startswith("# 图片测评报告".encode("utf-8"))

    quick_html_file_resp = client.post(
        f"/api/image-benchmark/runs/{run['id']}/export-html-file",
        headers=auth_header,
        json={"inline_images": False},
    )
    assert quick_html_file_resp.status_code == 200
    assert quick_html_file_resp.headers["content-disposition"].startswith("attachment;")
    assert quick_html_file_resp.headers["x-embedded-image-count"] == "0"
    assert quick_html_file_resp.headers["x-fallback-url-count"] == "0"
    assert b"<!doctype html>" in quick_html_file_resp.content


@pytest.mark.asyncio
async def test_retry_failed_cells_creates_new_run_and_only_retries_failed(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user

    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "重试数据集",
            "task_kind": "image_edit",
            "items": [
                {
                    "name": "样例1",
                    "prompt": "prompt-1",
                    "image_slots": [{"position": 1, "image": {"url": "https://oss.example.com/a.png", "name": "图1"}}],
                },
                {
                    "name": "样例2",
                    "prompt": "prompt-2",
                    "image_slots": [{"position": 1, "image": {"url": "https://oss.example.com/b.png", "name": "图1"}}],
                },
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "重试测评",
            "dataset_id": dataset["id"],
            "selected_models": ["qwen-image-2.0-pro"],
            "baseline_params": {"n": 1},
        },
    )
    suite = suite_resp.json()["suite"]

    set_current_user(user["id"])
    source_run = image_benchmark_router.ImageBenchmarkRun(
        suite_id=suite["id"],
        project_id=project_id,
        dataset_id=dataset["id"],
        task_kind="image_edit",
        status="completed",
        dataset_snapshot=dataset,
        model_snapshots=[{"id": "qwen-image-2.0-pro", "name": "千问图像 2.0 Pro"}],
        baseline_params={"n": 1},
        model_overrides={},
        cell_results=[
            ImageBenchmarkCellResult(
                case_id=dataset["items"][0]["id"],
                case_name="样例1",
                model_id="qwen-image-2.0-pro",
                model_name="千问图像 2.0 Pro",
                status="completed",
                output_images=[{"url": "https://oss.example.com/success.png"}],
            ),
            ImageBenchmarkCellResult(
                case_id=dataset["items"][1]["id"],
                case_name="样例2",
                model_id="qwen-image-2.0-pro",
                model_name="千问图像 2.0 Pro",
                status="failed",
                error_message="API 调用失败 (Throttling.RateQuota): Requests rate limit exceeded",
            ),
        ],
    )
    storage_service.save_image_benchmark_run(source_run)

    _patch_async_create_task(monkeypatch)
    retry_resp = client.post(f"/api/image-benchmark/runs/{source_run.id}/retry-failures", headers=auth_header)
    assert retry_resp.status_code == 200
    retry_run = retry_resp.json()["run"]
    assert retry_run["retry_source_run_id"] == source_run.id
    assert len(retry_run["retry_targets"]) == 1
    assert retry_run["retry_targets"][0]["case_id"] == dataset["items"][1]["id"]

    async def fake_execute_benchmark_cell(**kwargs):
        return ImageBenchmarkCellResult(
            case_id=kwargs["case_data"]["id"],
            case_name=kwargs["case_data"]["name"],
            model_id=kwargs["model_meta"]["id"],
            model_name=kwargs["model_meta"]["name"],
            status="completed",
            output_images=[{"url": f"https://oss.example.com/{kwargs['case_data']['id']}.png"}],
        )

    monkeypatch.setattr(image_benchmark_router, "execute_benchmark_cell", fake_execute_benchmark_cell)
    await image_benchmark_router._background_run_suite(retry_run["id"], suite["id"], user["id"], None)

    saved_run = client.get(f"/api/image-benchmark/runs/{retry_run['id']}", headers=auth_header).json()["run"]
    assert len(saved_run["cell_results"]) == 2
    retried_cell = next(cell for cell in saved_run["cell_results"] if cell["case_id"] == dataset["items"][1]["id"])
    assert retried_cell["status"] == "completed"
    assert saved_run["stats"]["retried_failure_count"] == 1


@pytest.mark.asyncio
async def test_retry_failed_cells_also_retries_unsupported(client, auth_header, registered_user, monkeypatch):
    project_id = _create_project(client, auth_header)
    _, user = registered_user

    dataset_resp = client.post(
        "/api/image-benchmark/datasets",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "未支持重试数据集",
            "task_kind": "image_edit",
            "items": [
                {
                    "name": "样例1",
                    "prompt": "prompt-1",
                    "image_slots": [{"position": 1, "image": {"url": "https://oss.example.com/a.png", "name": "图1"}}],
                },
            ],
        },
    )
    dataset = dataset_resp.json()["dataset"]

    suite_resp = client.post(
        "/api/image-benchmark/suites",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "未支持重试测评",
            "dataset_id": dataset["id"],
            "selected_models": ["wan2.7-image"],
            "baseline_params": {"n": 1},
        },
    )
    suite = suite_resp.json()["suite"]

    set_current_user(user["id"])
    source_run = image_benchmark_router.ImageBenchmarkRun(
        suite_id=suite["id"],
        project_id=project_id,
        dataset_id=dataset["id"],
        task_kind="image_edit",
        status="completed",
        dataset_snapshot=dataset,
        model_snapshots=[{"id": "wan2.7-image", "name": "万相 2.7 Image"}],
        baseline_params={"n": 1},
        model_overrides={},
        cell_results=[
            ImageBenchmarkCellResult(
                case_id=dataset["items"][0]["id"],
                case_name="样例1",
                model_id="wan2.7-image",
                model_name="万相 2.7 Image",
                status="unsupported",
                error_message="第 1 张输入图片无法读取: ",
            ),
        ],
    )
    storage_service.save_image_benchmark_run(source_run)

    _patch_async_create_task(monkeypatch)
    retry_resp = client.post(f"/api/image-benchmark/runs/{source_run.id}/retry-failures", headers=auth_header)
    assert retry_resp.status_code == 200
    retry_run = retry_resp.json()["run"]
    assert retry_run["retry_targets"] == [{"case_id": dataset["items"][0]["id"], "model_id": "wan2.7-image"}]
    assert retry_run["cell_results"][0]["status"] == "pending"
    assert retry_run["cell_results"][0]["case_id"] == dataset["items"][0]["id"]
