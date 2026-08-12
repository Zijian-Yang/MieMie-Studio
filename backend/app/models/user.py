"""
用户数据模型
"""

from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime
import uuid


class User(BaseModel):
    """用户模型"""
    id: str = ""
    username: str
    password: str  # bcrypt 哈希存储
    display_name: Optional[str] = None  # 显示名称
    role: Literal["admin", "member"] = "member"
    status: Literal["active", "disabled"] = "active"
    must_change_password: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_login: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
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
    role: Literal["admin", "member"] = "member"
    status: Literal["active", "disabled"] = "active"
    must_change_password: bool = False
    created_at: str
    updated_at: str
    last_login: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    token: str
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str
