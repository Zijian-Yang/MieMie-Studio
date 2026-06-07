"""
JSON 文件存储服务

支持多用户数据隔离和并发安全：
- 通过 set_current_user() 设置当前用户
- storage_service 会自动使用当前用户的数据目录
- 使用文件锁确保并发安全
- 如果未设置用户，使用全局默认目录（向后兼容）
"""

import json
import os
import logging
import fcntl
import threading
from uuid import uuid4
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import Optional, List
from datetime import datetime
from contextvars import ContextVar

from app.models.project import Project
from app.models.character import Character
from app.models.scene import Scene
from app.models.prop import Prop
from app.models.frame import Frame
from app.models.video import Video
from app.models.style import Style
from app.models.gallery import GalleryImage
from app.models.image_benchmark import ImageBenchmarkDataset, ImageBenchmarkRun, ImageBenchmarkSuite
from app.models.video_benchmark import VideoBenchmarkDataset, VideoBenchmarkRun, VideoBenchmarkSuite
from app.models.studio import StudioTask
from app.models.media import AudioItem, VideoItem, TextItem, VideoStudioTask
from app.models.audio_studio import AudioStudioTask, VoiceProfile

# 当前用户 ID 的上下文变量
_current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)


def set_current_user(user_id: Optional[str]):
    """设置当前请求的用户 ID"""
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[str]:
    """获取当前请求的用户 ID"""
    return _current_user_id.get()


