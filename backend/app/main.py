"""
AI 视频生成平台 - FastAPI 后端入口
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path

# 初始化日志系统（必须在导入其他模块之前）
from app.logger import init_logging
init_logging()

from app.routers import (
    settings, scripts, characters, scenes, props, frames, videos, projects, 
    styles, gallery, studio, audio, video_library, text_library, video_studio,
    models, auth
)
from app.middleware.auth import AuthMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# 创建 FastAPI 应用
app = FastAPI(
    title="AI 视频生成平台",
    description="基于通义万相的 AI 视频生成操作平台",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS（必须在 AuthMiddleware 之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件
app.add_middleware(AuthMiddleware)

# 静态文件服务 - 用于提供生成的素材
data_dir = Path(__file__).parent.parent / "data"
assets_dir = data_dir / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
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


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


# ──────────────────────────────────────
# 生产模式：由 FastAPI 服务前端静态文件
# ──────────────────────────────────────
SERVE_FRONTEND = os.environ.get("MIEMIE_SERVE_FRONTEND", "").lower() in ("true", "1", "yes")
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if SERVE_FRONTEND and FRONTEND_DIST.exists():
    _static_dir = FRONTEND_DIST / "_static"
    if _static_dir.exists():
        app.mount("/_static", StaticFiles(directory=str(_static_dir)), name="frontend_static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 回退：非 API 路径全部返回 index.html"""
        if full_path:
            file_path = FRONTEND_DIST / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/")
    async def root():
        """API 根路径（开发模式）"""
        return {
            "message": "AI 视频生成平台 API",
            "version": "1.0.0",
            "docs": "/docs"
        }
