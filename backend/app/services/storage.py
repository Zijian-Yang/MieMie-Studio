"""
JSON 文件存储服务
"""

import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

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


class StorageService:
    """JSON 文件存储服务"""
    
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
    
    # ============ Project ============
    
    def save_project(self, project: Project) -> None:
        """保存项目"""
        project.updated_at = datetime.now()
        file_path = self.projects_dir / f"{project.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(project.model_dump(), f, ensure_ascii=False, indent=2, default=self._serialize_datetime)
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目"""
        file_path = self.projects_dir / f"{project_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Project(**data)
    
    def list_projects(self) -> List[Project]:
        """列出所有项目"""
        projects = []
        for file_path in self.projects_dir.glob("*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                projects.append(Project(**data))
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)
    
    def delete_project(self, project_id: str) -> None:
        """删除项目"""
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


# 全局存储服务实例
storage_service = StorageService()
