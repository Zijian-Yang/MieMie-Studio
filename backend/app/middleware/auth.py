"""
认证中间件 - 纯 ASGI 实现，确保 contextvars 在并发下正确隔离

确保用户数据完全隔离：
- 存储（projects, characters, etc.）
- 配置（API Key, OSS, 模型参数等）
- 日志上下文（显示用户名）
"""

import json
import logging
import os
import subprocess
from uuid import uuid4
from pathlib import Path
from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.user_service import get_user_service
from app.services.storage import set_current_user
from app.config import set_user_config_dir
from app.logger import set_log_request_context, set_log_user_context


logger = logging.getLogger(__name__)

# 不需要认证的路径前缀
PUBLIC_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/bootstrap/status",
    "/api/image-benchmark/public",
    "/assets",      # 后端静态资源
    "/_static",     # 前端构建产物
]

SERVE_FRONTEND = os.environ.get("MIEMIE_SERVE_FRONTEND", "").lower() in ("true", "1", "yes")


def _resolve_deployment_version() -> str:
    env_value = os.environ.get("MIEMIE_RUNTIME_GIT_COMMIT")
    if env_value:
        return env_value

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


DEPLOYMENT_VERSION = _resolve_deployment_version()


def is_public_path(path: str) -> bool:
    """检查路径是否公开（不需要认证）"""
    if path == "/":
        return True
    # 生产模式下，所有非 /api 路径都是前端静态资源或 SPA 路由
    if SERVE_FRONTEND and not path.startswith("/api"):
        return True
    for public_path in PUBLIC_PATHS:
        if path == public_path or path.startswith(public_path + "/"):
            return True
    return False


def clear_user_context():
    """清除当前用户上下文"""
    set_current_user(None)
    set_user_config_dir(None)
    set_log_user_context(None)


def clear_request_context():
    """清除当前请求上下文"""
    set_log_request_context(None)


def set_user_context(user_id: str, username: str, user_data_path: str):
    """设置当前用户上下文"""
    set_current_user(user_id)
    set_user_config_dir(str(user_data_path))
    set_log_user_context(username)


class AuthMiddleware:
    """
    纯 ASGI 认证中间件

    使用纯 ASGI 协议而非 BaseHTTPMiddleware，避免 Starlette 的
    anyio task group 导致 contextvars 在并发请求间泄漏的问题。

    功能：
    1. 验证 Authorization header 中的 token
    2. 将用户信息注入到 request scope.state 中
    3. 设置当前用户上下文（存储和配置都使用用户专属目录）
    4. 公开路径跳过认证
    5. 确保请求结束后清除上下文（支持并发）
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        headers = dict(
            (k.decode("latin-1"), v.decode("latin-1"))
            for k, v in scope.get("headers", [])
        )
        request_id = headers.get("x-request-id", "").strip() or uuid4().hex[:12]
        set_log_request_context(request_id)

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id
        scope["state"]["deployment_version"] = DEPLOYMENT_VERSION

        async def send_with_context(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                lower_header_names = {key.lower() for key, _ in response_headers}
                if b"x-request-id" not in lower_header_names:
                    response_headers.append([b"x-request-id", request_id.encode("latin-1")])
                if DEPLOYMENT_VERSION and b"x-deployment-version" not in lower_header_names:
                    response_headers.append([b"x-deployment-version", DEPLOYMENT_VERSION.encode("latin-1")])
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            # 公开路径直接通过
            if is_public_path(path):
                clear_user_context()
                await self.app(scope, receive, send_with_context)
                return

            auth_header = headers.get("authorization", "")
            if not auth_header:
                clear_user_context()
                await self._send_json_response(send_with_context, 401, {"detail": "未登录"})
                return

            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header

            service = get_user_service()
            user = service.get_user_by_token(token)

            if not user:
                clear_user_context()
                await self._send_json_response(send_with_context, 401, {"detail": "登录已过期，请重新登录"})
                return

            user_data_path = service.get_user_data_path(user.id)
            set_user_context(user.id, user.username, user_data_path)

            scope["state"]["user"] = user
            scope["state"]["user_id"] = user.id
            scope["state"]["user_data_path"] = user_data_path

            logger.debug(f"[User: {user.username}] Processing request: {scope.get('method', '')} {path}")
            await self.app(scope, receive, send_with_context)
        finally:
            clear_user_context()
            clear_request_context()

    @staticmethod
    async def _send_json_response(send: Send, status_code: int, body: dict):
        """发送 JSON 错误响应"""
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body_bytes)).encode("latin-1")],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body_bytes,
        })
