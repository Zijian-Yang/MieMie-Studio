"""Bounded, secret-safe delivery for platform operations Webhook events."""

from __future__ import annotations

from datetime import datetime
import re
import time
from typing import Callable, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.platform_operations import PlatformOperationsSettings


_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class OpsWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    instance_id: str = Field(min_length=1, max_length=128)
    severity: Literal["info", "warning", "critical"]
    event_type: str = Field(min_length=1, max_length=128)
    state: Literal["queued", "running", "succeeded", "failed"]
    reason: str = Field(min_length=1, max_length=128)
    release_commit: str = Field(min_length=1, max_length=64)
    request_id: str | None = Field(default=None, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    occurred_at: datetime

    @field_validator(
        "instance_id",
        "event_type",
        "reason",
        "release_commit",
        "request_id",
        "run_id",
    )
    @classmethod
    def validate_safe_codes(cls, value: str | None, info) -> str | None:
        if value is not None and not _SAFE_CODE.fullmatch(value):
            raise ValueError(f"webhook_{info.field_name}_invalid")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("webhook_occurred_at_timezone_required")
        return value

    def payload(self) -> dict[str, str | None]:
        payload = self.model_dump(exclude={"occurred_at"})
        payload["occurred_at"] = self.occurred_at.isoformat().replace("+00:00", "Z")
        return payload


class WebhookDeliveryResult(BaseModel):
    delivered: bool
    skipped: bool = False
    attempts: int = 0
    status_code: int | None = None
    failure_category: str | None = None


class OpsWebhookClient:
    """Send one fixed event with bounded timeout and retry behavior."""

    def __init__(
        self,
        *,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._client_factory = client_factory
        self._sleeper = sleeper

    def send(
        self,
        event: OpsWebhookEvent,
        settings: PlatformOperationsSettings,
    ) -> WebhookDeliveryResult:
        if not settings.webhook_enabled or not settings.webhook_url:
            return WebhookDeliveryResult(
                delivered=False,
                skipped=True,
                failure_category="webhook_disabled",
            )

        attempts_allowed = settings.webhook_retry_count + 1
        last_category = "webhook_unknown_error"
        last_status: int | None = None
        with self._client_factory(
            timeout=httpx.Timeout(float(settings.webhook_timeout_seconds)),
            follow_redirects=False,
        ) as client:
            for attempt in range(1, attempts_allowed + 1):
                try:
                    response = client.post(settings.webhook_url, json=event.payload())
                    last_status = response.status_code
                    if 200 <= response.status_code < 300:
                        return WebhookDeliveryResult(
                            delivered=True,
                            attempts=attempt,
                            status_code=response.status_code,
                        )
                    if 400 <= response.status_code < 500:
                        return WebhookDeliveryResult(
                            delivered=False,
                            attempts=attempt,
                            status_code=response.status_code,
                            failure_category="webhook_http_4xx",
                        )
                    if 500 <= response.status_code < 600:
                        last_category = "webhook_http_5xx"
                    else:
                        return WebhookDeliveryResult(
                            delivered=False,
                            attempts=attempt,
                            status_code=response.status_code,
                            failure_category="webhook_http_unexpected",
                        )
                except httpx.TimeoutException:
                    last_category = "webhook_timeout"
                    last_status = None
                except httpx.NetworkError:
                    last_category = "webhook_network_error"
                    last_status = None

                if attempt < attempts_allowed:
                    self._sleeper(min(0.25 * (2 ** (attempt - 1)), 1.0))

        return WebhookDeliveryResult(
            delivered=False,
            attempts=attempts_allowed,
            status_code=last_status,
            failure_category=last_category,
        )


__all__ = [
    "OpsWebhookClient",
    "OpsWebhookEvent",
    "WebhookDeliveryResult",
]
