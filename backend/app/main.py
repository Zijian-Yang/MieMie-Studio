"""
AI 视频生成平台 - FastAPI 后端入口
"""

import os
import subprocess
import logging
from time import perf_counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# 初始化日志系统（必须在导入其他模块之前）
from app.logger import init_logging
init_logging()

from app.routers import (
    settings, scripts, characters, scenes, props, frames, videos, projects, 
    styles, gallery, studio, audio, video_library, text_library, video_studio,
    audio_studio, models, auth, image_benchmark, video_benchmark,
    admin_users, admin_platform,
)
from app.middleware.auth import AuthMiddleware
from app.db.engine import database_health
from app.services.rate_limit import create_limiter, redis_url_from_env
from app.services.runtime_observability import build_request_observation, should_observe_request

from slowapi import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = create_limiter(key_func=get_remote_address, default_limits=["200/minute"])
runtime_observability_logger = logging.getLogger("app.runtime_observability")

# 生产模式标志（提前定义，供 CORS 和静态文件使用）
SERVE_FRONTEND = os.environ.get("MIEMIE_SERVE_FRONTEND", "").lower() in ("true", "1", "yes")
APP_STARTED_AT = os.environ.get("MIEMIE_RUNTIME_STARTED_AT") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_runtime_git_commit() -> str:
    env_value = os.environ.get("MIEMIE_RUNTIME_GIT_COMMIT")
    if env_value:
        return env_value

    repo_root = Path(__file__).resolve().parent.parent.parent
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


RUNTIME_GIT_COMMIT = _resolve_runtime_git_commit()
RUNTIME_RUN_MODE = os.environ.get("MIEMIE_RUNTIME_RUN_MODE") or ("prod" if SERVE_FRONTEND else "dev")


def _redis_health() -> dict:
    url = redis_url_from_env()
    if not url:
        return {"configured": False, "ok": None}
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.ping()
        return {"configured": True, "ok": True}
    except Exception as exc:
        return {"configured": True, "ok": False, "error": exc.__class__.__name__}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：恢复需要继续推进的后台任务。"""
    await video_studio.start_pending_video_task_reconcilers()
    yield


# 创建 FastAPI 应用
app = FastAPI(
    title="AI 视频生成平台",
    description="基于通义万相的 AI 视频生成操作平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS（必须在 AuthMiddleware 之前）
# 通过环境变量 MIEMIE_CORS_ORIGINS 配置允许的源（逗号分隔）
# 默认开发模式允许前端端口（可通过 MIEMIE_FRONTEND_PORT 自定义）
_cors_origins_env = os.environ.get("MIEMIE_CORS_ORIGINS", "")
if _cors_origins_env:
    _cors_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
elif SERVE_FRONTEND:
    # 生产模式：同源访问，不需要指定特定域名
    _cors_origins = ["*"]
else:
    # 开发模式：允许自定义前端端口
    _frontend_port = os.environ.get("MIEMIE_FRONTEND_PORT", "3000")
    _cors_origins = [
        f"http://localhost:{_frontend_port}",
        "http://localhost:5173",  # Vite 默认端口
    ]
    # 如果自定义端口不是 3000，也保留 3000 的兼容
    if _frontend_port != "3000":
        _cors_origins.append("http://localhost:3000")

# allow_credentials 与 allow_origins=["*"] 不兼容（浏览器会拒绝）
_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Deployment-Version"],
)

# 添加认证中间件
app.add_middleware(AuthMiddleware)


@app.middleware("http")
async def log_runtime_observation(request: Request, call_next):
    path = request.url.path
    should_observe = should_observe_request(request.method, path)
    started = perf_counter()
    response = await call_next(request)

    if should_observe:
        observation = build_request_observation(
            method=request.method,
            path=path,
            query_params=dict(request.query_params),
            status_code=response.status_code,
            duration_ms=(perf_counter() - started) * 1000,
            user_id=getattr(request.state, "user_id", None),
            request_id=getattr(request.state, "request_id", None),
        )
        runtime_observability_logger.info("[runtime_observation] %s", observation)

    return response

# 静态文件服务 - 用于提供生成的素材
data_dir = Path(__file__).parent.parent / "data"
assets_dir = data_dir / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(auth.public_router, tags=["引导状态"])
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
app.include_router(audio_studio.router, prefix="/api/audio-studio", tags=["音频工作室"])
app.include_router(image_benchmark.router, prefix="/api/image-benchmark", tags=["图片测评"])
app.include_router(video_benchmark.router, prefix="/api/video-benchmark", tags=["视频测评"])
app.include_router(models.router, prefix="/api/models", tags=["模型配置"])
app.include_router(admin_users.router, prefix="/api/admin", tags=["平台用户管理"])
app.include_router(admin_platform.router, prefix="/api/admin", tags=["平台管理"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "git_commit": RUNTIME_GIT_COMMIT,
        "run_mode": RUNTIME_RUN_MODE,
        "serve_frontend": SERVE_FRONTEND,
        "started_at": APP_STARTED_AT,
        "redis": _redis_health(),
        "database": database_health(),
    }


# ──────────────────────────────────────
# 生产模式：由 FastAPI 服务前端静态文件
# ──────────────────────────────────────
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
