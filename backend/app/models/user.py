"""
用户数据模型
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class User(BaseModel):
    """用户模型"""
    id: str = ""
    username: str
    password: str  # 明文存储
    display_name: Optional[str] = None  # 显示名称
    created_at: str = ""
    last_login: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.display_name:
            self.display_name = self.username


class UserLoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class UserRegisterRequest(BaseModel):
    """注册请求"""
    username: str
    password: str
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    """用户响应（不包含密码）"""
    id: str
    username: str
    display_name: str
    created_at: str
    last_login: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    token: str
    user: UserResponse

