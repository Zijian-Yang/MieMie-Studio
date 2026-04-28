import pytest
from datetime import datetime, timedelta

from app.models.studio import ReferenceItem, StudioTaskImage
from app.routers import studio as studio_router
from app.models_registry.image.wan27_image import Wan27ImageService
from app.routers.studio import get_image_size_templates
from app.services.oss import PersistedAssetResult


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "能力测试项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(studio_router.asyncio, "create_task", fake_create_task)


def _mock_reference_items(urls):
    return [
        ReferenceItem(type="gallery", id=f"ref-{index}", name=f"图{index + 1}", url=url)
        for index, url in enumerate(urls)
    ]


def test_get_available_image_models_preserves_registry_metadata(client, auth_header):
    resp = client.get("/api/studio/models/available", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()["models"]

    assert "wan2.7-image-pro" in data
    assert "qwen-image-max" in data
    assert "wan2.6-image" in data

    assert data["wan2.7-image-pro"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
        "interactive_edit",
        "sequential_generation",
    ]
    assert data["wan2.6-image"]["parameters"]
    assert any(param["name"] == "enable_interleave" for param in data["wan2.6-image"]["parameters"])
    assert data["qwen-image-max"]["parameters"]
    assert any(param["name"] == "size" for param in data["qwen-image-max"]["parameters"])
    assert data["wan2.7-image-pro"]["size_ui_mode"] == "preset_plus_custom_with_templates"
    assert data["wan2.5-t2i-preview"]["size_ui_mode"] == "preset_plus_custom_with_templates"
    assert data["qwen-image-edit-plus"]["size_ui_mode"] == "preset_only"


def test_get_available_image_models_includes_seedream_models(client, auth_header):
    resp = client.get("/api/studio/models/available", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()["models"]

    assert "doubao-seedream-5.0-lite" in data
    assert "doubao-seedream-4.5" in data
    assert data["doubao-seedream-5.0-lite"]["provider"] == "volcengine"
    assert data["doubao-seedream-5.0-lite"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
        "sequential_generation",
    ]
    assert data["doubao-seedream-4.5"]["supported_task_kinds"] == [
        "text_to_image",
        "image_edit",
        "sequential_generation",
    ]
    seedream_lite = data["doubao-seedream-5.0-lite"]
    seedream_params = {param["name"] for param in seedream_lite["parameters"]}
    assert {"size", "n", "prompt_extend", "watermark", "output_format", "web_search"}.issubset(seedream_params)
    assert "guidance_scale" not in seedream_params
    size_param = next(param for param in seedream_lite["parameters"] if param["name"] == "size")
    assert size_param["default"] == "2K"
    size_option_values = [option["value"] for option in size_param["constraint"]["options"]]
    assert size_option_values == ["2K", "3K", "4K"]
    assert [option["label"] for option in size_param["constraint"]["options"]] == ["2K", "3K", "4K"]
    fixed_size_values = {f"{size['width']}x{size['height']}" for size in seedream_lite["common_sizes"]}
    assert fixed_size_values
    assert not set(size_option_values) & fixed_size_values
    assert "3072x3072" in fixed_size_values

    seedream_45 = data["doubao-seedream-4.5"]
    seedream_45_params = {param["name"] for param in seedream_45["parameters"]}
    assert "guidance_scale" not in seedream_45_params
    assert "output_format" not in seedream_45_params
    assert "web_search" not in seedream_45_params
    size_45_param = next(param for param in seedream_45["parameters"] if param["name"] == "size")
    assert [option["value"] for option in size_45_param["constraint"]["options"]] == ["2K", "4K"]
    assert [option["label"] for option in size_45_param["constraint"]["options"]] == ["2K", "4K"]
    fixed_45_size_values = {f"{size['width']}x{size['height']}" for size in seedream_45["common_sizes"]}
    assert "3072x3072" not in fixed_45_size_values


def test_wan27_size_templates_are_legal_for_pure_text_mode():
    templates = get_image_size_templates(
        model_name="wan2.7-image-pro",
        task_kind="text_to_image",
        has_images=False,
        enable_sequential=False,
    )
    assert templates
    assert any(item["ratio"] == "21:9" for item in templates)
    for item in templates:
        assert 768 * 768 <= item["width"] * item["height"] <= 4096 * 4096
        ratio = item["width"] / item["height"]
        assert (1 / 8) <= ratio <= 8


def test_preview_payload_rejects_incompatible_model_task_kind(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "qwen-image-edit-plus",
            "task_kind": "text_to_image",
            "prompt": "生成一张海报",
            "n": 1,
            "group_count": 1,
            "references": [],
        },
    )
    assert resp.status_code == 400
    assert "不支持任务类型" in resp.json()["detail"]


def test_preview_payload_builds_wan27_sequential_payload(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "sequential_generation",
            "prompt": "电影感组图，同一只橘猫在四季场景中保持特征一致",
            "n": 4,
            "group_count": 1,
            "enable_sequential": True,
            "size_mode": "preset",
            "size_preset": "2K",
            "references": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "sequential_generation"
    assert data["provider_payload"]["parameters"]["enable_sequential"] is True
    assert data["provider_payload"]["parameters"]["size"] == "2K"


def test_preview_payload_builds_seedream_lite_sequential_payload(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "doubao-seedream-5.0-lite",
            "task_kind": "sequential_generation",
            "prompt": "同一只橘猫的四格漫画组图",
            "n": 4,
            "group_count": 1,
            "size": "2K",
            "prompt_extend": True,
            "watermark": False,
            "output_format": "png",
            "web_search": True,
            "references": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["provider"] == "volcengine"
    assert data["canonical_request"]["task_kind"] == "sequential_generation"
    payload = data["provider_payload"]
    assert payload["model"] == "doubao-seedream-5-0-260128"
    assert payload["prompt"] == "同一只橘猫的四格漫画组图"
    assert payload["size"] == "2K"
    assert payload["sequential_image_generation"] == "auto"
    assert payload["sequential_image_generation_options"]["max_images"] == 4
    assert payload["optimize_prompt_options"]["mode"] == "standard"
    assert payload["output_format"] == "png"
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["response_format"] == "url"
    assert payload["stream"] is False


def test_preview_payload_builds_seedream_image_edit_payload_with_fixed_size(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(
            [
                "https://oss.example.com/ref-1.png",
                "https://oss.example.com/ref-2.png",
            ]
        ),
    )
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "doubao-seedream-4.5",
            "task_kind": "image_edit",
            "prompt": "融合图1和图2生成电影海报",
            "n": 1,
            "group_count": 1,
            "size": "3750*1250",
            "prompt_extend": False,
            "watermark": True,
            "references": [{"type": "gallery", "id": "g1"}, {"type": "gallery", "id": "g2"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    payload = data["provider_payload"]
    assert data["canonical_request"]["task_kind"] == "image_edit"
    assert data["canonical_request"]["normalized_params"]["size"] == "3750x1250"
    assert payload["model"] == "doubao-seedream-4-5-251128"
    assert payload["size"] == "3750x1250"
    assert payload["image"] == ["https://oss.example.com/ref-1.png", "https://oss.example.com/ref-2.png"]
    assert payload["sequential_image_generation"] == "disabled"
    assert payload["watermark"] is True
    assert "optimize_prompt_options" not in payload
    assert "guidance_scale" not in payload


def test_preview_payload_rejects_seedream_45_output_format(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "doubao-seedream-4.5",
            "task_kind": "text_to_image",
            "prompt": "一张海报",
            "n": 1,
            "size": "2K",
            "output_format": "png",
            "references": [],
        },
    )
    assert resp.status_code == 400
    assert "output_format" in resp.json()["detail"]


def test_preview_payload_rejects_seedream_too_many_reference_and_output_images(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items([f"https://oss.example.com/ref-{index}.png" for index in range(14)]),
    )
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "doubao-seedream-5.0-lite",
            "task_kind": "sequential_generation",
            "prompt": "根据参考图生成组图",
            "n": 2,
            "size": "2K",
            "references": [{"type": "gallery", "id": f"g{index}"} for index in range(14)],
        },
    )
    assert resp.status_code == 400
    assert "参考图数量 + 最终生成图片数量" in resp.json()["detail"]


def test_oss_temporary_url_detection_includes_volcengine_tos_signature():
    url = (
        "https://ark-content-generation-cn-beijing.tos-cn-beijing.volces.com/output.png"
        "?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Signature=abc"
    )

    assert studio_router.oss_service.is_probably_temporary_url(url) is True


def test_preview_payload_rejects_wan27_4k_when_input_images_present(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": 1.0,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "image_edit",
            "prompt": "把图1做成海报",
            "n": 4,
            "size_mode": "preset",
            "size_preset": "4K",
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 400
    assert "4K" in resp.json()["detail"]


def test_preview_payload_reports_wan27_image_read_error_with_url(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        raise ValueError("HTTP 403，content-type=text/html")

    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://old.example.com/private/ref.png?token=secret"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image",
            "task_kind": "image_edit",
            "prompt": "把图1做成海报",
            "n": 1,
            "group_count": 1,
            "size_mode": "preset",
            "size_preset": "2K",
            "references": [{"type": "gallery", "id": "ref-1"}],
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "第 1 张输入图片无法读取" in detail
    assert "https://old.example.com/private/ref.png" in detail
    assert "HTTP 403" in detail


def test_preview_payload_allows_wan27_input_image_with_alpha(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": 1.0,
            "file_size": 1024,
            "has_alpha": True,
        }

    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image",
            "task_kind": "image_edit",
            "prompt": "编辑图片",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "image_edit"
    assert data["provider_payload"]["model"] == "wan2.7-image"
    assert "bbox_list" not in data["provider_payload"]["parameters"]


def test_preview_payload_ignores_bbox_list_for_wan27_image_edit(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": 1.0,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image",
            "task_kind": "image_edit",
            "prompt": "编辑图片",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
            "bbox_list": [],
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_request"]["task_kind"] == "image_edit"
    assert "bbox_list" not in data["canonical_request"]["normalized_params"]
    assert "bbox_list" not in data["provider_payload"]["parameters"]


def test_generate_wan27_image_edit_ignores_empty_bbox_list(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "PNG",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": 1.0,
            "file_size": 1024,
            "has_alpha": False,
        }

    project_id = _create_project(client, auth_header)
    _patch_async_create_task(monkeypatch)
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "wan27 图片编辑",
            "model": "wan2.7-image",
            "task_kind": "image_edit",
            "prompt": "编辑图片",
            "n": 1,
            "bbox_list": [],
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    generate_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "image_edit",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
            "bbox_list": [],
        },
    )
    assert generate_resp.status_code == 200
    task = generate_resp.json()["task"]
    assert task["task_kind"] == "image_edit"
    assert task["bbox_list"] == []
    assert "bbox_list" not in task["normalized_params"]
    assert "bbox_list" not in task["provider_payload_snapshot"]["parameters"]


def test_generate_wan27_with_references_does_not_inspect_remote_images_before_return(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    scheduled = {"called": False}

    def fake_create_task(coro):
        scheduled["called"] = True
        coro.close()
        return None

    monkeypatch.setattr(studio_router.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )

    async def fail_if_called(_url):
        raise AssertionError("inspect_remote_image should not run before /generate returns")

    monkeypatch.setattr("app.routers.studio.inspect_remote_image", fail_if_called)

    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "wan27 同步探测回归",
            "model": "wan2.7-image",
            "task_kind": "image_edit",
            "prompt": "编辑图片",
            "n": 1,
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    generate_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "image_edit",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
        },
    )

    assert generate_resp.status_code == 200
    task = generate_resp.json()["task"]
    assert scheduled["called"] is True
    assert task["status"] == "generating"


def test_generate_returns_existing_task_when_same_task_is_already_generating(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    scheduled = {"count": 0}

    def fake_create_task(coro):
        scheduled["count"] += 1
        coro.close()
        return None

    monkeypatch.setattr(studio_router.asyncio, "create_task", fake_create_task)

    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "重复提交保护",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成海报",
            "n": 1,
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    first_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "text_to_image",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
        },
    )
    assert first_resp.status_code == 200
    assert first_resp.json()["task"]["status"] == "generating"
    assert scheduled["count"] == 1

    second_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "text_to_image",
            "n": 1,
            "size_mode": "preset",
            "size_preset": "2K",
        },
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["task"]["status"] == "generating"
    assert scheduled["count"] == 1