class StorageService:
    """JSON 文件存储服务 - 支持并发安全"""
    
    def __init__(self, data_dir: Optional[str] = None, owner_user_id: Optional[str] = None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        self.owner_user_id = owner_user_id
        
        self.projects_dir = self.data_dir / "projects"
        self.characters_dir = self.data_dir / "characters"
        self.scenes_dir = self.data_dir / "scenes"
        self.props_dir = self.data_dir / "props"
        self.frames_dir = self.data_dir / "frames"
        self.videos_dir = self.data_dir / "videos"
        self.styles_dir = self.data_dir / "styles"
        self.gallery_dir = self.data_dir / "gallery"
        self.studio_dir = self.data_dir / "studio"
        # 新增媒体库目录
        self.audio_dir = self.data_dir / "audio"
        self.video_library_dir = self.data_dir / "video_library"
        self.text_library_dir = self.data_dir / "text_library"
        self.video_studio_dir = self.data_dir / "video_studio"
        self.audio_studio_dir = self.data_dir / "audio_studio"
        self.voices_dir = self.data_dir / "voices"
        self.image_benchmark_datasets_dir = self.data_dir / "image_benchmark_datasets"
        self.image_benchmark_suites_dir = self.data_dir / "image_benchmark_suites"
        self.image_benchmark_runs_dir = self.data_dir / "image_benchmark_runs"
        self.video_benchmark_datasets_dir = self.data_dir / "video_benchmark_datasets"
        self.video_benchmark_suites_dir = self.data_dir / "video_benchmark_suites"
        self.video_benchmark_runs_dir = self.data_dir / "video_benchmark_runs"

        self._lock = threading.RLock()
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保所有目录存在"""
        for dir_path in [
            self.projects_dir, self.characters_dir, self.scenes_dir,
            self.props_dir, self.frames_dir, self.videos_dir, self.styles_dir,
            self.gallery_dir, self.studio_dir,
            self.audio_dir, self.video_library_dir, self.text_library_dir, self.video_studio_dir,
            self.audio_studio_dir, self.voices_dir,
            self.image_benchmark_datasets_dir, self.image_benchmark_suites_dir, self.image_benchmark_runs_dir,
            self.video_benchmark_datasets_dir, self.video_benchmark_suites_dir, self.video_benchmark_runs_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _serialize_datetime(self, obj):
        """序列化 datetime 对象"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _get_owner_user_id(self) -> Optional[str]:
        return self.owner_user_id or get_current_user_id()
    
    def _read_json_with_lock(self, file_path: Path) -> Optional[dict]:
        """带文件锁的 JSON 读取"""
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享锁
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _write_json_with_lock(self, file_path: Path, data: dict):
        """原子写入 JSON 文件：写临时文件 → fsync → os.replace"""
        tmp_path = file_path.with_name(
            f".{file_path.name}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
        )
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
                try:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(str(tmp_path), str(file_path))
        except Exception:
            # 清理临时文件
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    # ============ Project ============
    
    def save_project(self, project: Project) -> None:
        """保存项目（线程安全）"""
        from app.repositories.project_runtime import (
            json_archive_writes_enabled,
            save_project_primary,
            shadow_save_project,
        )

        owner_user_id = self._get_owner_user_id()
        project.updated_at = datetime.now()
        if save_project_primary(owner_user_id, project):
            if json_archive_writes_enabled():
                with self._lock:
                    file_path = self.projects_dir / f"{project.id}.json"
                    self._write_json_with_lock(file_path, project.model_dump())
            return

        with self._lock:
            file_path = self.projects_dir / f"{project.id}.json"
            self._write_json_with_lock(file_path, project.model_dump())
        shadow_save_project(owner_user_id, project)
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目（线程安全）"""
        from app.repositories.project_runtime import read_project

        return read_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_project_from_file(project_id),
        )

    def _get_project_from_file(self, project_id: str) -> Optional[Project]:
        file_path = self.projects_dir / f"{project_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Project(**data)
        return None
    
    def list_projects(self) -> List[Project]:
        """列出所有项目（线程安全）"""
        from app.repositories.project_runtime import read_projects

        return read_projects(self._get_owner_user_id(), self._list_projects_from_file)

    def _list_projects_from_file(self) -> List[Project]:
        projects = []
        with self._lock:
            for file_path in self.projects_dir.glob("*.json"):
                data = self._read_json_with_lock(file_path)
                if data:
                    try:
                        projects.append(Project(**data))
                    except Exception as e:
                        logger.warning(f"跳过格式错误的项目文件 {file_path.name}: {e}")
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)
    
    def delete_project(self, project_id: str) -> None:
        """删除项目（线程安全）"""
        from app.repositories.project_runtime import (
            json_archive_writes_enabled,
            mark_project_deleted_primary,
            shadow_mark_project_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_project_deleted_primary(owner_user_id, project_id):
            if json_archive_writes_enabled():
                with self._lock:
                    file_path = self.projects_dir / f"{project_id}.json"
                    if file_path.exists():
                        file_path.unlink()
            return

        with self._lock:
            file_path = self.projects_dir / f"{project_id}.json"
            if file_path.exists():
                file_path.unlink()
        shadow_mark_project_deleted(owner_user_id, project_id)
    
    # ============ Character ============
    
    def save_character(self, character: Character) -> None:
        """保存角色（线程安全）"""
        with self._lock:
            character.updated_at = datetime.now()
            file_path = self.characters_dir / f"{character.id}.json"
            self._write_json_with_lock(file_path, character.model_dump())
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """获取角色"""
        file_path = self.characters_dir / f"{character_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Character(**data)
        return None
    
    def delete_character(self, character_id: str) -> None:
        """删除角色"""
        file_path = self.characters_dir / f"{character_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Scene ============
    
    def save_scene(self, scene: Scene) -> None:
        """保存场景（线程安全）"""
        with self._lock:
            scene.updated_at = datetime.now()
            file_path = self.scenes_dir / f"{scene.id}.json"
            self._write_json_with_lock(file_path, scene.model_dump())
    
    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取场景"""
        file_path = self.scenes_dir / f"{scene_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Scene(**data)
        return None
    
    def delete_scene(self, scene_id: str) -> None:
        """删除场景"""
        file_path = self.scenes_dir / f"{scene_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Prop ============
    
    def save_prop(self, prop: Prop) -> None:
        """保存道具（线程安全）"""
        with self._lock:
            prop.updated_at = datetime.now()
            file_path = self.props_dir / f"{prop.id}.json"
            self._write_json_with_lock(file_path, prop.model_dump())
    
    def get_prop(self, prop_id: str) -> Optional[Prop]:
        """获取道具"""
        file_path = self.props_dir / f"{prop_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Prop(**data)
        return None
    
    def delete_prop(self, prop_id: str) -> None:
        """删除道具"""
        file_path = self.props_dir / f"{prop_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Frame ============
    
    def save_frame(self, frame: Frame) -> None:
        """保存首帧（线程安全）"""
        with self._lock:
            frame.updated_at = datetime.now()
            file_path = self.frames_dir / f"{frame.id}.json"
            self._write_json_with_lock(file_path, frame.model_dump())
    
    def get_frame(self, frame_id: str) -> Optional[Frame]:
        """获取首帧"""
        file_path = self.frames_dir / f"{frame_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Frame(**data)
        return None
    
    def get_frame_by_shot(self, project_id: str, shot_id: str) -> Optional[Frame]:
        """根据分镜ID获取首帧"""
        for file_path in self.frames_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id and data.get("shot_id") == shot_id:
                return Frame(**data)
        return None
    
    def get_frames_by_project(self, project_id: str) -> List[Frame]:
        """获取项目所有首帧"""
        frames = []
        for file_path in self.frames_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                frames.append(Frame(**data))
        return sorted(frames, key=lambda f: f.shot_number)
    
    def delete_frame(self, frame_id: str) -> None:
        """删除首帧"""
        file_path = self.frames_dir / f"{frame_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video ============
    
    def save_video(self, video: Video) -> None:
        """保存视频（线程安全）"""
        with self._lock:
            video.updated_at = datetime.now()
            file_path = self.videos_dir / f"{video.id}.json"
            self._write_json_with_lock(file_path, video.model_dump())
    
    def get_video(self, video_id: str) -> Optional[Video]:
        """获取视频"""
        file_path = self.videos_dir / f"{video_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Video(**data)
        return None

    def get_video_by_task(self, task_id: str) -> Optional[Video]:
        """根据任务ID获取视频"""
        for file_path in self.videos_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data:
                task = data.get("task")
                if task and task.get("task_id") == task_id:
                    return Video(**data)
        return None

    def get_videos_by_project(self, project_id: str) -> List[Video]:
        """获取项目所有视频"""
        videos = []
        for file_path in self.videos_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                videos.append(Video(**data))
        return sorted(videos, key=lambda v: v.shot_number)

    def get_video_by_shot(self, project_id: str, shot_id: str) -> Optional[Video]:
        """根据分镜ID获取视频"""
        for file_path in self.videos_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id and data.get("shot_id") == shot_id:
                return Video(**data)
        return None
    
    def delete_video(self, video_id: str) -> None:
        """删除视频"""
        file_path = self.videos_dir / f"{video_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Style ============
    
    def save_style(self, style: Style) -> None:
        """保存风格（线程安全）"""
        with self._lock:
            style.updated_at = datetime.now()
            file_path = self.styles_dir / f"{style.id}.json"
            self._write_json_with_lock(file_path, style.model_dump())
    
    def get_style(self, style_id: str) -> Optional[Style]:
        """获取风格"""
        file_path = self.styles_dir / f"{style_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Style(**data)
        return None
    
    def delete_style(self, style_id: str) -> None:
        """删除风格"""
        file_path = self.styles_dir / f"{style_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Gallery ============
    
    def save_gallery_image(self, image: GalleryImage) -> None:
        """保存图库图片（线程安全）"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            save_gallery_image_primary,
            shadow_save_gallery_image,
        )

        image.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_gallery_image_primary(owner_user_id, image):
            if json_archive_writes_enabled():
                self._save_gallery_image_to_file(image)
            return

        self._save_gallery_image_to_file(image)
        shadow_save_gallery_image(owner_user_id, image)

    def _save_gallery_image_to_file(self, image: GalleryImage) -> None:
        with self._lock:
            file_path = self.gallery_dir / f"{image.id}.json"
            self._write_json_with_lock(file_path, image.model_dump())
    
    def get_gallery_image(self, image_id: str) -> Optional[GalleryImage]:
        """获取图库图片"""
        from app.repositories.media_asset_runtime import read_gallery_image

        return read_gallery_image(
            self._get_owner_user_id(),
            image_id,
            lambda: self._get_gallery_image_from_file(image_id),
        )

    def _get_gallery_image_from_file(self, image_id: str) -> Optional[GalleryImage]:
        file_path = self.gallery_dir / f"{image_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return GalleryImage(**data)
        return None

    def get_gallery_images_by_project(self, project_id: str) -> List[GalleryImage]:
        """获取项目所有图库图片"""
        from app.repositories.media_asset_runtime import read_gallery_images_for_project

        return read_gallery_images_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_gallery_images_by_project_from_file(project_id),
        )

    def _get_gallery_images_by_project_from_file(self, project_id: str) -> List[GalleryImage]:
        images = []
        for file_path in self.gallery_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                images.append(GalleryImage(**data))
        return sorted(images, key=lambda i: i.created_at, reverse=True)
    
    def delete_gallery_image(self, image_id: str) -> None:
        """删除图库图片"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            mark_media_asset_deleted_primary,
            shadow_mark_media_asset_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_media_asset_deleted_primary(owner_user_id, image_id):
            if json_archive_writes_enabled():
                self._delete_gallery_image_from_file(image_id)
            return

        self._delete_gallery_image_from_file(image_id)
        shadow_mark_media_asset_deleted(owner_user_id, image_id)

    def _delete_gallery_image_from_file(self, image_id: str) -> None:
        file_path = self.gallery_dir / f"{image_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Studio Task ============
    
    def save_studio_task(self, task: StudioTask) -> None:
        """保存图片工作室任务（线程安全）"""
        from app.repositories.studio_task_runtime import (
            json_archive_writes_enabled,
            save_studio_task_primary,
            shadow_save_studio_task,
        )

        task.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_studio_task_primary(owner_user_id, task):
            if json_archive_writes_enabled():
                self._save_studio_task_to_file(task)
            return

        self._save_studio_task_to_file(task)
        shadow_save_studio_task(owner_user_id, task)

    def _save_studio_task_to_file(self, task: StudioTask) -> None:
        with self._lock:
            file_path = self.studio_dir / f"{task.id}.json"
            self._write_json_with_lock(file_path, task.model_dump())
    
    def get_studio_task(self, task_id: str) -> Optional[StudioTask]:
        """获取图片工作室任务"""
        from app.repositories.studio_task_runtime import read_studio_task

        return read_studio_task(
            self._get_owner_user_id(),
            task_id,
            lambda: self._get_studio_task_from_file(task_id),
        )

    def _get_studio_task_from_file(self, task_id: str) -> Optional[StudioTask]:
        file_path = self.studio_dir / f"{task_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return StudioTask(**data)
        return None

    def get_studio_tasks_by_project(self, project_id: str) -> List[StudioTask]:
        """获取项目所有图片工作室任务"""
        from app.repositories.studio_task_runtime import read_studio_tasks_for_project

        return read_studio_tasks_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_studio_tasks_by_project_from_file(project_id),
        )

    def _get_studio_tasks_by_project_from_file(self, project_id: str) -> List[StudioTask]:
        tasks = []
        for file_path in self.studio_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                tasks.append(StudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def delete_studio_task(self, task_id: str) -> None:
        """删除图片工作室任务"""
        from app.repositories.studio_task_runtime import (
            json_archive_writes_enabled,
            mark_studio_task_deleted_primary,
            shadow_mark_studio_task_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_studio_task_deleted_primary(owner_user_id, task_id):
            if json_archive_writes_enabled():
                self._delete_studio_task_from_file(task_id)
            return

        self._delete_studio_task_from_file(task_id)
        shadow_mark_studio_task_deleted(owner_user_id, task_id)

    def _delete_studio_task_from_file(self, task_id: str) -> None:
        file_path = self.studio_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Audio Library ============
    
    def save_audio_item(self, audio: AudioItem) -> None:
        """保存音频项（线程安全）"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            save_audio_item_primary,
            shadow_save_audio_item,
        )

        audio.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_audio_item_primary(owner_user_id, audio):
            if json_archive_writes_enabled():
                self._save_audio_item_to_file(audio)
            return

        self._save_audio_item_to_file(audio)
        shadow_save_audio_item(owner_user_id, audio)

    def _save_audio_item_to_file(self, audio: AudioItem) -> None:
        with self._lock:
            file_path = self.audio_dir / f"{audio.id}.json"
            self._write_json_with_lock(file_path, audio.model_dump())
    
    def get_audio_item(self, audio_id: str) -> Optional[AudioItem]:
        """获取音频项"""
        from app.repositories.media_asset_runtime import read_audio_item

        return read_audio_item(
            self._get_owner_user_id(),
            audio_id,
            lambda: self._get_audio_item_from_file(audio_id),
        )

    def _get_audio_item_from_file(self, audio_id: str) -> Optional[AudioItem]:
        file_path = self.audio_dir / f"{audio_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return AudioItem(**data)
        return None

    def get_audio_items(self, project_id: str) -> List[AudioItem]:
        """获取项目所有音频"""
        from app.repositories.media_asset_runtime import read_audio_items_for_project

        return read_audio_items_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_audio_items_from_file(project_id),
        )

    def _get_audio_items_from_file(self, project_id: str) -> List[AudioItem]:
        audios = []
        for file_path in self.audio_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                audios.append(AudioItem(**data))
        return sorted(audios, key=lambda a: a.created_at, reverse=True)
    
    def delete_audio_item(self, audio_id: str) -> None:
        """删除音频项"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            mark_media_asset_deleted_primary,
            shadow_mark_media_asset_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_media_asset_deleted_primary(owner_user_id, audio_id):
            if json_archive_writes_enabled():
                self._delete_audio_item_from_file(audio_id)
            return

        self._delete_audio_item_from_file(audio_id)
        shadow_mark_media_asset_deleted(owner_user_id, audio_id)

    def _delete_audio_item_from_file(self, audio_id: str) -> None:
        file_path = self.audio_dir / f"{audio_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video Library ============
    
    def save_video_item(self, video: VideoItem) -> None:
        """保存视频项（线程安全）"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            save_video_item_primary,
            shadow_save_video_item,
        )

        video.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_video_item_primary(owner_user_id, video):
            if json_archive_writes_enabled():
                self._save_video_item_to_file(video)
            return

        self._save_video_item_to_file(video)
        shadow_save_video_item(owner_user_id, video)

    def _save_video_item_to_file(self, video: VideoItem) -> None:
        with self._lock:
            file_path = self.video_library_dir / f"{video.id}.json"
            self._write_json_with_lock(file_path, video.model_dump())
    
    def get_video_item(self, video_id: str) -> Optional[VideoItem]:
        """获取视频项"""
        from app.repositories.media_asset_runtime import read_video_item

        return read_video_item(
            self._get_owner_user_id(),
            video_id,
            lambda: self._get_video_item_from_file(video_id),
        )

    def _get_video_item_from_file(self, video_id: str) -> Optional[VideoItem]:
        file_path = self.video_library_dir / f"{video_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VideoItem(**data)
        return None

    def get_video_items(self, project_id: str) -> List[VideoItem]:
        """获取项目所有视频"""
        from app.repositories.media_asset_runtime import read_video_items_for_project

        return read_video_items_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_video_items_from_file(project_id),
        )

    def _get_video_items_from_file(self, project_id: str) -> List[VideoItem]:
        videos = []
        for file_path in self.video_library_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                videos.append(VideoItem(**data))
        return sorted(videos, key=lambda v: v.created_at, reverse=True)
    
    def delete_video_item(self, video_id: str) -> None:
        """删除视频项"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            mark_media_asset_deleted_primary,
            shadow_mark_media_asset_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_media_asset_deleted_primary(owner_user_id, video_id):
            if json_archive_writes_enabled():
                self._delete_video_item_from_file(video_id)
            return

        self._delete_video_item_from_file(video_id)
        shadow_mark_media_asset_deleted(owner_user_id, video_id)

    def _delete_video_item_from_file(self, video_id: str) -> None:
        file_path = self.video_library_dir / f"{video_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Text Library ============
    
    def save_text_item(self, text: TextItem) -> None:
        """保存文本项（线程安全）"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            save_text_item_primary,
            shadow_save_text_item,
        )

        text.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_text_item_primary(owner_user_id, text):
            if json_archive_writes_enabled():
                self._save_text_item_to_file(text)
            return

        self._save_text_item_to_file(text)
        shadow_save_text_item(owner_user_id, text)

    def _save_text_item_to_file(self, text: TextItem) -> None:
        with self._lock:
            file_path = self.text_library_dir / f"{text.id}.json"
            self._write_json_with_lock(file_path, text.model_dump())
    
    def get_text_item(self, text_id: str) -> Optional[TextItem]:
        """获取文本项"""
        from app.repositories.media_asset_runtime import read_text_item

        return read_text_item(
            self._get_owner_user_id(),
            text_id,
            lambda: self._get_text_item_from_file(text_id),
        )

    def _get_text_item_from_file(self, text_id: str) -> Optional[TextItem]:
        file_path = self.text_library_dir / f"{text_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return TextItem(**data)
        return None

    def get_text_items(self, project_id: str) -> List[TextItem]:
        """获取项目所有文本"""
        from app.repositories.media_asset_runtime import read_text_items_for_project

        return read_text_items_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_text_items_from_file(project_id),
        )

    def _get_text_items_from_file(self, project_id: str) -> List[TextItem]:
        texts = []
        for file_path in self.text_library_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                texts.append(TextItem(**data))
        return sorted(texts, key=lambda t: t.created_at, reverse=True)
    
    def delete_text_item(self, text_id: str) -> None:
        """删除文本项"""
        from app.repositories.media_asset_runtime import (
            json_archive_writes_enabled,
            mark_text_item_deleted_primary,
            shadow_mark_text_item_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_text_item_deleted_primary(owner_user_id, text_id):
            if json_archive_writes_enabled():
                self._delete_text_item_from_file(text_id)
            return

        self._delete_text_item_from_file(text_id)
        shadow_mark_text_item_deleted(owner_user_id, text_id)

    def _delete_text_item_from_file(self, text_id: str) -> None:
        file_path = self.text_library_dir / f"{text_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video Studio ============
    
    def save_video_studio_task(self, task: VideoStudioTask) -> None:
        """保存视频工作室任务（线程安全）"""
        from app.repositories.video_studio_task_runtime import (
            json_archive_writes_enabled,
            save_video_studio_task_primary,
            shadow_save_video_studio_task,
        )

        task.updated_at = datetime.now()
        owner_user_id = self._get_owner_user_id()
        if save_video_studio_task_primary(owner_user_id, task):
            if json_archive_writes_enabled():
                self._save_video_studio_task_to_file(task)
            return

        self._save_video_studio_task_to_file(task)
        shadow_save_video_studio_task(owner_user_id, task)

    def _save_video_studio_task_to_file(self, task: VideoStudioTask) -> None:
        with self._lock:
            file_path = self.video_studio_dir / f"{task.id}.json"
            self._write_json_with_lock(file_path, task.model_dump())
    
    def _get_video_studio_task_from_file(self, task_id: str) -> Optional[VideoStudioTask]:
        file_path = self.video_studio_dir / f"{task_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VideoStudioTask(**data)
        return None

    def _get_video_studio_tasks_from_file(self, project_id: str) -> List[VideoStudioTask]:
        tasks = []
        for file_path in self.video_studio_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                tasks.append(VideoStudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def _get_all_video_studio_tasks_from_file(self) -> List[VideoStudioTask]:
        tasks = []
        for file_path in self.video_studio_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data:
                tasks.append(VideoStudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def get_video_studio_task(self, task_id: str) -> Optional[VideoStudioTask]:
        """获取视频工作室任务"""
        from app.repositories.video_studio_task_runtime import read_video_studio_task

        return read_video_studio_task(
            self._get_owner_user_id(),
            task_id,
            lambda: self._get_video_studio_task_from_file(task_id),
        )

    def get_video_studio_tasks(self, project_id: str) -> List[VideoStudioTask]:
        """获取项目所有视频工作室任务"""
        from app.repositories.video_studio_task_runtime import (
            read_video_studio_tasks_for_project,
        )

        return read_video_studio_tasks_for_project(
            self._get_owner_user_id(),
            project_id,
            lambda: self._get_video_studio_tasks_from_file(project_id),
        )

    def get_all_video_studio_tasks(self) -> List[VideoStudioTask]:
        """获取当前存储目录下所有视频工作室任务"""
        from app.repositories.video_studio_task_runtime import read_all_video_studio_tasks

        return read_all_video_studio_tasks(
            self._get_owner_user_id(),
            self._get_all_video_studio_tasks_from_file,
        )
    
    def delete_video_studio_task(self, task_id: str) -> None:
        """删除视频工作室任务"""
        from app.repositories.video_studio_task_runtime import (
            json_archive_writes_enabled,
            mark_video_studio_task_deleted_primary,
            shadow_mark_video_studio_task_deleted,
        )

        owner_user_id = self._get_owner_user_id()
        if mark_video_studio_task_deleted_primary(owner_user_id, task_id):
            if json_archive_writes_enabled():
                self._delete_video_studio_task_from_file(task_id)
            return

        self._delete_video_studio_task_from_file(task_id)
        shadow_mark_video_studio_task_deleted(owner_user_id, task_id)

    def _delete_video_studio_task_from_file(self, task_id: str) -> None:
        file_path = self.video_studio_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Audio Studio ============

    def save_audio_studio_task(self, task: AudioStudioTask) -> None:
        """保存音频工作室任务（线程安全）"""
        with self._lock:
            task.updated_at = datetime.now()
            file_path = self.audio_studio_dir / f"{task.id}.json"
            self._write_json_with_lock(file_path, task.model_dump())

    def get_audio_studio_task(self, task_id: str) -> Optional[AudioStudioTask]:
        """获取音频工作室任务"""
        file_path = self.audio_studio_dir / f"{task_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return AudioStudioTask(**data)
        return None

    def get_audio_studio_tasks(self, project_id: str) -> List[AudioStudioTask]:
        """获取项目所有音频工作室任务"""
        tasks = []
        for file_path in self.audio_studio_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                tasks.append(AudioStudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def delete_audio_studio_task(self, task_id: str) -> None:
        """删除音频工作室任务"""
        file_path = self.audio_studio_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Voice Profiles ============

    def save_voice_profile(self, profile: VoiceProfile) -> None:
        """保存音色档案（线程安全）"""
        with self._lock:
            profile.updated_at = datetime.now()
            file_path = self.voices_dir / f"{profile.id}.json"
            self._write_json_with_lock(file_path, profile.model_dump())

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """获取音色档案"""
        file_path = self.voices_dir / f"{profile_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VoiceProfile(**data)
        return None

    def get_voice_profiles(self, project_id: str) -> List[VoiceProfile]:
        """获取项目所有音色档案"""
        profiles = []
        for file_path in self.voices_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                profiles.append(VoiceProfile(**data))
        return sorted(profiles, key=lambda p: p.created_at, reverse=True)

    def get_voice_profile_by_voice_id(self, voice_id: str) -> Optional[VoiceProfile]:
        """通过 DashScope voice_id 获取音色档案"""
        for file_path in self.voices_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("voice_id") == voice_id:
                return VoiceProfile(**data)
        return None

    def delete_voice_profile(self, profile_id: str) -> None:
        """删除音色档案"""
        file_path = self.voices_dir / f"{profile_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Image Benchmark Dataset ============

    def save_image_benchmark_dataset(self, dataset: ImageBenchmarkDataset) -> None:
        """保存图片测评数据集"""
        with self._lock:
            dataset.updated_at = datetime.now()
            file_path = self.image_benchmark_datasets_dir / f"{dataset.id}.json"
            self._write_json_with_lock(file_path, dataset.model_dump())

    def get_image_benchmark_dataset(self, dataset_id: str) -> Optional[ImageBenchmarkDataset]:
        """获取图片测评数据集"""
        file_path = self.image_benchmark_datasets_dir / f"{dataset_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return ImageBenchmarkDataset(**data)
        return None

    def get_image_benchmark_datasets(self, project_id: str) -> List[ImageBenchmarkDataset]:
        """获取项目下的图片测评数据集"""
        datasets = []
        for file_path in self.image_benchmark_datasets_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                datasets.append(ImageBenchmarkDataset(**data))
        return sorted(datasets, key=lambda item: item.updated_at, reverse=True)

    def delete_image_benchmark_dataset(self, dataset_id: str) -> None:
        """删除图片测评数据集"""
        file_path = self.image_benchmark_datasets_dir / f"{dataset_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Image Benchmark Suite ============

    def save_image_benchmark_suite(self, suite: ImageBenchmarkSuite) -> None:
        """保存图片测评配置"""
        with self._lock:
            suite.updated_at = datetime.now()
            file_path = self.image_benchmark_suites_dir / f"{suite.id}.json"
            self._write_json_with_lock(file_path, suite.model_dump())

    def get_image_benchmark_suite(self, suite_id: str) -> Optional[ImageBenchmarkSuite]:
        """获取图片测评配置"""
        file_path = self.image_benchmark_suites_dir / f"{suite_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return ImageBenchmarkSuite(**data)
        return None

    def get_image_benchmark_suites(self, project_id: str) -> List[ImageBenchmarkSuite]:
        """获取项目下的图片测评配置"""
        suites = []
        for file_path in self.image_benchmark_suites_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                suites.append(ImageBenchmarkSuite(**data))
        return sorted(suites, key=lambda item: item.updated_at, reverse=True)

    def delete_image_benchmark_suite(self, suite_id: str) -> None:
        """删除图片测评配置"""
        file_path = self.image_benchmark_suites_dir / f"{suite_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Image Benchmark Run ============

    def save_image_benchmark_run(self, run: ImageBenchmarkRun) -> None:
        """保存图片测评运行记录"""
        with self._lock:
            run.updated_at = datetime.now()
            file_path = self.image_benchmark_runs_dir / f"{run.id}.json"
            self._write_json_with_lock(file_path, run.model_dump())

    def get_image_benchmark_run(self, run_id: str) -> Optional[ImageBenchmarkRun]:
        """获取图片测评运行记录"""
        file_path = self.image_benchmark_runs_dir / f"{run_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return ImageBenchmarkRun(**data)
        return None

    def get_image_benchmark_runs_by_suite(self, suite_id: str) -> List[ImageBenchmarkRun]:
        """获取某个测评配置下的所有运行记录"""
        runs = []
        for file_path in self.image_benchmark_runs_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("suite_id") == suite_id:
                runs.append(ImageBenchmarkRun(**data))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def get_image_benchmark_runs_by_project(self, project_id: str) -> List[ImageBenchmarkRun]:
        """获取项目下的所有图片测评运行记录"""
        runs = []
        for file_path in self.image_benchmark_runs_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                runs.append(ImageBenchmarkRun(**data))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def delete_image_benchmark_run(self, run_id: str) -> None:
        """删除图片测评运行记录"""
        file_path = self.image_benchmark_runs_dir / f"{run_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Video Benchmark Dataset ============

    def save_video_benchmark_dataset(self, dataset: VideoBenchmarkDataset) -> None:
        """保存视频测评数据集"""
        with self._lock:
            dataset.updated_at = datetime.now()
            file_path = self.video_benchmark_datasets_dir / f"{dataset.id}.json"
            self._write_json_with_lock(file_path, dataset.model_dump())

    def get_video_benchmark_dataset(self, dataset_id: str) -> Optional[VideoBenchmarkDataset]:
        """获取视频测评数据集"""
        file_path = self.video_benchmark_datasets_dir / f"{dataset_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VideoBenchmarkDataset(**data)
        return None

    def get_video_benchmark_datasets(self, project_id: str) -> List[VideoBenchmarkDataset]:
        """获取项目下的视频测评数据集"""
        datasets = []
        for file_path in self.video_benchmark_datasets_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                datasets.append(VideoBenchmarkDataset(**data))
        return sorted(datasets, key=lambda item: item.updated_at, reverse=True)

    def delete_video_benchmark_dataset(self, dataset_id: str) -> None:
        """删除视频测评数据集"""
        file_path = self.video_benchmark_datasets_dir / f"{dataset_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Video Benchmark Suite ============

    def save_video_benchmark_suite(self, suite: VideoBenchmarkSuite) -> None:
        """保存视频测评配置"""
        with self._lock:
            suite.updated_at = datetime.now()
            file_path = self.video_benchmark_suites_dir / f"{suite.id}.json"
            self._write_json_with_lock(file_path, suite.model_dump())

    def get_video_benchmark_suite(self, suite_id: str) -> Optional[VideoBenchmarkSuite]:
        """获取视频测评配置"""
        file_path = self.video_benchmark_suites_dir / f"{suite_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VideoBenchmarkSuite(**data)
        return None

    def get_video_benchmark_suites(self, project_id: str) -> List[VideoBenchmarkSuite]:
        """获取项目下的视频测评配置"""
        suites = []
        for file_path in self.video_benchmark_suites_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                suites.append(VideoBenchmarkSuite(**data))
        return sorted(suites, key=lambda item: item.updated_at, reverse=True)

    def delete_video_benchmark_suite(self, suite_id: str) -> None:
        """删除视频测评配置"""
        file_path = self.video_benchmark_suites_dir / f"{suite_id}.json"
        if file_path.exists():
            file_path.unlink()

    # ============ Video Benchmark Run ============

    def save_video_benchmark_run(self, run: VideoBenchmarkRun) -> None:
        """保存视频测评运行记录"""
        with self._lock:
            run.updated_at = datetime.now()
            file_path = self.video_benchmark_runs_dir / f"{run.id}.json"
            self._write_json_with_lock(file_path, run.model_dump())

    def get_video_benchmark_run(self, run_id: str) -> Optional[VideoBenchmarkRun]:
        """获取视频测评运行记录"""
        file_path = self.video_benchmark_runs_dir / f"{run_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return VideoBenchmarkRun(**data)
        return None

    def get_video_benchmark_runs_by_suite(self, suite_id: str) -> List[VideoBenchmarkRun]:
        """获取某个视频测评配置下的所有运行记录"""
        runs = []
        for file_path in self.video_benchmark_runs_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("suite_id") == suite_id:
                runs.append(VideoBenchmarkRun(**data))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def get_video_benchmark_runs_by_project(self, project_id: str) -> List[VideoBenchmarkRun]:
        """获取项目下的所有视频测评运行记录"""
        runs = []
        for file_path in self.video_benchmark_runs_dir.glob("*.json"):
            data = self._read_json_with_lock(file_path)
            if data and data.get("project_id") == project_id:
                runs.append(VideoBenchmarkRun(**data))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def delete_video_benchmark_run(self, run_id: str) -> None:
        """删除视频测评运行记录"""
        file_path = self.video_benchmark_runs_dir / f"{run_id}.json"
        if file_path.exists():
            file_path.unlink()


# 存储服务缓存（线程安全）
_storage_cache: dict = {}
_cache_lock = threading.Lock()
_default_storage: Optional[StorageService] = None


def get_user_storage(user_id: str) -> StorageService:
    """
    获取用户专属的存储服务（线程安全，double-checked locking）

    Args:
        user_id: 用户 ID

    Returns:
        用户专属的 StorageService 实例
    """
    if user_id not in _storage_cache:
        with _cache_lock:
            if user_id not in _storage_cache:
                from app.services.user_service import get_user_service
                user_service = get_user_service()
                user_data_path = user_service.get_user_data_path(user_id)
                _storage_cache[user_id] = StorageService(
                    str(user_data_path),
                    owner_user_id=user_id,
                )
    return _storage_cache[user_id]


def get_default_storage() -> StorageService:
    """获取默认存储服务（向后兼容，线程安全）"""
    global _default_storage
    if _default_storage is None:
        with _cache_lock:
            if _default_storage is None:
                _default_storage = StorageService()
    return _default_storage


class StorageServiceProxy:
    """
    存储服务代理
    
    自动根据当前用户上下文选择正确的存储服务：
    - 如果有当前用户，使用用户专属存储
    - 否则使用默认存储（向后兼容）
    """
    
    def _get_service(self) -> StorageService:
        """获取当前应使用的存储服务"""
        user_id = get_current_user_id()
        if user_id:
            return get_user_storage(user_id)
        return get_default_storage()
    
    def __getattr__(self, name):
        """代理所有属性访问到实际的存储服务"""
        return getattr(self._get_service(), name)


# 全局存储服务代理（自动路由到正确的用户存储）
storage_service = StorageServiceProxy()
