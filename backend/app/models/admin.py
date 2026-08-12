"""Typed administrator API request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.user import UserResponse


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=128)
    role: Literal["admin", "member"] = "member"
    must_change_password: bool = True


class AdminUserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["admin", "member"] | None = None
    status: Literal["active", "disabled"] | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)
    must_change_password: bool = True


class AdminUserPageResponse(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int


class PlatformSettingsResponse(BaseModel):
    registration_enabled: bool


class PlatformSettingsUpdateRequest(BaseModel):
    registration_enabled: bool


class AdminAuditItemResponse(BaseModel):
    id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: str | None = None
    request_id: str | None = None
    result: str
    changes: dict[str, Any]
    created_at: datetime


class AdminAuditPageResponse(BaseModel):
    items: list[AdminAuditItemResponse]
    page: int
    page_size: int
    total: int
