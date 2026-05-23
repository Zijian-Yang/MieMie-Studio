"""Optional Redis-backed session storage.

The file session store remains the source of compatibility. Redis is enabled
only when `MIEMIE_REDIS_URL` is configured and reachable.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    user_id: str
    created_at: str

    @classmethod
    def from_raw(cls, raw: object) -> Optional["SessionRecord"]:
        if isinstance(raw, str):
            return cls(user_id=raw, created_at="")
        if not isinstance(raw, dict):
            return None
        user_id = raw.get("user_id")
        if not user_id:
            return None
        return cls(user_id=user_id, created_at=raw.get("created_at", ""))

    def to_dict(self) -> Dict[str, str]:
        return {"user_id": self.user_id, "created_at": self.created_at}


class RedisSessionStore:
    def __init__(self, url: str, *, prefix: str = "miemie", ttl_seconds: int):
        import redis

        self.url = url
        self.prefix = prefix.rstrip(":")
        self.ttl_seconds = ttl_seconds
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.client.ping()

    @classmethod
    def from_env(cls, *, ttl_seconds: int) -> Optional["RedisSessionStore"]:
        url = os.environ.get("MIEMIE_REDIS_URL", "").strip()
        if not url:
            return None
        prefix = os.environ.get("MIEMIE_REDIS_KEY_PREFIX", "miemie").strip() or "miemie"
        try:
            return cls(url, prefix=prefix, ttl_seconds=ttl_seconds)
        except Exception as exc:
            logger.warning("[会话] Redis 不可用，回退文件会话: %s", exc)
            return None

    def _session_key(self, token: str) -> str:
        return f"{self.prefix}:session:{token}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"{self.prefix}:user_sessions:{user_id}"

    def get(self, token: str) -> Optional[SessionRecord]:
        raw = self.client.get(self._session_key(token))
        if not raw:
            return None
        try:
            return SessionRecord.from_raw(json.loads(raw))
        except json.JSONDecodeError:
            self.delete(token)
            return None

    def set(self, token: str, record: SessionRecord) -> None:
        self.client.setex(self._session_key(token), self.ttl_seconds, json.dumps(record.to_dict()))
        self.client.sadd(self._user_sessions_key(record.user_id), token)
        self.client.expire(self._user_sessions_key(record.user_id), self.ttl_seconds)

    def delete(self, token: str) -> None:
        record = self.get(token)
        if record:
            self.client.srem(self._user_sessions_key(record.user_id), token)
        self.client.delete(self._session_key(token))

    def delete_user_sessions(self, user_id: str) -> int:
        user_key = self._user_sessions_key(user_id)
        tokens = list(self.client.smembers(user_key))
        deleted = 0
        if tokens:
            deleted = int(self.client.delete(*(self._session_key(token) for token in tokens)))
        self.client.delete(user_key)
        return deleted