def test_preview_payload_normalizes_wan27_bbox_and_warns_thinking_mode(client, auth_header, monkeypatch):
    async def mock_inspect_remote_image(_url):
        return {
            "format": "WEBP",
            "width": 320,
            "height": 240,
            "aspect_ratio": 320 / 240,
            "file_size": 1024,
            "has_alpha": False,
        }

    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.webp"]),
    )
    monkeypatch.setattr("app.routers.studio.inspect_remote_image", mock_inspect_remote_image)

    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "interactive_edit",
            "prompt": "把图1中的物体放到框选位置",
            "n": 1,
            "thinking_mode": True,
            "size_mode": "preset",
            "size_preset": "2K",
            "bbox_list": [[[500, 400, -10, 20]]],
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["bbox_list"] == [[[0, 20, 320, 240]]]
    assert any("thinking_mode" in warning for warning in data["validation_warnings"])


def test_preview_payload_rejects_wan27_invalid_custom_size_ratio(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张超长海报",
            "n": 4,
            "size_mode": "custom",
            "custom_width": 2000,
            "custom_height": 100,
            "references": [],
        },
    )
    assert resp.status_code == 400
    assert "宽高比" in resp.json()["detail"]


def test_preview_payload_builds_wan27_custom_text_size(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张 16:9 海报",
            "n": 1,
            "size_mode": "custom",
            "custom_width": 3072,
            "custom_height": 1728,
            "references": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["size"] == "3072*1728"
    assert data["canonical_request"]["normalized_params"]["size"] == "3072*1728"


def test_preview_payload_builds_wan27_custom_portrait_size(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张 9:16 竖版海报",
            "n": 1,
            "size_mode": "custom",
            "custom_width": 1080,
            "custom_height": 1920,
            "references": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_payload"]["parameters"]["size"] == "1080*1920"
    assert data["canonical_request"]["normalized_params"]["size"] == "1080*1920"


def test_generate_wan27_uses_canonical_custom_size(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    _patch_async_create_task(monkeypatch)
    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "wan27 自定义比例",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张 16:9 海报",
            "n": 1,
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    generate_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "text_to_image",
            "n": 1,
            "size": None,
            "size_mode": "custom",
            "size_preset": None,
            "custom_width": 3072,
            "custom_height": 1728,
        },
    )
    assert generate_resp.status_code == 200
    task = generate_resp.json()["task"]
    assert task["size"] == "3072*1728"
    assert task["normalized_params"]["size"] == "3072*1728"
    assert task["provider_payload_snapshot"]["parameters"]["size"] == "3072*1728"


def test_generate_wan27_uses_canonical_portrait_custom_size(client, auth_header, monkeypatch):
    project_id = _create_project(client, auth_header)
    _patch_async_create_task(monkeypatch)
    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "wan27 竖版比例",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张 9:16 竖版海报",
            "n": 1,
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    generate_resp = client.post(
        f"/api/studio/{task_id}/generate",
        headers=auth_header,
        json={
            "task_kind": "text_to_image",
            "n": 1,
            "size": None,
            "size_mode": "custom",
            "size_preset": None,
            "custom_width": 1080,
            "custom_height": 1920,
        },
    )
    assert generate_resp.status_code == 200
    task = generate_resp.json()["task"]
    assert task["size"] == "1080*1920"
    assert task["normalized_params"]["size"] == "1080*1920"
    assert task["provider_payload_snapshot"]["parameters"]["size"] == "1080*1920"


def test_update_studio_task_can_clear_wan27_optional_size_fields(client, auth_header):
    project_id = _create_project(client, auth_header)
    create_resp = client.post(
        "/api/studio",
        headers=auth_header,
        json={
            "project_id": project_id,
            "name": "待清空参数",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成海报",
            "seed": 123,
            "size": "3072*1728",
            "size_mode": "custom",
            "custom_width": 3072,
            "custom_height": 1728,
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/api/studio/{task_id}",
        headers=auth_header,
        json={
            "seed": None,
            "size": None,
            "size_mode": "preset",
            "size_preset": "2K",
            "custom_width": None,
            "custom_height": None,
        },
    )
    assert update_resp.status_code == 200
    task = update_resp.json()
    assert task["seed"] is None
    assert task["size"] is None
    assert task["size_mode"] == "preset"
    assert task["size_preset"] == "2K"
    assert task["custom_width"] is None
    assert task["custom_height"] is None


def test_preview_payload_rejects_invalid_wan27_color_palette(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张海报",
            "n": 1,
            "color_palette": [
                {"hex": "C2D1E6", "ratio": "34.00%"},
                {"hex": "#C0B5B4", "ratio": "33.0%"},
                {"hex": "#636574", "ratio": "33.00%"},
            ],
            "references": [],
        },
    )
    assert resp.status_code == 400
    assert "hex" in resp.json()["detail"]


def test_preview_payload_rejects_invalid_wan27_color_ratio_format(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.7-image-pro",
            "task_kind": "text_to_image",
            "prompt": "生成一张海报",
            "n": 1,
            "color_palette": [
                {"hex": "#C2D1E6", "ratio": "34.0%"},
                {"hex": "#C0B5B4", "ratio": "33.00%"},
                {"hex": "#636574", "ratio": "33.00%"},
            ],
            "references": [],
        },
    )
    assert resp.status_code == 400
    assert "两位小数" in resp.json()["detail"]


