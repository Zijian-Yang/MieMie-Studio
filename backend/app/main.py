"""
AI 视频生成平台 - FastAPI 后端入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routers import (
    settings, scripts, characters, scenes, props, frames, videos, projects, 
    styles, gallery, studio, audio, video_library, text_library, video_studio,
    models
)

# 创建 FastAPI 应用
app = FastAPI(
    title="AI 视频生成平台",
    description="基于通义万相的 AI 视频生成操作平台",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务 - 用于提供生成的素材
data_dir = Path(__file__).parent.parent / "data"
assets_dir = data_dir / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# 注册路由
app.include_router(settings.router, prefix="/api/settings", tags=["设置"])
app.include_router(projects.router, prefix="/api/projects", tags=["项目"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["分镜脚本"])
app.include_router(characters.router, prefix="/api/characters", tags=["角色"])
app.include_router(scenes.router, prefix="/api/scenes", tags=["场景"])
app.include_router(props.router, prefix="/api/props", tags=["道具"])
app.include_router(frames.router, prefix="/api/frames", tags=["分镜首帧"])
app.include_router(videos.router, prefix="/api/videos", tags=["视频"])
app.include_router(styles.router, prefix="/api/styles", tags=["风格"])
app.include_router(gallery.router, prefix="/api/gallery", tags=["图库"])
app.include_router(studio.router, prefix="/api/studio", tags=["图片工作室"])
app.include_router(audio.router, prefix="/api/audio", tags=["音频库"])
app.include_router(video_library.router, prefix="/api/video-library", tags=["视频库"])
app.include_router(text_library.router, prefix="/api/text-library", tags=["文本库"])
app.include_router(video_studio.router, prefix="/api/video-studio", tags=["视频工作室"])
app.include_router(models.router, prefix="/api/models", tags=["模型配置"])


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "message": "AI 视频生成平台 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
