"""
API 路由模块
"""

from app.routers import (
    settings, scripts, characters, scenes, props, frames, videos, projects,
    styles, gallery, studio, audio, video_library, text_library, video_studio,
    models, auth
)

__all__ = [
    "settings", "scripts", "characters", "scenes", "props", "frames", 
    "videos", "projects", "styles", "gallery", "studio", "audio",
    "video_library", "text_library", "video_studio", "models", "auth"
]
