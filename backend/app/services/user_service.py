"""
用户服务 - 处理用户注册、登录、数据隔离
"""

import json
import os
import uuid
import hashlib
import logging
import threading
import fcntl
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone

import bcrypt

from app.models.user import User, UserResponse
from app.repositories import session_runtime
from app.services.session_store import RedisSessionStore, SessionRecord

logger = logging.getLogger(__name__)

# Token 有效期（天）
TOKEN_EXPIRE_DAYS = 7
TOKEN_EXPIRE_SECONDS = TOKEN_EXPIRE_DAYS * 24 * 60 * 60


class UserService:
    """用户服务"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir is not None else Path(__file__).parent.parent.parent / "data"
        self.users_file = self.data_dir / "users.json"
        self.sessions: Dict[str, str] = {}  # token -> user_id
        self._lock = threading.RLock()
        self._redis_sessions = RedisSessionStore.from_env(ttl_seconds=TOKEN_EXPIRE_SECONDS)
        self._ensure_data_dir()
        self._load_sessions()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.users_file.exists() and self._users_file_required():
            self._save_users({})

    def _users_file_required(self) -> bool:
        from app.repositories.user_config_runtime import (
            json_archive_writes_enabled,
            user_config_primary_write_enabled,
        )

        return not user_config_primary_write_enabled() or json_archive_writes_enabled()
    
    def _load_users(self) -> Dict[str, dict]:
        """加载所有用户"""
        return self._read_json_with_lock(self.users_file)
    
    def _save_users(self, users: Dict[str, dict]):
        """保存所有用户（原子写入）"""
        self._write_json_with_lock(self.users_file, users)

    def _shadow_save_user(self, user: User):
        from app.repositories.user_config_runtime import shadow_save_user

        shadow_save_user(user)

    def _save_user_record(self, users: Dict[str, dict], user: User):
        from app.repositories.user_config_runtime import (
            json_archive_writes_enabled,
            save_user_primary,
        )

        if save_user_primary(user):
            if json_archive_writes_enabled():
                users[user.id] = user.model_dump()
                self._save_users(users)
            return

        users[user.id] = user.model_dump()
        self._save_users(users)
        self._shadow_save_user(user)

    def _load_user_from_json(self, user_id: str) -> Optional[User]:
        users = self._load_users()
        user_data = users.get(user_id)
        return User(**user_data) if user_data else None

    def _read_user(self, user_id: str) -> Optional[User]:
        from app.repositories.user_config_runtime import read_user

        return read_user(user_id, lambda: self._load_user_from_json(user_id))

    def _load_user_by_username_from_json(self, username: str) -> Optional[User]:
        users = self._load_users()
        for user_data in users.values():
            if user_data.get('username') == username:
                return User(**user_data)
        return None

    def _read_user_by_username(self, username: str) -> Optional[User]:
        from app.repositories.user_config_runtime import read_user_by_username

        return read_user_by_username(username, lambda: self._load_user_by_username_from_json(username))

    def _lock_file_path(self, file_path: Path) -> Path:
        return file_path.with_suffix(file_path.suffix + '.lock')

    def _read_json_with_lock(self, file_path: Path) -> Dict[str, dict]:
        if not file_path.exists():
            return {}

        lock_path = self._lock_file_path(file_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch(exist_ok=True)

        with open(lock_path, 'a+', encoding='utf-8') as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_SH)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def _write_json_with_lock(self, file_path: Path, data: Dict[str, dict]):
        lock_path = self._lock_file_path(file_path)
        tmp_path = file_path.with_suffix('.tmp')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch(exist_ok=True)

        with open(lock_path, 'a+', encoding='utf-8') as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(str(tmp_path), str(file_path))
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
    
    def _load_sessions(self):
        """加载会话（从文件恢复），自动兼容旧格式并清理过期 token"""
        sessions_file = self.data_dir / "sessions.json"
        if not sessions_file.exists():
            self.sessions = {}
            return

        try:
            raw = self._read_json_with_lock(sessions_file)
            migrated = False
            for token, val in list(raw.items()):
                if isinstance(val, str):
                    raw[token] = {
                        "user_id": val,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    migrated = True
            self.sessions = raw
            if migrated:
                self._save_sessions()
            self._cleanup_expired_sessions()
        except Exception as e:
            logger.warning(f"会话文件加载失败，已重置会话: {e}")
            self.sessions = {}
    
    def _save_sessions(self):
        """保存会话到文件（原子写入）"""
        sessions_file = self.data_dir / "sessions.json"
        self._write_json_with_lock(sessions_file, self.sessions)

    def _save_session(self, token: str, session: Dict[str, str]):
        """保存单个 session：Redis 优先用于多 worker，文件保留兜底。"""
        record = SessionRecord.from_raw(session)
        if session_runtime.save_session_primary(token, record):
            self.sessions[token] = session
            if self._redis_sessions:
                try:
                    if record:
                        self._redis_sessions.set(token, record)
                except Exception as exc:
                    logger.warning("[会话] Redis session 写入失败，PostgreSQL 主写已保留: %s", exc)
            if session_runtime.json_archive_writes_enabled():
                self._save_sessions()
            return

        self.sessions[token] = session
        if self._redis_sessions:
            try:
                if record:
                    self._redis_sessions.set(token, record)
            except Exception as exc:
                logger.warning("[会话] Redis session 写入失败，保留文件兜底: %s", exc)
        self._save_sessions()
        session_runtime.shadow_save_session(token, record)

    def _delete_session(self, token: str):
        primary_deleted = session_runtime.delete_session_primary(token)
        session = self.sessions.pop(token, None)
        if self._redis_sessions:
            try:
                self._redis_sessions.delete(token)
            except Exception as exc:
                logger.warning("[会话] Redis session 删除失败: %s", exc)
        if session is not None and (not primary_deleted or session_runtime.json_archive_writes_enabled()):
            self._save_sessions()
        if not primary_deleted:
            session_runtime.shadow_delete_session(token)

    def _delete_user_sessions(self, user_id: str):
        primary_deleted = session_runtime.delete_user_sessions_primary(user_id)
        tokens = []
        for token, session in self.sessions.items():
            record = SessionRecord.from_raw(session)
            if record and record.user_id == user_id:
                tokens.append(token)
        for token in tokens:
            self.sessions.pop(token, None)
        if tokens and (not primary_deleted or session_runtime.json_archive_writes_enabled()):
            self._save_sessions()
        if self._redis_sessions:
            try:
                self._redis_sessions.delete_user_sessions(user_id)
            except Exception as exc:
                logger.warning("[会话] Redis 用户 session 清理失败: %s", exc)
        if not primary_deleted:
            session_runtime.shadow_delete_user_sessions(user_id)
    
    def _cleanup_expired_sessions(self):
        """清理过期的会话"""
        expired = []
        for token, session in self.sessions.items():
            if self._session_is_expired(session.get("created_at", "")):
                expired.append(token)
        if expired:
            for token in expired:
                del self.sessions[token]
            self._save_sessions()
            logger.info(f"已清理 {len(expired)} 个过期会话")

    @staticmethod
    def _session_is_expired(created_value: object) -> bool:
        try:
            created_at = datetime.fromisoformat(str(created_value))
        except (ValueError, TypeError):
            return True

        if created_at.tzinfo is None:
            return datetime.now() - created_at > timedelta(days=TOKEN_EXPIRE_DAYS)
        return datetime.now(timezone.utc) - created_at.astimezone(timezone.utc) > timedelta(
            days=TOKEN_EXPIRE_DAYS
        )
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """使用 bcrypt 哈希密码"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        """验证密码（支持 bcrypt 哈希和明文密码的渐进式迁移）"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except (ValueError, TypeError):
            # 明文密码兼容：旧数据未哈希时直接比较
            return password == hashed

    @staticmethod
    def _is_hashed(password: str) -> bool:
        """判断密码是否已经 bcrypt 哈希"""
        return password.startswith('$2b$') or password.startswith('$2a$')

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
        with self._lock:
            users = self._load_users()
            
            # 检查用户名是否已存在
            if self._read_user_by_username(username):
                return None
            
            # 创建新用户（密码 bcrypt 哈希）
            user = User(
                username=username,
                password=self._hash_password(password),
                display_name=display_name or username
            )
            
            self._save_user_record(users, user)
            
            # 创建用户数据目录
            self._ensure_user_data_dir(user.id)
            
            return user
    
    def login(self, username: str, password: str) -> Optional[tuple[str, User]]:
        """
        用户登录
        
        Returns:
            登录成功返回 (token, user)，失败返回 None
        """
        with self._lock:
            users = self._load_users()
            user = self._read_user_by_username(username)
            if user and self._verify_password(password, user.password):
                # 渐进式迁移：明文密码自动升级为 bcrypt 哈希
                if not self._is_hashed(user.password):
                    user.password = self._hash_password(password)
                    logger.info(f"用户 {username} 密码已自动迁移为 bcrypt 哈希")

                # 更新最后登录时间
                now = datetime.now().isoformat()
                user.last_login = now
                user.updated_at = now
                self._save_user_record(users, user)

                # 生成 token（带过期时间）
                token = self._generate_token(user.id)
                self._save_session(token, {
                    "user_id": user.id,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

                return token, user
            
            return None
    
    def logout(self, token: str) -> bool:
        """用户登出"""
        with self._lock:
            if session_runtime.session_primary_write_enabled():
                session = session_runtime.read_session(token, lambda: self.sessions.get(token))
                if session:
                    self._delete_session(token)
                    return True
            if token in self.sessions:
                self._delete_session(token)
                return True
            if self._redis_sessions:
                try:
                    if self._redis_sessions.get(token):
                        self._redis_sessions.delete(token)
                        session_runtime.shadow_delete_session(token)
                        return True
                except Exception as exc:
                    logger.warning("[会话] Redis logout 查询失败: %s", exc)
            return False
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """通过 token 获取用户（支持多 worker：每次从文件读取，含过期检查）"""
        with self._lock:
            self._load_sessions()

            def load_current_session():
                session = None
                if self._redis_sessions:
                    try:
                        redis_record = self._redis_sessions.get(token)
                        if redis_record:
                            session = redis_record.to_dict()
                    except Exception as exc:
                        logger.warning("[会话] Redis session 读取失败，回退文件会话: %s", exc)
                return session or self.sessions.get(token)

            session = session_runtime.read_session(token, load_current_session)
            if not session:
                return None
            
            # 兼容旧格式（字符串）
            if isinstance(session, str):
                user_id = session
            else:
                user_id = session.get("user_id")
                created_str = session.get("created_at", "")
                if self._session_is_expired(created_str):
                    self._delete_session(token)
                    return None
            
            if not user_id:
                return None
            
            user = self._read_user(user_id)
            if user:
                if token not in self.sessions:
                    self._save_session(
                        token,
                        {
                            "user_id": user_id,
                            "created_at": session.get(
                                "created_at", datetime.now(timezone.utc).isoformat()
                            ),
                        },
                    )
                return user
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过 ID 获取用户"""
        with self._lock:
            return self._read_user(user_id)
    
    def to_response(self, user: User) -> UserResponse:
        """转换为响应对象（不包含密码）"""
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            role=user.role,
            status=user.status,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login
        )
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> tuple[bool, str]:
        """
        修改用户密码
        
        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            (success, message) 成功返回 (True, "密码修改成功")，失败返回 (False, 错误信息)
        """
        with self._lock:
            users = self._load_users()
            
            user = self._read_user(user_id)
            if not user:
                return False, "用户不存在"
            
            # 验证旧密码
            if not self._verify_password(old_password, user.password):
                return False, "原密码错误"

            # 验证新密码
            if len(new_password) < 4:
                return False, "新密码长度至少为 4 位"

            if new_password == old_password:
                return False, "新密码不能与原密码相同"

            # 更新密码（bcrypt 哈希）
            user.password = self._hash_password(new_password)
            user.must_change_password = False
            user.updated_at = datetime.now().isoformat()
            self._save_user_record(users, user)
            self._delete_user_sessions(user_id)
            
            return True, "密码修改成功"
    
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

    def list_user_ids(self) -> list[str]:
        """列出当前所有用户 ID"""
        from app.repositories.user_config_runtime import list_user_ids

        with self._lock:
            return list_user_ids(lambda: list(self._load_users().keys()))


# 全局单例（线程安全）
_user_service: Optional[UserService] = None
_service_lock = threading.Lock()

def get_user_service() -> UserService:
    """获取用户服务单例（线程安全，double-checked locking）"""
    global _user_service
    if _user_service is None:
        with _service_lock:
            if _user_service is None:
                _user_service = UserService()
    return _user_service
