"""Aliyun/DashScope model submit-rate and in-flight concurrency limits.

The vendor document exposes two separate constraints: task submit rate and
the number of tasks simultaneously being processed. The latter depends on the
actual API mode used by this platform, not only on what a model can support.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Deque, Dict, Literal, Optional


ApiMode = Literal["sync", "async"]
InflightScope = Literal["model", "shared_pool", "unlimited", "unknown"]


@dataclass(frozen=True)
class SubmitRateLimit:
    count: int
    period_seconds: int

    def as_dict(self) -> Dict[str, int]:
        return {"count": self.count, "period_seconds": self.period_seconds}


@dataclass(frozen=True)
class ModelRateLimitSpec:
    api_mode: ApiMode
    submit_rate_limit: SubmitRateLimit
    max_inflight: Optional[int]
    inflight_scope: InflightScope
    shared_pool_id: Optional[str] = None
    source_note: str = "docs/阿里云模型api文档/阿里模型限流.md"


def _sync(count: int, period_seconds: int, *, note: str = "") -> ModelRateLimitSpec:
    return ModelRateLimitSpec(
        api_mode="sync",
        submit_rate_limit=SubmitRateLimit(count=count, period_seconds=period_seconds),
        max_inflight=None,
        inflight_scope="unlimited",
        source_note=note or "同步接口同时处理中任务数量无限制；仍受任务下发接口调用限制约束。",
    )


def _async_model(count: int, period_seconds: int, max_inflight: int, *, note: str = "") -> ModelRateLimitSpec:
    return ModelRateLimitSpec(
        api_mode="async",
        submit_rate_limit=SubmitRateLimit(count=count, period_seconds=period_seconds),
        max_inflight=max_inflight,
        inflight_scope="model",
        source_note=note or "异步任务接口：提交频率与同时处理中任务数量均按文档限制。",
    )


def _async_shared(
    count: int,
    period_seconds: int,
    max_inflight: int,
    pool_id: str,
    *,
    note: str,
) -> ModelRateLimitSpec:
    return ModelRateLimitSpec(
        api_mode="async",
        submit_rate_limit=SubmitRateLimit(count=count, period_seconds=period_seconds),
        max_inflight=max_inflight,
        inflight_scope="shared_pool",
        shared_pool_id=pool_id,
        source_note=note,
    )


MODEL_RATE_LIMITS: Dict[str, ModelRateLimitSpec] = {
    # Qwen image models: this platform calls the synchronous API.
    "qwen-image-2.0-pro": _sync(2, 60),
    "qwen-image-2.0": _sync(2, 1),
    "qwen-image-max": _sync(2, 60),
    "qwen-image-plus": _sync(2, 1, note="平台使用同步 HTTP 接口，因此不套用文档中的异步接口并发 2。"),
    "qwen-image-edit-max": _sync(2, 60),
    "qwen-image-edit-plus": _sync(2, 1),
    # Wan image models: async task APIs.
    "wan2.7-image-pro": _async_model(5, 1, 5),
    "wan2.7-image": _async_model(5, 1, 5),
    "wan2.6-image": _async_model(5, 1, 5),
    "wan2.6-t2i": _async_model(1, 1, 5, note="中国内地部署范围：任务下发 1 次/秒，同时处理中任务数 5。"),
    "wan2.5-t2i-preview": _async_model(5, 1, 5),
    "wan2.5-i2i-preview": _async_model(5, 1, 5),
    # Wan video models: async task APIs.
    "wan2.7-t2v": _async_model(5, 1, 5),
    "wan2.7-i2v": _async_model(5, 1, 5),
    "wan2.7-i2v-2026-04-25": _async_model(5, 1, 5),
    "wan2.7-r2v": _async_model(5, 1, 5),
    "wan2.7-videoedit": _async_model(5, 1, 5),
    "wan2.6-t2v": _async_model(5, 1, 5),
    "wan2.5-t2v-preview": _async_model(5, 1, 5),
    "wan2.6-i2v-flash": _async_model(5, 1, 5),
    "wan2.6-i2v": _async_model(5, 1, 5),
    "wan2.5-i2v-preview": _async_model(5, 1, 5),
    "wan2.6-r2v-flash": _async_model(5, 1, 5),
    "wan2.6-r2v": _async_model(5, 1, 5),
    "wan2.2-t2v-plus": _async_model(2, 1, 2),
    "wanx2.1-t2v-turbo": _async_model(2, 1, 2),
    "wanx2.1-t2v-plus": _async_model(2, 1, 2),
    "wanx2.1-i2v-turbo": _async_model(2, 1, 2),
    "wan2.2-s2v": _async_model(1, 1, 1),
    # HappyHorse video models.
    "happyhorse-1.0-t2v": _async_model(5, 1, 5),
    "happyhorse-1.0-i2v": _async_model(5, 1, 5),
    "happyhorse-1.0-r2v": _async_model(5, 1, 5),
    "happyhorse-1.0-video-edit": _async_model(5, 1, 5),
    # Kling video models share one in-flight pool across Kling image/video models.
    "kling/kling-v3-video-generation": _async_shared(
        5,
        1,
        10,
        "aliyun:kling:video-image",
        note="同一阿里云百炼 API Key 下，可灵图像/视频 4 个模型共享 10 个处理中任务。",
    ),
    "kling/kling-v3-omni-video-generation": _async_shared(
        5,
        1,
        10,
        "aliyun:kling:video-image",
        note="同一阿里云百炼 API Key 下，可灵图像/视频 4 个模型共享 10 个处理中任务。",
    ),
}

for _vidu_model_id in (
    "vidu/viduq3-pro_text2video",
    "vidu/viduq3-turbo_text2video",
    "vidu/viduq2_text2video",
    "vidu/viduq3-pro_img2video",
    "vidu/viduq3-turbo_img2video",
    "vidu/viduq2-pro_img2video",
    "vidu/viduq2-turbo_img2video",
    "vidu/viduq3-pro_start-end2video",
    "vidu/viduq3-turbo_start-end2video",
    "vidu/viduq2-pro_start-end2video",
    "vidu/viduq2-turbo_start-end2video",
    "vidu/viduq2_reference2video",
    "vidu/viduq2-pro_reference2video",
):
    MODEL_RATE_LIMITS[_vidu_model_id] = _async_shared(
        5,
        1,
        5,
        "aliyun:vidu:video",
        note="同一个阿里云百炼 API Key 在 13 个 Vidu 视频模型间共享 5 个处理中任务。",
    )


def get_model_rate_limit(model_id: Optional[str]) -> Optional[ModelRateLimitSpec]:
    if not model_id:
        return None
    return MODEL_RATE_LIMITS.get(model_id)


def rate_limit_capabilities(model_id: Optional[str], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a frontend/API capability dict with rate-limit metadata merged in."""

    capabilities = dict(existing or {})
    spec = get_model_rate_limit(model_id)
    if not spec:
        return capabilities

    capabilities.update(
        {
            "api_mode": spec.api_mode,
            "submit_rate_limit": spec.submit_rate_limit.as_dict(),
            "max_concurrent": spec.max_inflight,
            "concurrency_scope": spec.inflight_scope,
            "rate_limit_note": spec.source_note,
        }
    )
    if spec.shared_pool_id:
        capabilities["concurrency_pool_id"] = spec.shared_pool_id
    else:
        capabilities.pop("concurrency_pool_id", None)
    return capabilities


