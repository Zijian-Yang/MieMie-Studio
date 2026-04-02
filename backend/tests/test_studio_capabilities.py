from app.models.studio import ReferenceItem


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
