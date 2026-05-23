"""Shared slowapi limiter construction."""

import os
import logging
from typing import Callable, List, Optional

from slowapi import Limiter

logger = logging.getLogger(__name__)


def redis_url_from_env() -> Optional[str]:
    """Return the configured Redis URL, if any."""
    return os.environ.get("MIEMIE_REDIS_URL", "").strip() or None


def rate_limit_storage_uri() -> Optional[str]:
    """Return the slowapi storage URI.

    `MIEMIE_RATE_LIMIT_STORAGE_URI` can override `MIEMIE_REDIS_URL` when a
    dedicated limiter store is needed. When neither is set, slowapi keeps its
    existing in-memory behavior.
    """
    explicit = os.environ.get("MIEMIE_RATE_LIMIT_STORAGE_URI", "").strip()
    if explicit:
        return explicit
    return redis_url_from_env()


def create_limiter(
    *,
    key_func: Callable,
    default_limits: Optional[List[str]] = None,
    key_prefix: str = "miemie",
) -> Limiter:
    storage_uri = rate_limit_storage_uri()
    if storage_uri:
        logger.info("[限流] 使用外部存储: %s", storage_uri.split("@")[-1])
    return Limiter(
        key_func=key_func,
        default_limits=default_limits or [],
        storage_uri=storage_uri,
        in_memory_fallback_enabled=True,
        key_prefix=key_prefix,
    )
