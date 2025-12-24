"""
认证中间件 - 处理用户认证和数据路径重定向

确保用户数据完全隔离：
- 存储（projects, characters, etc.）
- 配置（API Key, OSS, 模型参数等）
- 日志上下文（显示用户名）
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Optional

from app.services.user_service import get_user_service
from app.services.storage import set_current_user
from app.config import set_user_config_dir
from app.logger import set_log_user_context


logger = logging.getLogger(__name__)

# 不需要认证的路径
PUBLIC_PATHS = [
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/assets",  # 静态资源
]


def is_public_path(path: str) -> bool:
    """检查路径是否公开（不需要认证）"""
    for public_path in PUBLIC_PATHS:
        if path == public_path or path.startswith(public_path + "/"):
            return True
    return False


def clear_user_context():
    """清除当前用户上下文"""
    set_current_user(None)
    set_user_config_dir(None)
    set_log_user_context(None)


def set_user_context(user_id: str, username: str, user_data_path: str):
    """设置当前用户上下文"""
    set_current_user(user_id)
    set_user_config_dir(str(user_data_path))
    set_log_user_context(username)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件
    
    功能：
    1. 验证 Authorization header 中的 token
    2. 将用户信息注入到 request.state 中
    3. 设置当前用户上下文（存储和配置都使用用户专属目录）
    4. 公开路径跳过认证
    5. 确保请求结束后清除上下文（支持并发）
    """
    
    async def dispatch(self, request: Request, call_next):
        # 公开路径直接通过（不设置用户上下文）
        if is_public_path(request.url.path):
            clear_user_context()
            return await call_next(request)
        
        # 获取 Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            clear_user_context()
            return JSONResponse(
                status_code=401,
                content={"detail": "未登录"}
            )
        
        # 解析 token
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header
        
        # 验证 token
        service = get_user_service()
        user = service.get_user_by_token(token)
        
        if not user:
            clear_user_context()
            return JSONResponse(
                status_code=401,
                content={"detail": "登录已过期，请重新登录"}
            )
        
        # 获取用户数据路径
        user_data_path = service.get_user_data_path(user.id)
        
        # 设置当前用户上下文（让 storage_service 和 config_manager 自动使用正确的用户目录）
        set_user_context(user.id, user.username, user_data_path)
        
        # 将用户信息注入到 request.state
        request.state.user = user
        request.state.user_id = user.id
        request.state.user_data_path = user_data_path
        
        # 添加用户上下文到日志
        logger.debug(f"[User: {user.username}] Processing request: {request.method} {request.url.path}")
        
        # 继续处理请求
        try:
            response = await call_next(request)
            return response
        finally:
            # 请求结束后清除用户上下文（非常重要！）
            clear_user_context()