def test_preview_payload_accepts_wan25_t2i_custom_size(client, auth_header):
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.5-t2i-preview",
            "task_kind": "text_to_image",
            "prompt": "生成一张电影感海报",
            "n": 1,
            "size_mode": "custom",
            "custom_width": 1536,
            "custom_height": 1024,
            "references": [],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["provider_payload"]["parameters"]["size"] == "1536*1024"
    assert payload["canonical_request"]["normalized_params"]["size_mode"] == "custom"


def test_preview_payload_rejects_wan25_i2i_invalid_custom_size(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "wan2.5-i2i-preview",
            "task_kind": "image_edit",
            "prompt": "把图1做成超长横幅",
            "n": 1,
            "size_mode": "custom",
            "custom_width": 4000,
            "custom_height": 400,
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 400
    assert "宽高比" in resp.json()["detail"] or "总像素" in resp.json()["detail"]


def test_preview_payload_rejects_qwen_image_edit_size_when_n_gt_one(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "qwen-image-edit-plus",
            "task_kind": "image_edit",
            "prompt": "把图1做成广告主视觉",
            "n": 2,
            "size": "1024*1024",
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 400
    assert "n=1" in resp.json()["detail"]


def test_preview_payload_omits_qwen_image2_size_when_not_set(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        "app.routers.studio._resolve_reference_items",
        lambda _refs: _mock_reference_items(["https://oss.example.com/ref.png"]),
    )
    resp = client.post(
        "/api/studio/preview-payload",
        headers=auth_header,
        json={
            "project_id": "p1",
            "model": "qwen-image-2.0-pro",
            "task_kind": "image_edit",
            "prompt": "把图1做成广告主视觉",
            "n": 1,
            "size": "",
            "references": [{"type": "gallery", "id": "g1"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "size" not in data["provider_payload"]["parameters"]
    assert data["canonical_request"]["normalized_params"]["size"] == ""


@pytest.mark.asyncio
async def test_generate_with_qwen_image2_allows_missing_size(monkeypatch):
    captured = {}

    async def fake_generate(self, **kwargs):
        captured.update(kwargs)
        return ["https://oss.example.com/output.png"], "req-123"

    monkeypatch.setattr("app.models_registry.image.qwen_image_2.QwenImage2Service.generate", fake_generate)

    from app.models.studio import StudioTask
    from app.routers.studio import generate_with_qwen_image_2

    task = StudioTask(
        project_id="p1",
        name="qwen2 测试",
        model="qwen-image-2.0-pro",
        prompt="把图1做成海报",
        n=1,
        group_count=1,
    )

    images, request_ids = await generate_with_qwen_image_2(
        task=task,
        ref_urls=["https://oss.example.com/ref.png"],
        api_key="sk-test",
        model_name="qwen-image-2.0-pro",
        size=None,
        prompt_extend=True,
        watermark=False,
        seed=None,
    )

    assert images[0].url == "https://oss.example.com/output.png"
    assert request_ids == ["req-123"]
    assert captured["size"] is None


@pytest.mark.asyncio
async def test_seedream_service_normalizes_success_and_item_errors(monkeypatch):
    from app.models_registry.image.seedream import (
        SEEDREAM_5_LITE_MODEL_INFO,
        SeedreamImageService,
    )

    captured = {}

    class MockResponse:
        status_code = 200
        headers = {"x-tt-logid": "log-123"}

        @staticmethod
        def json():
            return {
                "model": "doubao-seedream-5-0-260128",
                "created": 1770000000,
                "data": [
                    {"url": "https://volc.example.com/a.jpeg", "size": "2048x2048"},
                    {"error": {"code": "ContentRisk", "message": "审核不通过"}},
                ],
                "usage": {"generated_images": 1, "output_tokens": 16384, "total_tokens": 16384},
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["payload"] = json or {}
            return MockResponse()

    monkeypatch.setattr("app.models_registry.image.seedream.httpx.AsyncClient", MockAsyncClient)

    service = SeedreamImageService(SEEDREAM_5_LITE_MODEL_INFO)
    service.configure("volc-key")

    urls, request_id, meta = await service.generate(
        prompt="一张海报",
        images=[],
        size="2K",
        n=2,
        task_kind="sequential_generation",
        prompt_extend=True,
        watermark=False,
        output_format="png",
        web_search=True,
    )

    assert urls == ["https://volc.example.com/a.jpeg"]
    assert request_id == "log-123"
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    assert captured["headers"]["Authorization"] == "Bearer volc-key"
    assert captured["payload"]["model"] == "doubao-seedream-5-0-260128"
    assert captured["payload"]["sequential_image_generation"] == "auto"
    assert captured["payload"]["sequential_image_generation_options"]["max_images"] == 2
    assert captured["payload"]["output_format"] == "png"
    assert meta["usage"]["generated_images"] == 1
    assert meta["item_errors"][0]["code"] == "ContentRisk"
    assert meta["raw_response"]["data"][1]["error"]["message"] == "审核不通过"


@pytest.mark.asyncio
async def test_ensure_generated_images_persisted_marks_local_fallback_warning(monkeypatch):
    images = [
        StudioTaskImage(
            group_index=0,
            url="https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/tmp/output.png",
            prompt_used="prompt",
        )
    ]

    async def fake_persist(_url, _project_id="", max_retries=5):
        return PersistedAssetResult(
            url="/assets/oss_staging/image/project-1/output.png",
            storage_source="local_fallback",
            warning="图片结果转存 OSS 连续失败，已暂时回落到本地文件",
            error="上传失败: timeout",
        )

    monkeypatch.setattr(studio_router.oss_service, "should_persist_generated_url", lambda _url: True)
    monkeypatch.setattr(studio_router.oss_service, "is_current_oss_url", lambda _url: False)
    monkeypatch.setattr(
        studio_router.oss_service,
        "persist_generated_image_with_fallback_async",
        fake_persist,
    )

    report = await studio_router._ensure_generated_images_persisted(
        images,
        "project-1",
        model_id="wan2.7-image-pro",
        request_ids=["req-1"],
        task_ids=["task-1"],
    )

    assert report["errors"] == []
    assert report["warnings"] == ["第 1 张图片 OSS 转存连续失败，已暂时回退为服务器本地文件。"]
    assert images[0].url == "/assets/oss_staging/image/project-1/output.png"
    assert images[0].storage_source == "local_fallback"
    assert "回落到本地文件" in (images[0].storage_warning or "")


def test_expire_local_fallback_images_marks_image_expired(monkeypatch):
    from app.models.studio import StudioTask

    task = StudioTask(
        project_id="p1",
        name="本地回退过期",
        model="wan2.7-image-pro",
        prompt="prompt",
        status="completed",
        provider_payload_snapshot={"model": "wan2.7-image-pro"},
        images=[
            StudioTaskImage(
                group_index=0,
                url="/assets/oss_staging/image/project-1/expired.png",
                storage_source="local_fallback",
                storage_warning="等待自动重传",
                fallback_created_at=datetime.now() - timedelta(days=8),
            )
        ],
    )

    captured = {}
    monkeypatch.setattr(
        studio_router.oss_service,
        "cleanup_local_asset_url",
        lambda url: captured.setdefault("url", url) or True,
    )

    changed = studio_router._expire_local_fallback_images(task, datetime.now())

    assert changed is True
    assert captured["url"] == "/assets/oss_staging/image/project-1/expired.png"
    assert task.images[0].storage_source == "local_expired"
    assert task.images[0].url is None
    assert "自动清理" in (task.images[0].storage_warning or "")


def test_get_studio_task_schedules_due_local_fallback_retry(client, auth_header, registered_user, monkeypatch):
    from app.models.studio import StudioTask
    from app.services.storage import storage_service, set_current_user

    project_id = _create_project(client, auth_header)
    _, user = registered_user
    task = StudioTask(
        project_id=project_id,
        name="待自动重传",
        model="wan2.7-image-pro",
        prompt="prompt",
        status="completed",
        provider_payload_snapshot={"model": "wan2.7-image-pro"},
        images=[
            StudioTaskImage(
                group_index=0,
                url="/assets/oss_staging/image/project-1/retry.png",
                storage_source="local_fallback",
                storage_warning="等待自动重传",
                next_retry_at=datetime.now() - timedelta(minutes=1),
                fallback_created_at=datetime.now(),
            )
        ],
    )
    set_current_user(user["id"])
    storage_service.save_studio_task(task)
    set_current_user(None)

    scheduled = {"count": 0}

    def fake_create_task(coro):
        scheduled["count"] += 1
        coro.close()
        return None

    monkeypatch.setattr(studio_router.asyncio, "create_task", fake_create_task)

    resp = client.get(f"/api/studio/{task.id}", headers=auth_header)

    assert resp.status_code == 200
    assert scheduled["count"] == 1


def test_retry_task_oss_fallbacks_endpoint_updates_task(client, auth_header, registered_user, monkeypatch):
    from app.models.studio import StudioTask
    from app.services.storage import storage_service, set_current_user

    project_id = _create_project(client, auth_header)
    _, user = registered_user
    task = StudioTask(
        project_id=project_id,
        name="手动重传",
        model="wan2.7-image-pro",
        prompt="prompt",
        status="completed",
        provider_payload_snapshot={"model": "wan2.7-image-pro"},
        images=[
            StudioTaskImage(
                group_index=0,
                url="/assets/oss_staging/image/project-1/manual.png",
                storage_source="local_fallback",
                storage_warning="等待手动重传",
                fallback_created_at=datetime.now(),
            )
        ],
    )
    set_current_user(user["id"])
    storage_service.save_studio_task(task)
    set_current_user(None)

    async def fake_retry(task_obj, *, due_only, reason):
        task_obj.images[0].url = "https://oss.example.com/final.png"
        task_obj.images[0].storage_source = "oss"
        task_obj.images[0].storage_warning = None
        task_obj.warnings = []
        storage_service.save_studio_task(task_obj)
        return {
            "retried_image_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "paused_count": 0,
            "expired_count": 0,
        }

    monkeypatch.setattr(studio_router.oss_service, "is_enabled", lambda: True)
    monkeypatch.setattr(studio_router, "_retry_task_local_fallback_images", fake_retry)

    resp = client.post(f"/api/studio/{task.id}/retry-oss", headers=auth_header)

    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["success_count"] == 1
    assert data["task"]["images"][0]["url"] == "https://oss.example.com/final.png"
    assert data["task"]["images"][0]["storage_source"] == "oss"


def test_save_to_gallery_rejects_local_fallback_image(client, auth_header, registered_user):
    from app.models.studio import StudioTask
    from app.services.storage import storage_service, set_current_user

    project_id = _create_project(client, auth_header)
    _, user = registered_user
    image = StudioTaskImage(
        group_index=0,
        url="/assets/oss_staging/image/project-1/local.png",
        storage_source="local_fallback",
        storage_warning="等待重传",
        fallback_created_at=datetime.now(),
    )
    task = StudioTask(
        project_id=project_id,
        name="保存拦截",
        model="wan2.7-image-pro",
        prompt="prompt",
        status="completed",
        provider_payload_snapshot={"model": "wan2.7-image-pro"},
        images=[image],
    )
    set_current_user(user["id"])
    storage_service.save_studio_task(task)
    set_current_user(None)

    resp = client.post(
        f"/api/studio/{task.id}/save-to-gallery",
        headers=auth_header,
        json={"image_ids": [image.id]},
    )

    assert resp.status_code == 409
    assert "本地回退状态" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wan27_async_create_uses_image_generation_endpoint(monkeypatch):
    captured = {}

    class MockResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "request_id": "req-123",
                "output": {
                    "task_id": "task-123",
                    "task_status": "PENDING",
                },
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["payload"] = json or {}
            return MockResponse()

    monkeypatch.setattr("app.models_registry.image.wan27_image.httpx.AsyncClient", MockAsyncClient)

    service = Wan27ImageService()
    service.configure("sk-test")

    task_id = await service.create_task(
        prompt="把图2的机械臂替换到图1中",
        images=["https://oss.example.com/a.png", "https://oss.example.com/b.jpg"],
        size="2K",
        n=1,
        bbox_list=[[[0, 0, 10, 10]], [[5, 5, 20, 20]]],
        watermark=False,
    )

    assert task_id == "task-123"
    assert captured["url"].endswith("/services/aigc/image-generation/generation")
    assert captured["headers"]["X-DashScope-Async"] == "enable"
    assert captured["payload"]["model"] == "wan2.7-image-pro"
    assert captured["payload"]["parameters"]["bbox_list"] == [
        [[0, 0, 10, 10]],
        [[5, 5, 20, 20]],
    ]


@pytest.mark.asyncio
async def test_wan27_get_task_status_reads_failed_output_message(monkeypatch):
    class MockResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "request_id": "req-456",
                "output": {
                    "task_id": "task-456",
                    "task_status": "FAILED",
                    "code": "InvalidParameter",
                    "message": "bbox_list length (0) must match the number of input images (2).",
                },
            }

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return MockResponse()

    monkeypatch.setattr("app.models_registry.image.wan27_image.httpx.AsyncClient", MockAsyncClient)

    service = Wan27ImageService()
    service.configure("sk-test")

    result = await service.get_task_status("task-456")

    assert result.status.value == "failed"
    assert result.error_message == "bbox_list length (0) must match the number of input images (2)."
    assert result.metadata["error_code"] == "InvalidParameter"
    assert result.metadata["error_message"] == "bbox_list length (0) must match the number of input images (2)."


@pytest.mark.asyncio
async def test_generate_with_wan27_image_respects_group_count(monkeypatch):
    from app.models.studio import StudioTask
    from app.models_registry.base import TaskResult, TaskStatus
    from app.routers.studio import generate_with_wan27_image

    create_calls = []

    async def fake_create_task(self, **kwargs):
        call_index = len(create_calls)
        create_calls.append(kwargs)
        self.last_request_id = f"submit-{call_index}"
        return f"task-{call_index}"

    async def fake_get_task_status(self, task_id):
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.SUCCEEDED,
            result=[f"https://oss.example.com/{task_id}-0.png", f"https://oss.example.com/{task_id}-1.png"],
            metadata={"request_id": f"poll-{task_id}"},
        )

    monkeypatch.setattr("app.models_registry.image.wan27_image.Wan27ImageService.create_task", fake_create_task)
    monkeypatch.setattr("app.models_registry.image.wan27_image.Wan27ImageService.get_task_status", fake_get_task_status)
    monkeypatch.setattr(studio_router.oss_service, "is_enabled", lambda: False)

    task = StudioTask(
        project_id="p1",
        name="wan27 并发组数",
        model="wan2.7-image-pro",
        prompt="生成一组竖版海报",
        n=2,
        group_count=3,
    )

    images, task_ids, request_ids, provider_meta = await generate_with_wan27_image(
        task=task,
        api_key="sk-test",
        base_url="",
        ref_urls=[],
        size="1080*1920",
        enable_sequential=False,
        thinking_mode=True,
        bbox_list=None,
        color_palette=[],
        watermark=False,
        seed=None,
    )

    assert len(create_calls) == 3
    assert all(call["n"] == 2 for call in create_calls)
    assert all(call["size"] == "1080*1920" for call in create_calls)
    assert len(images) == 6
    assert task_ids == ["task-0", "task-1", "task-2"]
    assert request_ids == [
        "submit-0", "poll-task-0",
        "submit-1", "poll-task-1",
        "submit-2", "poll-task-2",
    ]
    assert set(provider_meta.keys()) == {"task-0", "task-1", "task-2"}


@pytest.mark.asyncio
async def test_generate_with_wan27_image_preserves_submit_error_meta(monkeypatch):
    from app.models.studio import StudioTask
    from app.routers.studio import generate_with_wan27_image

    async def fake_create_task(self, **kwargs):
        self.last_request_id = "submit-failed-request"
        self.last_error_code = "InvalidParameter"
        self.last_error_message = "transparent png rejected by provider"
        self.last_raw_output = {"task_status": "FAILED", "message": "transparent png rejected by provider"}
        raise RuntimeError(self.last_error_message)

    monkeypatch.setattr("app.models_registry.image.wan27_image.Wan27ImageService.create_task", fake_create_task)
    monkeypatch.setattr(studio_router.oss_service, "is_enabled", lambda: False)

    task = StudioTask(
        project_id="p1",
        name="wan27 提交失败",
        model="wan2.7-image",
        task_kind="image_edit",
        prompt="编辑透明 PNG",
        n=1,
        group_count=1,
    )

    images, task_ids, request_ids, provider_meta = await generate_with_wan27_image(
        task=task,
        api_key="sk-test",
        base_url="",
        ref_urls=["https://oss.example.com/transparent.png"],
        size="2K",
        enable_sequential=False,
        thinking_mode=None,
        bbox_list=None,
        color_palette=[],
        watermark=False,
        seed=None,
    )

    assert images == []
    assert task_ids == []
    assert request_ids == ["submit-failed-request"]
    assert task._group_errors == ["transparent png rejected by provider"]
    meta = provider_meta["submit-failed-request"]
    assert meta["error_code"] == "InvalidParameter"
    assert meta["error_message"] == "transparent png rejected by provider"
    assert meta["request_id"] == "submit-failed-request"
    assert meta["raw_output"]["task_status"] == "FAILED"
