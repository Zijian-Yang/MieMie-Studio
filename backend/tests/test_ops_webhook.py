from __future__ import annotations

from datetime import datetime, timezone
import json

import httpx
import pytest
from pydantic import ValidationError

from app.models.platform_operations import PlatformOperationsSettings
from app.services.ops_webhook import OpsWebhookClient, OpsWebhookEvent


def _event(**changes):
    values = {
        "instance_id": "miemie-pre",
        "severity": "info",
        "event_type": "platform.webhook.test",
        "state": "succeeded",
        "reason": "manual_test",
        "release_commit": "8f626cd",
        "request_id": "request-1",
        "run_id": "run-1",
        "occurred_at": datetime(2026, 8, 12, 8, 30, tzinfo=timezone.utc),
    }
    values.update(changes)
    return OpsWebhookEvent(**values)


def _settings(**changes):
    values = {
        "webhook_enabled": True,
        "webhook_url": "https://hooks.example.test/private-token",
        "webhook_timeout_seconds": 7,
        "webhook_retry_count": 2,
    }
    values.update(changes)
    return PlatformOperationsSettings(**values)


def _client(handler):
    transport = httpx.MockTransport(handler)
    return OpsWebhookClient(
        client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs)
    )


def test_disabled_webhook_is_skipped_without_opening_http_client():
    opened = False

    def factory(**kwargs):
        nonlocal opened
        opened = True
        return httpx.Client(**kwargs)

    result = OpsWebhookClient(client_factory=factory).send(
        _event(), _settings(webhook_enabled=False, webhook_url=None)
    )

    assert result.delivered is False
    assert result.skipped is True
    assert result.attempts == 0
    assert result.failure_category == "webhook_disabled"
    assert opened is False


def test_success_uses_fixed_payload_and_json_content_type():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(204)

    result = _client(handler).send(_event(), _settings())

    assert result.delivered is True
    assert result.skipped is False
    assert result.attempts == 1
    assert result.status_code == 204
    request = requests[0]
    payload = json.loads(request.content)
    assert request.headers["content-type"] == "application/json"
    assert payload == {
        "schema_version": "v1",
        "instance_id": "miemie-pre",
        "severity": "info",
        "event_type": "platform.webhook.test",
        "state": "succeeded",
        "reason": "manual_test",
        "release_commit": "8f626cd",
        "request_id": "request-1",
        "run_id": "run-1",
        "occurred_at": "2026-08-12T08:30:00Z",
    }


def test_4xx_is_not_retried_and_response_body_is_not_returned():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(403, text="private upstream response")

    result = _client(handler).send(_event(), _settings(webhook_retry_count=3))

    assert calls == 1
    assert result.delivered is False
    assert result.attempts == 1
    assert result.status_code == 403
    assert result.failure_category == "webhook_http_4xx"
    assert "private upstream response" not in repr(result)


def test_5xx_retries_until_success_with_bounded_attempts():
    statuses = iter((503, 502, 202))

    def handler(request):
        return httpx.Response(next(statuses))

    result = _client(handler).send(_event(), _settings(webhook_retry_count=2))

    assert result.delivered is True
    assert result.attempts == 3
    assert result.status_code == 202


@pytest.mark.parametrize(
    "exception,category",
    (
        (httpx.ReadTimeout("timeout"), "webhook_timeout"),
        (httpx.ConnectError("connect"), "webhook_network_error"),
    ),
)
def test_transport_failures_retry_and_return_stable_categories(exception, category):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise exception

    result = _client(handler).send(_event(), _settings(webhook_retry_count=1))

    assert calls == 2
    assert result.delivered is False
    assert result.attempts == 2
    assert result.status_code is None
    assert result.failure_category == category


def test_result_and_event_never_accept_or_expose_private_payload_fields():
    with pytest.raises(ValidationError):
        OpsWebhookEvent(
            **_event().model_dump(),
            prompt="private prompt",
        )

    with pytest.raises(ValidationError, match="webhook_reason_invalid"):
        _event(reason="private URL https://private.example.test/token")

    result = _client(lambda request: httpx.Response(500, text="secret body")).send(
        _event(), _settings(webhook_retry_count=0)
    )
    serialized = repr(result.model_dump())
    for forbidden in (
        "hooks.example.test",
        "private-token",
        "secret body",
        "private prompt",
    ):
        assert forbidden not in serialized


def test_configuration_limits_timeout_and_retry_count_before_sending():
    with pytest.raises(ValidationError):
        _settings(webhook_timeout_seconds=31)
    with pytest.raises(ValidationError):
        _settings(webhook_retry_count=4)


def test_event_time_requires_an_explicit_timezone():
    with pytest.raises(ValidationError, match="webhook_occurred_at_timezone_required"):
        _event(occurred_at=datetime(2026, 8, 12, 8, 30))
