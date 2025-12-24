"""
FastAPI 依赖项 - 用户认证和数据路径
"""

from fastapi import Header, HTTPException, Request, Depends
from typing import Optional
from pathlib import Path

from app.services.user_service import get_user_service
from app.models.user import User
from app.services.storage import StorageService, get_user_storage


async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """
    获取当前登录用户（必须登录）
    
    用法:
        @router.get("/xxx")
        async def xxx(user: User = Depends(get_current_user)):
            ...
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    service = get_user_service()
    user = service.get_user_by_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    
    return user


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """
    获取当前登录用户（可选，未登录返回 None）
    """
    if not authorization:
        return None
    
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    service = get_user_service()
    return service.get_user_by_token(token)


def get_user_data_path(user: User) -> Path:
    """获取用户数据目录路径"""
    service = get_user_service()
    return service.get_user_data_path(user.id)


class UserDataPath:
    """
    用户数据路径辅助类
    
    使用方法：
        data_path = UserDataPath(user)
        projects_dir = data_path.projects
        config_file = data_path.config
    """
    
    def __init__(self, user: User):
        self.user = user
        self.base = get_user_data_path(user)
    
    @property
    def projects(self) -> Path:
        return self.base / "projects"
    
    @property
    def characters(self) -> Path:
        return self.base / "characters"
    
    @property
    def scenes(self) -> Path:
        return self.base / "scenes"
    
    @property
    def props(self) -> Path:
        return self.base / "props"
    
    @property
    def frames(self) -> Path:
        return self.base / "frames"
    
    @property
    def videos(self) -> Path:
        return self.base / "videos"
    
    @property
    def styles(self) -> Path:
        return self.base / "styles"
    
    @property
    def gallery(self) -> Path:
        return self.base / "gallery"
    
    @property
    def studio(self) -> Path:
        return self.base / "studio"
    
    @property
    def audio(self) -> Path:
        return self.base / "audio"
    
    @property
    def video_library(self) -> Path:
        return self.base / "video_library"
    
    @property
    def text_library(self) -> Path:
        return self.base / "text_library"
    
    @property
    def video_studio(self) -> Path:
        return self.base / "video_studio"
    
    @property
    def config(self) -> Path:
        return self.base / "config.json"


async def get_storage(user: User = Depends(get_current_user)) -> StorageService:
    """
    获取当前用户的存储服务
    
    用法:
        @router.get("/xxx")
        async def xxx(storage: StorageService = Depends(get_storage)):
            projects = storage.list_projects()
    """
    return get_user_storage(user.id)

