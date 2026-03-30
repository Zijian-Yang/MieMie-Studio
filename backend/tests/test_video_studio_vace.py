import io

from app.models.media import VideoStudioTask
from app.routers import video_studio as video_studio_router
from app.services.storage import storage_service, set_current_user


def _create_project(client, auth_header):
    resp = client.post("/api/projects", headers=auth_header, json={"name": "VACE测试项目"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _patch_async_create_task(monkeypatch):
    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(video_studio_router.asyncio, "create_task", fake_create_task)


class TestVideoStudioVace:
    def test_prepare_source_video_success(self, client, auth_header, monkeypatch):
        async def fake_prepare(self, project_id: str, video_url: str):
            return {
                "preview_image_data_url": "data:image/jpeg;base64,test",
                "preview_image_url": "https://oss.example.com/preview.jpg",
                "metadata": {
                    "width": 1280,
                    "height": 720,
                    "fps": 24.0,
                    "duration": 4.0,
                    "frame_count": 96,
                    "file_size": 1024,
                    "format": "mp4",
                    "warnings": [],
                },
                "warnings": [],
            }

        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "prepare_source_video", fake_prepare)

        resp = client.post(
            "/api/video-studio/prepare-source-video",
            headers=auth_header,
            json={"project_id": "p1", "video_url": "https://oss.example.com/source.mp4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview_image_data_url"].startswith("data:image/jpeg;base64,")
        assert data["metadata"]["width"] == 1280

    def test_upload_mask_success(self, client, auth_header, monkeypatch):
        async def fake_upload(self, project_id: str, source_video_url: str, mask_bytes: bytes):
            assert project_id == "p1"
            assert source_video_url.endswith(".mp4")
            assert mask_bytes
            return {
                "mask_image_url": "https://oss.example.com/mask.png",
                "width": 1280,
                "height": 720,
            }

        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "upload_mask", fake_upload)

        resp = client.post(
            "/api/video-studio/upload-mask",
            headers=auth_header,
            data={"project_id": "p1", "source_video_url": "https://oss.example.com/source.mp4"},
            files={"mask_file": ("mask.png", io.BytesIO(b"mask-bytes"), "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["mask_image_url"] == "https://oss.example.com/mask.png"

    def test_create_video_repainting_task_success(self, client, auth_header, monkeypatch):
        project_id = _create_project(client, auth_header)
        _patch_async_create_task(monkeypatch)
        monkeypatch.setattr(video_studio_router.oss_service, "is_enabled", lambda: True)

        async def fake_validate_source(self, video_url: str):
            return {"width": 1280, "height": 720, "fps": 24.0, "duration": 4.0}

        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "validate_source_video", fake_validate_source)

        resp = client.post(
            "/api/video-studio",
            headers=auth_header,
            json={
                "project_id": project_id,
                "task_type": "video_repainting",
                "name": "重绘任务",
                "source_video_url": "https://oss.example.com/source.mp4",
                "source_video_preview_url": "https://oss.example.com/preview.jpg",
                "prompt": "把主角替换成蒸汽朋克机器人",
                "control_condition": "depth",
                "strength": 0.8,
                "prompt_extend": False,
                "group_count": 1,
                "model": "wanx2.1-vace-plus",
            },
        )
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert task["task_type"] == "video_repainting"
        assert task["model"] == "wanx2.1-vace-plus"
        assert task["source_video_url"].endswith(".mp4")
        assert task["duration"] == 4

    def test_create_video_edit_rejects_fixed_expand_ratio(self, client, auth_header, monkeypatch):
        project_id = _create_project(client, auth_header)
        _patch_async_create_task(monkeypatch)
        monkeypatch.setattr(video_studio_router.oss_service, "is_enabled", lambda: True)

        async def fake_validate_source(self, video_url: str):
            return {"width": 1280, "height": 720, "fps": 24.0, "duration": 5.0}

        async def fake_validate_mask(self, mask_image_url: str, expected_width: int, expected_height: int):
            return {"width": expected_width, "height": expected_height}

        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "validate_source_video", fake_validate_source)
        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "validate_mask_image", fake_validate_mask)

        resp = client.post(
            "/api/video-studio",
            headers=auth_header,
            json={
                "project_id": project_id,
                "task_type": "video_edit",
                "source_video_url": "https://oss.example.com/source.mp4",
                "mask_image_url": "https://oss.example.com/mask.png",
                "prompt": "把窗户改成彩色玻璃",
                "mask_type": "fixed",
                "expand_ratio": 0.2,
                "model": "wanx2.1-vace-plus",
            },
        )
        assert resp.status_code == 400
        assert "fixed模式下不支持expand_ratio" in resp.json()["detail"]

    def test_get_vace_task_status_success(self, client, auth_header, registered_user, monkeypatch):
        project_id = _create_project(client, auth_header)
        _, user = registered_user
        set_current_user(user["id"])
        task = VideoStudioTask(
            project_id=project_id,
            name="局部编辑任务",
            task_type="video_edit",
            model="wanx2.1-vace-plus",
            prompt="把招牌换成霓虹灯",
            source_video_url="https://oss.example.com/source.mp4",
            source_video_preview_url="https://oss.example.com/preview.jpg",
            mask_image_url="https://oss.example.com/mask.png",
            mask_frame_id=1,
            task_ids=["api-task-1"],
            status="processing",
        )
        storage_service.save_video_studio_task(task)

        async def fake_status(self, task_id: str, project_id: str = ""):
            assert task_id == "api-task-1"
            return "SUCCEEDED", "https://oss.example.com/result.mp4"

        monkeypatch.setattr(video_studio_router.VaceVideoEditService, "get_task_status", fake_status)

        resp = client.get(f"/api/video-studio/{task.id}/status", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()["task"]
        assert data["status"] == "succeeded"
        assert data["video_urls"] == ["https://oss.example.com/result.mp4"]
