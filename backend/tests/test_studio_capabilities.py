import pytest

from app.models.studio import ReferenceItem
from app.routers import studio as studio_router
from app.models_registry.image.wan27_image import Wan27ImageService
from app.routers.studio import get_image_size_templates


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


def test_preview_payload_rejects_wan27_input_image_with_alpha(client, auth_header, monkeypatch):
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
    assert resp.status_code == 400
    assert "透明通道" in resp.json()["detail"]


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
