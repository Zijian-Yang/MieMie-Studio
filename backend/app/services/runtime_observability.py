from __future__ import annotations

from typing import Any, Mapping


SENSITIVE_QUERY_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "dashscope_api_key",
    "key",
    "password",
    "secret",
    "token",
}

SENSITIVE_QUERY_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "key",
    "password",
    "prompt",
    "secret",
    "token",
    "url",
)


def should_observe_request(method: str, path: str) -> bool:
    """Return true for high-frequency runtime paths worth lightweight timing logs."""
    method = method.upper()

    if path.startswith("/api/studio"):
        if method == "GET":
            return True
        return method == "POST" and path.endswith("/generate")

    if path.startswith("/api/video-studio"):
        if method == "GET":
            return True
        return method == "POST" and path == "/api/video-studio"

    if path.startswith("/api/image-benchmark") or path.startswith("/api/video-benchmark"):
        return method == "GET"

    return False


def build_request_observation(
    *,
    method: str,
    path: str,
    query_params: Mapping[str, Any],
    status_code: int,
    duration_ms: float,
    user_id: str | None,
    request_id: str | None,
) -> dict[str, Any]:
    return {
        "method": method.upper(),
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "user_id": user_id or "-",
        "request_id": request_id or "-",
        "query": {
            key: "[redacted]" if _should_redact_query_key(key) else value
            for key, value in query_params.items()
        },
    }


def _should_redact_query_key(key: str) -> bool:
    lowered_key = key.lower()
    return lowered_key in SENSITIVE_QUERY_KEYS or any(
        fragment in lowered_key for fragment in SENSITIVE_QUERY_KEY_FRAGMENTS
    )
