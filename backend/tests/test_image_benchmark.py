import pytest

from app.models.image_benchmark import ImageBenchmarkCellResult
from app.routers import image_benchmark as image_benchmark_router
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
    assert data["provider_payload"]["parameters"]["bbox_list"] == [[], [[0, 20, 320, 240]]]


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

    export_resp = client.post(f"/api/image-benchmark/runs/{run['id']}/export-md", headers=auth_header)
    assert export_resp.status_code == 200
    markdown = export_resp.json()["content"]
    assert "# 图片测评报告" in markdown
    assert "https://oss.example.com/output.png" in markdown


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
    assert retry_run["cell_results"] == []
