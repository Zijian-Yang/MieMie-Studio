"""
用户服务 - 处理用户注册、登录、数据隔离
"""

import json
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

from app.models.user import User, UserResponse


class UserService:
    """用户服务"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.users_file = self.data_dir / "users.json"
        self.sessions: Dict[str, str] = {}  # token -> user_id
        self._ensure_data_dir()
        self._load_sessions()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.users_file.exists():
            self._save_users({})
    
    def _load_users(self) -> Dict[str, dict]:
        """加载所有用户"""
        if self.users_file.exists():
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_users(self, users: Dict[str, dict]):
        """保存所有用户"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    
    def _load_sessions(self):
        """加载会话（从文件恢复）"""
        sessions_file = self.data_dir / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file, 'r', encoding='utf-8') as f:
                    self.sessions = json.load(f)
            except:
                self.sessions = {}
    
    def _save_sessions(self):
        """保存会话到文件"""
        sessions_file = self.data_dir / "sessions.json"
        with open(sessions_file, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)
    
    def _generate_token(self, user_id: str) -> str:
        """生成简单的会话 token"""
        raw = f"{user_id}-{datetime.now().isoformat()}-{uuid.uuid4()}"
        return hashlib.sha256(raw.encode()).hexdigest()
    
    def register(self, username: str, password: str, display_name: Optional[str] = None) -> Optional[User]:
        """
        注册新用户
        
        Returns:
            注册成功返回用户对象，用户名已存在返回 None
        """
        users = self._load_users()
        
        # 检查用户名是否已存在
        for user_data in users.values():
            if user_data.get('username') == username:
                return None
        
        # 创建新用户
        user = User(
            username=username,
            password=password,
            display_name=display_name or username
        )
        
        users[user.id] = user.model_dump()
        self._save_users(users)
        
        # 创建用户数据目录
        self._ensure_user_data_dir(user.id)
        
        return user
    
    def login(self, username: str, password: str) -> Optional[tuple[str, User]]:
        """
        用户登录
        
        Returns:
            登录成功返回 (token, user)，失败返回 None
        """
        users = self._load_users()
        
        for user_id, user_data in users.items():
            if user_data.get('username') == username and user_data.get('password') == password:
                # 更新最后登录时间
                user_data['last_login'] = datetime.now().isoformat()
                users[user_id] = user_data
                self._save_users(users)
                
                # 生成 token
                token = self._generate_token(user_id)
                self.sessions[token] = user_id
                self._save_sessions()
                
                return token, User(**user_data)
        
        return None
    
    def logout(self, token: str) -> bool:
        """用户登出"""
        if token in self.sessions:
            del self.sessions[token]
            self._save_sessions()
            return True
        return False
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """通过 token 获取用户"""
        user_id = self.sessions.get(token)
        if not user_id:
            return None
        
        users = self._load_users()
        user_data = users.get(user_id)
        if user_data:
            return User(**user_data)
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过 ID 获取用户"""
        users = self._load_users()
        user_data = users.get(user_id)
        if user_data:
            return User(**user_data)
        return None
    
    def to_response(self, user: User) -> UserResponse:
        """转换为响应对象（不包含密码）"""
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            created_at=user.created_at,
            last_login=user.last_login
        )
    
    def _ensure_user_data_dir(self, user_id: str):
        """确保用户数据目录存在"""
        user_data_dir = self.data_dir / "users" / user_id
        
        # 创建用户专属的各类数据目录
        subdirs = [
            "projects", "characters", "scenes", "props", 
            "frames", "videos", "styles", "gallery", "studio",
            "audio", "video_library", "text_library", "video_studio"
        ]
        
        for subdir in subdirs:
            (user_data_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # 创建用户配置文件（使用默认配置）
        # 注意：不在这里创建空文件，ConfigManager 会在首次访问时创建默认配置
    
    def get_user_data_path(self, user_id: str) -> Path:
        """获取用户数据目录路径"""
        return self.data_dir / "users" / user_id


# 全局单例
_user_service: Optional[UserService] = None

def get_user_service() -> UserService:
    """获取用户服务单例"""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service

