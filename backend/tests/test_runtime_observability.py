from app.services.runtime_observability import (
    build_request_observation,
    should_observe_request,
)


def test_should_observe_high_frequency_runtime_paths():
    assert should_observe_request("GET", "/api/studio")
    assert should_observe_request("POST", "/api/studio/task_123/generate")
    assert should_observe_request("GET", "/api/studio/task_123")
    assert should_observe_request("GET", "/api/video-studio/task_123/status")
    assert should_observe_request("GET", "/api/image-benchmark/runs/run_123")
    assert should_observe_request("GET", "/api/video-benchmark/runs/run_123")


def test_should_skip_low_signal_and_static_paths():
    assert not should_observe_request("GET", "/api/health")
    assert not should_observe_request("GET", "/assets/example.png")
    assert not should_observe_request("POST", "/api/auth/login")


def test_build_request_observation_sanitizes_sensitive_query_values():
    observation = build_request_observation(
        method="GET",
        path="/api/video-studio/task_123/status",
        query_params={
            "project_id": "project_123",
            "api_key": "sk-secret",
            "access_token": "secret-token",
            "prompt": "真实提示词",
            "video_url": "https://example.com/output.mp4",
            "token": "secret-token",
            "page": "2",
        },
        status_code=200,
        duration_ms=12.34,
        user_id="user_123",
        request_id="req_123",
    )

    assert observation == {
        "method": "GET",
        "path": "/api/video-studio/task_123/status",
        "status_code": 200,
        "duration_ms": 12.34,
        "user_id": "user_123",
        "request_id": "req_123",
        "query": {
            "project_id": "project_123",
            "api_key": "[redacted]",
            "access_token": "[redacted]",
            "prompt": "[redacted]",
            "video_url": "[redacted]",
            "token": "[redacted]",
            "page": "2",
        },
    }
