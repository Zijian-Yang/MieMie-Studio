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
