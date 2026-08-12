from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import require_admin
from app.models.user import User


def _request(user=None):
    return SimpleNamespace(state=SimpleNamespace(user=user))


def test_require_admin_returns_active_administrator():
    admin = User(username="owner", password="hash", role="admin")

    assert require_admin(_request(admin)) == admin


@pytest.mark.parametrize(
    "user,status_code,error_code",
    [
        (None, 401, "authentication_required"),
        (User(username="member", password="hash"), 403, "admin_required"),
        (
            User(username="disabled", password="hash", role="admin", status="disabled"),
            403,
            "admin_required",
        ),
    ],
)
def test_require_admin_rejects_missing_member_and_disabled_admin(user, status_code, error_code):
    with pytest.raises(HTTPException) as exc_info:
        require_admin(_request(user))

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail["code"] == error_code
