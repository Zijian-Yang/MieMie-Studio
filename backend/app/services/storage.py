"""
JSON 文件存储服务

支持多用户数据隔离和并发安全：
- 通过 set_current_user() 设置当前用户
- storage_service 会自动使用当前用户的数据目录
- 使用文件锁确保并发安全
- 如果未设置用户，使用全局默认目录（向后兼容）
"""

import json
import fcntl
import threading
from pathlib import Path
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
from app.models.studio import StudioTask
from app.models.media import AudioItem, VideoItem, TextItem, VideoStudioTask

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
    
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
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
        
        self._lock = threading.RLock()  # 可重入锁，支持并发访问
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保所有目录存在"""
        for dir_path in [
            self.projects_dir, self.characters_dir, self.scenes_dir,
            self.props_dir, self.frames_dir, self.videos_dir, self.styles_dir,
            self.gallery_dir, self.studio_dir,
            self.audio_dir, self.video_library_dir, self.text_library_dir, self.video_studio_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _serialize_datetime(self, obj):
        """序列化 datetime 对象"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
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
        """带文件锁的 JSON 写入"""
        with open(file_path, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            try:
                json.dump(data, f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    # ============ Project ============
    
    def save_project(self, project: Project) -> None:
        """保存项目（线程安全）"""
        with self._lock:
            project.updated_at = datetime.now()
            file_path = self.projects_dir / f"{project.id}.json"
            self._write_json_with_lock(file_path, project.model_dump())
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目（线程安全）"""
        file_path = self.projects_dir / f"{project_id}.json"
        data = self._read_json_with_lock(file_path)
        if data:
            return Project(**data)
        return None
    
    def list_projects(self) -> List[Project]:
        """列出所有项目（线程安全）"""
        projects = []
        with self._lock:
            for file_path in self.projects_dir.glob("*.json"):
                data = self._read_json_with_lock(file_path)
                if data:
                    try:
                        projects.append(Project(**data))
                    except Exception:
                        pass  # 跳过格式错误的文件
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)
    
    def delete_project(self, project_id: str) -> None:
        """删除项目（线程安全）"""
        with self._lock:
            file_path = self.projects_dir / f"{project_id}.json"
            if file_path.exists():
                file_path.unlink()
    
    # ============ Character ============
    
    def save_character(self, character: Character) -> None:
        """保存角色"""
        character.updated_at = datetime.now()
        file_path = self.characters_dir / f"{character.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(character.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """获取角色"""
        file_path = self.characters_dir / f"{character_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Character(**data)
    
    def delete_character(self, character_id: str) -> None:
        """删除角色"""
        file_path = self.characters_dir / f"{character_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Scene ============
    
    def save_scene(self, scene: Scene) -> None:
        """保存场景"""
        scene.updated_at = datetime.now()
        file_path = self.scenes_dir / f"{scene.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(scene.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取场景"""
        file_path = self.scenes_dir / f"{scene_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Scene(**data)
    
    def delete_scene(self, scene_id: str) -> None:
        """删除场景"""
        file_path = self.scenes_dir / f"{scene_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Prop ============
    
    def save_prop(self, prop: Prop) -> None:
        """保存道具"""
        prop.updated_at = datetime.now()
        file_path = self.props_dir / f"{prop.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(prop.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_prop(self, prop_id: str) -> Optional[Prop]:
        """获取道具"""
        file_path = self.props_dir / f"{prop_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Prop(**data)
    
    def delete_prop(self, prop_id: str) -> None:
        """删除道具"""
        file_path = self.props_dir / f"{prop_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Frame ============
    
    def save_frame(self, frame: Frame) -> None:
        """保存首帧"""
        frame.updated_at = datetime.now()
        file_path = self.frames_dir / f"{frame.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(frame.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_frame(self, frame_id: str) -> Optional[Frame]:
        """获取首帧"""
        file_path = self.frames_dir / f"{frame_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Frame(**data)
    
    def get_frame_by_shot(self, project_id: str, shot_id: str) -> Optional[Frame]:
        """根据分镜ID获取首帧"""
        for file_path in self.frames_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id and data.get("shot_id") == shot_id:
                    return Frame(**data)
        return None
    
    def get_frames_by_project(self, project_id: str) -> List[Frame]:
        """获取项目所有首帧"""
        frames = []
        for file_path in self.frames_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    frames.append(Frame(**data))
        return sorted(frames, key=lambda f: f.shot_number)
    
    def delete_frame(self, frame_id: str) -> None:
        """删除首帧"""
        file_path = self.frames_dir / f"{frame_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video ============
    
    def save_video(self, video: Video) -> None:
        """保存视频"""
        video.updated_at = datetime.now()
        file_path = self.videos_dir / f"{video.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(video.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_video(self, video_id: str) -> Optional[Video]:
        """获取视频"""
        file_path = self.videos_dir / f"{video_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Video(**data)
    
    def get_video_by_task(self, task_id: str) -> Optional[Video]:
        """根据任务ID获取视频"""
        for file_path in self.videos_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                task = data.get("task")
                if task and task.get("task_id") == task_id:
                    return Video(**data)
        return None
    
    def get_videos_by_project(self, project_id: str) -> List[Video]:
        """获取项目所有视频"""
        videos = []
        for file_path in self.videos_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    videos.append(Video(**data))
        return sorted(videos, key=lambda v: v.shot_number)
    
    def get_video_by_shot(self, project_id: str, shot_id: str) -> Optional[Video]:
        """根据分镜ID获取视频"""
        for file_path in self.videos_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id and data.get("shot_id") == shot_id:
                    return Video(**data)
        return None
    
    def delete_video(self, video_id: str) -> None:
        """删除视频"""
        file_path = self.videos_dir / f"{video_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Style ============
    
    def save_style(self, style: Style) -> None:
        """保存风格"""
        style.updated_at = datetime.now()
        file_path = self.styles_dir / f"{style.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(style.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_style(self, style_id: str) -> Optional[Style]:
        """获取风格"""
        file_path = self.styles_dir / f"{style_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Style(**data)
    
    def delete_style(self, style_id: str) -> None:
        """删除风格"""
        file_path = self.styles_dir / f"{style_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Gallery ============
    
    def save_gallery_image(self, image: GalleryImage) -> None:
        """保存图库图片"""
        image.updated_at = datetime.now()
        file_path = self.gallery_dir / f"{image.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(image.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_gallery_image(self, image_id: str) -> Optional[GalleryImage]:
        """获取图库图片"""
        file_path = self.gallery_dir / f"{image_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return GalleryImage(**data)
    
    def get_gallery_images_by_project(self, project_id: str) -> List[GalleryImage]:
        """获取项目所有图库图片"""
        images = []
        for file_path in self.gallery_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    images.append(GalleryImage(**data))
        return sorted(images, key=lambda i: i.created_at, reverse=True)
    
    def delete_gallery_image(self, image_id: str) -> None:
        """删除图库图片"""
        file_path = self.gallery_dir / f"{image_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Studio Task ============
    
    def save_studio_task(self, task: StudioTask) -> None:
        """保存图片工作室任务"""
        task.updated_at = datetime.now()
        file_path = self.studio_dir / f"{task.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(task.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_studio_task(self, task_id: str) -> Optional[StudioTask]:
        """获取图片工作室任务"""
        file_path = self.studio_dir / f"{task_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return StudioTask(**data)
    
    def get_studio_tasks_by_project(self, project_id: str) -> List[StudioTask]:
        """获取项目所有图片工作室任务"""
        tasks = []
        for file_path in self.studio_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    tasks.append(StudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def delete_studio_task(self, task_id: str) -> None:
        """删除图片工作室任务"""
        file_path = self.studio_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Audio Library ============
    
    def save_audio_item(self, audio: AudioItem) -> None:
        """保存音频项"""
        audio.updated_at = datetime.now()
        file_path = self.audio_dir / f"{audio.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(audio.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_audio_item(self, audio_id: str) -> Optional[AudioItem]:
        """获取音频项"""
        file_path = self.audio_dir / f"{audio_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return AudioItem(**data)
    
    def get_audio_items(self, project_id: str) -> List[AudioItem]:
        """获取项目所有音频"""
        audios = []
        for file_path in self.audio_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    audios.append(AudioItem(**data))
        return sorted(audios, key=lambda a: a.created_at, reverse=True)
    
    def delete_audio_item(self, audio_id: str) -> None:
        """删除音频项"""
        file_path = self.audio_dir / f"{audio_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video Library ============
    
    def save_video_item(self, video: VideoItem) -> None:
        """保存视频项"""
        video.updated_at = datetime.now()
        file_path = self.video_library_dir / f"{video.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(video.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_video_item(self, video_id: str) -> Optional[VideoItem]:
        """获取视频项"""
        file_path = self.video_library_dir / f"{video_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return VideoItem(**data)
    
    def get_video_items(self, project_id: str) -> List[VideoItem]:
        """获取项目所有视频"""
        videos = []
        for file_path in self.video_library_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    videos.append(VideoItem(**data))
        return sorted(videos, key=lambda v: v.created_at, reverse=True)
    
    def delete_video_item(self, video_id: str) -> None:
        """删除视频项"""
        file_path = self.video_library_dir / f"{video_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Text Library ============
    
    def save_text_item(self, text: TextItem) -> None:
        """保存文本项"""
        text.updated_at = datetime.now()
        file_path = self.text_library_dir / f"{text.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(text.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_text_item(self, text_id: str) -> Optional[TextItem]:
        """获取文本项"""
        file_path = self.text_library_dir / f"{text_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return TextItem(**data)
    
    def get_text_items(self, project_id: str) -> List[TextItem]:
        """获取项目所有文本"""
        texts = []
        for file_path in self.text_library_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    texts.append(TextItem(**data))
        return sorted(texts, key=lambda t: t.created_at, reverse=True)
    
    def delete_text_item(self, text_id: str) -> None:
        """删除文本项"""
        file_path = self.text_library_dir / f"{text_id}.json"
        if file_path.exists():
            file_path.unlink()
    
    # ============ Video Studio ============
    
    def save_video_studio_task(self, task: VideoStudioTask) -> None:
        """保存视频工作室任务"""
        task.updated_at = datetime.now()
        file_path = self.video_studio_dir / f"{task.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(task.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_video_studio_task(self, task_id: str) -> Optional[VideoStudioTask]:
        """获取视频工作室任务"""
        file_path = self.video_studio_dir / f"{task_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return VideoStudioTask(**data)
    
    def get_video_studio_tasks(self, project_id: str) -> List[VideoStudioTask]:
        """获取项目所有视频工作室任务"""
        tasks = []
        for file_path in self.video_studio_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("project_id") == project_id:
                    tasks.append(VideoStudioTask(**data))
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def delete_video_studio_task(self, task_id: str) -> None:
        """删除视频工作室任务"""
        file_path = self.video_studio_dir / f"{task_id}.json"
        if file_path.exists():
            file_path.unlink()


# 存储服务缓存
_storage_cache: dict = {}
_default_storage: Optional[StorageService] = None


def get_user_storage(user_id: str) -> StorageService:
    """
    获取用户专属的存储服务
    
    Args:
        user_id: 用户 ID
        
    Returns:
        用户专属的 StorageService 实例
    """
    if user_id not in _storage_cache:
        from app.services.user_service import get_user_service
        user_service = get_user_service()
        user_data_path = user_service.get_user_data_path(user_id)
        _storage_cache[user_id] = StorageService(str(user_data_path))
    return _storage_cache[user_id]


def get_default_storage() -> StorageService:
    """获取默认存储服务（向后兼容）"""
    global _default_storage
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
