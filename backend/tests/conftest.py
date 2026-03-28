"""
测试配置 - 提供隔离的测试环境

使用临时目录作为数据目录，避免影响真实数据。
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# 在导入 app 之前设置环境，避免影响真实数据
_test_data_dir = None


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """为每个测试用例提供隔离的数据目录，并重置限流器"""
    global _test_data_dir
    _test_data_dir = tmp_path / "data"
    _test_data_dir.mkdir()

    # 重置全局单例，确保每个测试独立
    import app.services.user_service as us_mod
    with us_mod._service_lock:
        us_mod._user_service = None

    # 创建新的 UserService，使用临时目录
    from app.services.user_service import UserService
    svc = UserService.__new__(UserService)
    svc.data_dir = _test_data_dir
    svc.users_file = _test_data_dir / "users.json"
    svc.sessions = {}
    svc._ensure_data_dir()

    with us_mod._service_lock:
        us_mod._user_service = svc

    # 重置限流器状态，避免测试间干扰
    from app.routers.auth import limiter as auth_limiter
    from app.main import limiter as main_limiter
    auth_limiter.reset()
    main_limiter.reset()

    yield _test_data_dir


@pytest.fixture
def client():
    """创建 TestClient"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def registered_user(client):
    """注册一个测试用户，返回 (token, user_data)"""
    resp = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "test1234",
        "display_name": "Test User"
    })
    assert resp.status_code == 200
    data = resp.json()
    return data["token"], data["user"]


@pytest.fixture
def auth_header(registered_user):
    """返回认证 header"""
    token, _ = registered_user
    return {"Authorization": f"Bearer {token}"}
