"""
API 路由模块
"""

from app.routers import (
    settings, scripts, characters, scenes, props, frames, videos, projects,
    styles, gallery, studio, audio, video_library, text_library, video_studio,
    audio_studio, models, auth, image_benchmark, video_benchmark
)

__all__ = [
    "settings", "scripts", "characters", "scenes", "props", "frames", 
    "videos", "projects", "styles", "gallery", "studio", "audio",
    "video_library", "text_library", "video_studio", "audio_studio",
    "models", "auth", "image_benchmark", "video_benchmark"
]