def validate_group_count_for_model(model_id: Optional[str], group_count: int) -> None:
    spec = get_model_rate_limit(model_id)
    if not spec or spec.max_inflight is None:
        return
    if group_count > spec.max_inflight:
        raise ValueError(f"模型 {model_id} 生成组数不能超过并发上限 {spec.max_inflight}")


class SubmitRateLimiter:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._history: Dict[str, Deque[float]] = defaultdict(deque)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def wait(self, model_id: Optional[str]) -> None:
        spec = get_model_rate_limit(model_id)
        if not spec:
            return
        limit = spec.submit_rate_limit
        key = model_id or "_unknown"
        async with self._locks[key]:
            while True:
                now = self._clock()
                history = self._history[key]
                while history and now - history[0] >= limit.period_seconds:
                    history.popleft()
                if len(history) < limit.count:
                    history.append(now)
                    return
                wait_seconds = max(0.0, limit.period_seconds - (now - history[0]))
                await self._sleep(wait_seconds)


class InflightLease:
    def __init__(self, semaphore: Optional[asyncio.Semaphore], pool_key: Optional[str]) -> None:
        self._semaphore = semaphore
        self.pool_key = pool_key
        self.acquired = semaphore is not None
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._semaphore is not None:
            self._semaphore.release()


class ModelInflightLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._semaphores: Dict[str, asyncio.Semaphore] = {}

    def _pool_key_for(self, model_id: Optional[str], spec: ModelRateLimitSpec) -> str:
        if spec.inflight_scope == "shared_pool" and spec.shared_pool_id:
            return spec.shared_pool_id
        return f"model:{model_id}"

    async def acquire(self, model_id: Optional[str]) -> InflightLease:
        spec = get_model_rate_limit(model_id)
        if not spec or spec.max_inflight is None:
            return InflightLease(None, None)
        pool_key = self._pool_key_for(model_id, spec)
        async with self._lock:
            semaphore = self._semaphores.get(pool_key)
            if semaphore is None:
                semaphore = asyncio.Semaphore(spec.max_inflight)
                self._semaphores[pool_key] = semaphore
        await semaphore.acquire()
        return InflightLease(semaphore, pool_key)


submit_rate_limiter = SubmitRateLimiter()
model_inflight_limiter = ModelInflightLimiter()


async def wait_for_model_submit(model_id: Optional[str]) -> None:
    await submit_rate_limiter.wait(model_id)


async def acquire_model_inflight_lease(model_id: Optional[str]) -> InflightLease:
    return await model_inflight_limiter.acquire(model_id)


@asynccontextmanager
async def model_inflight_context(model_id: Optional[str]):
    lease = await acquire_model_inflight_lease(model_id)
    try:
        yield lease
    finally:
        lease.release()
