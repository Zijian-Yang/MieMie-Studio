import pytest


def test_qwen_sync_models_keep_submit_rate_even_when_inflight_is_unlimited():
    from app.services.model_rate_limits import (
        get_model_rate_limit,
        rate_limit_capabilities,
        validate_group_count_for_model,
    )

    qwen_pro = get_model_rate_limit("qwen-image-2.0-pro")
    assert qwen_pro is not None
    assert qwen_pro.api_mode == "sync"
    assert qwen_pro.submit_rate_limit.count == 2
    assert qwen_pro.submit_rate_limit.period_seconds == 60
    assert qwen_pro.max_inflight is None
    assert qwen_pro.inflight_scope == "unlimited"

    qwen_plus = rate_limit_capabilities("qwen-image-plus")
    assert qwen_plus["api_mode"] == "sync"
    assert qwen_plus["submit_rate_limit"] == {"count": 2, "period_seconds": 1}
    assert qwen_plus["max_concurrent"] is None
    assert qwen_plus["concurrency_scope"] == "unlimited"

    validate_group_count_for_model("qwen-image-plus", 20)


def test_async_video_models_expose_finite_or_shared_inflight_limits():
    from app.services.model_rate_limits import (
        get_model_rate_limit,
        rate_limit_capabilities,
        validate_group_count_for_model,
    )

    wan_snapshot = get_model_rate_limit("wan2.7-i2v-2026-04-25")
    assert wan_snapshot is not None
    assert wan_snapshot.api_mode == "async"
    assert wan_snapshot.submit_rate_limit.count == 5
    assert wan_snapshot.submit_rate_limit.period_seconds == 1
    assert wan_snapshot.max_inflight == 5
    assert wan_snapshot.inflight_scope == "model"

    kling = rate_limit_capabilities("kling/kling-v3-omni-video-generation")
    assert kling["api_mode"] == "async"
    assert kling["max_concurrent"] == 10
    assert kling["concurrency_scope"] == "shared_pool"
    assert kling["concurrency_pool_id"] == "aliyun:kling:video-image"

    vidu = rate_limit_capabilities("vidu/viduq3-turbo_img2video")
    assert vidu["api_mode"] == "async"
    assert vidu["max_concurrent"] == 5
    assert vidu["concurrency_scope"] == "shared_pool"
    assert vidu["concurrency_pool_id"] == "aliyun:vidu:video"

    validate_group_count_for_model("wan2.7-i2v", 5)
    with pytest.raises(ValueError, match="不能超过并发上限 5"):
        validate_group_count_for_model("wan2.7-i2v", 6)


@pytest.mark.asyncio
async def test_submit_rate_limiter_waits_for_qwen_two_per_minute():
    from app.services.model_rate_limits import SubmitRateLimiter

    now = 100.0
    sleeps = []

    def fake_clock():
        return now

    async def fake_sleep(delay: float):
        nonlocal now
        sleeps.append(delay)
        now += delay

    limiter = SubmitRateLimiter(clock=fake_clock, sleep=fake_sleep)

    await limiter.wait("qwen-image-max")
    await limiter.wait("qwen-image-max")
    await limiter.wait("qwen-image-max")

    assert sleeps == [60.0]


@pytest.mark.asyncio
async def test_inflight_limiter_uses_shared_pools_and_skips_unlimited_models():
    from app.services.model_rate_limits import ModelInflightLimiter

    limiter = ModelInflightLimiter()

    qwen_lease = await limiter.acquire("qwen-image-2.0-pro")
    assert qwen_lease.acquired is False
    qwen_lease.release()

    first = await limiter.acquire("vidu/viduq3-turbo_img2video")
    second = await limiter.acquire("vidu/viduq3-pro_img2video")

    assert first.acquired is True
    assert second.acquired is True
    assert first.pool_key == second.pool_key == "aliyun:vidu:video"

    second.release()
    first.release()
