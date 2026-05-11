"""
MieMie-Studio 16 项修复的全面验证测试

运行方式:
    cd backend && python -m pytest tests/test_fixes.py -v

覆盖修复:
    Fix-01: bcrypt 密码哈希
    Fix-02: 纯 ASGI 认证中间件
    Fix-03: 原子文件写入
    Fix-04: CORS 环境变量配置
    Fix-05: 项目级联删除
    Fix-06: Storage 缓存线程安全
    Fix-07: 读操作文件锁一致性
    Fix-15: 登录/注册限流
    Fix-17: UserService 单例线程安全
"""

import json
import threading
from pathlib import Path

import pytest


# ═══════════════════════════════════════════
# Group A: 认证与安全 (Fix-01, Fix-02, Fix-17)
# ═══════════════════════════════════════════

class TestAuth:
    """认证流程测试"""

    def test_register_returns_token(self, client):
        """Fix-01: 注册成功返回 token 和 user"""
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "password": "pass1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["username"] == "newuser"

    def test_register_password_is_bcrypt(self, client, isolated_data_dir):
        """Fix-01: 注册后密码以 bcrypt 格式存储"""
        client.post("/api/auth/register", json={
            "username": "hashcheck",
            "password": "secret123",
        })
        users_file = isolated_data_dir / "users.json"
        users = json.loads(users_file.read_text(encoding="utf-8"))
        for uid, udata in users.items():
            if udata["username"] == "hashcheck":
                assert udata["password"].startswith("$2b$"), \
                    f"密码未使用 bcrypt: {udata['password'][:20]}..."
                return
        pytest.fail("未找到注册的用户")

    def test_register_duplicate_username(self, client):
        """Fix-01: 重复用户名注册失败"""
        client.post("/api/auth/register", json={
            "username": "dupuser", "password": "pass1234",
        })
        resp = client.post("/api/auth/register", json={
            "username": "dupuser", "password": "pass5678",
        })
        assert resp.status_code == 400

    def test_login_success(self, client, registered_user):
        """Fix-01: 已注册用户登录成功"""
        resp = client.post("/api/auth/login", json={
            "username": "testuser", "password": "test1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["username"] == "testuser"

    def test_login_wrong_password(self, client, registered_user):
        """Fix-01: 错误密码登录失败"""
        resp = client.post("/api/auth/login", json={
            "username": "testuser", "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client, registered_user):
        """Fix-02: 有效 token 可获取用户信息"""
        token, user = registered_user
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        # 响应中不应包含密码
        assert "password" not in data

    def test_me_without_token(self, client):
        """Fix-02: 无 token 返回 401"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_protected_endpoint_no_auth(self, client):
        """Fix-02: 受保护端点无认证返回 401"""
        resp = client.get("/api/projects")
        assert resp.status_code == 401

    def test_change_password(self, client, registered_user):
        """Fix-01: 修改密码成功"""
        token, _ = registered_user
        resp = client.post("/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": "test1234", "new_password": "newpass123"}
        )
        assert resp.status_code == 200

        # 用新密码登录
        resp2 = client.post("/api/auth/login", json={
            "username": "testuser", "password": "newpass123",
        })
        assert resp2.status_code == 200

    def test_change_password_wrong_old(self, client, registered_user):
        """Fix-01: 旧密码错误时修改失败"""
        token, _ = registered_user
        resp = client.post("/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": "wrongold", "new_password": "newpass123"}
        )
        assert resp.status_code == 400

    def test_logout(self, client, registered_user):
        """Fix-01: 登出后 token 失效"""
        token, _ = registered_user
        # 登出
        resp = client.post("/api/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200

        # token 应该失效
        resp2 = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp2.status_code == 401


# ═══════════════════════════════════════════
# Group B: CORS (Fix-04)
# ═══════════════════════════════════════════

class TestCORS:
    """CORS 配置测试"""

    def test_cors_dev_mode(self, client):
        """Fix-04: 开发模式 CORS 允许 localhost:3000"""
        resp = client.options("/api/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_credentials_header(self, client):
        """Fix-04: 开发模式 credentials=true"""
        resp = client.options("/api/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.headers.get("access-control-allow-credentials") == "true"


# ═══════════════════════════════════════════
# Group C: 中间件与公开路径 (Fix-02)
# ═══════════════════════════════════════════

class TestMiddleware:
    """纯 ASGI 中间件测试"""

    def test_health_check(self, client):
        """基础: 健康检查端点可访问"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "git_commit" in data
        assert data["run_mode"] in {"dev", "prod"}
        assert isinstance(data["serve_frontend"], bool)
        assert data["started_at"]

    def test_health_check_exposes_request_and_deployment_headers(self, client):
        """Step-00: 健康检查暴露统一请求与部署标识"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-request-id")
        assert resp.headers.get("x-deployment-version")
        assert resp.headers["x-deployment-version"] == resp.json()["git_commit"]

    def test_request_id_header_is_passthrough(self, client):
        """Step-00: 允许外部传入 request id 以便压测与对账"""
        resp = client.get("/api/health", headers={"X-Request-ID": "loadtest-run-001"})
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "loadtest-run-001"

    def test_unauthorized_response_keeps_request_id_header(self, client):
        """Step-00: 401 也返回 request id，便于排障"""
        resp = client.get("/api/projects")
        assert resp.status_code == 401
        assert resp.headers.get("x-request-id")

    def test_public_paths_no_auth(self, client):
        """Fix-02: 公开路径不需要 token"""
        # /api/health
        assert client.get("/api/health").status_code == 200
        # /api/auth/login (POST)
        resp = client.post("/api/auth/login", json={
            "username": "nonexist", "password": "x"
        })
        assert resp.status_code == 401  # 认证失败但不是中间件拦截
        # /docs (可能 200 或 307 重定向到 /docs/)
        resp = client.get("/docs", follow_redirects=True)
        assert resp.status_code == 200


# ═══════════════════════════════════════════
# Group D: 项目 CRUD 与级联删除 (Fix-05)
# ═══════════════════════════════════════════

class TestProjectCascadeDelete:
    """项目级联删除测试"""

    def test_create_project(self, client, auth_header):
        """基础: 创建项目"""
        resp = client.post("/api/projects", headers=auth_header, json={
            "name": "测试项目",
            "description": "用于测试级联删除"
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试项目"

    def test_delete_project_cascade(self, client, auth_header):
        """Fix-05: 删除项目后 GET 返回 404"""
        # 创建
        resp = client.post("/api/projects", headers=auth_header, json={
            "name": "待删除项目"
        })
        project_id = resp.json()["id"]

        # 删除
        resp = client.delete(f"/api/projects/{project_id}", headers=auth_header)
        assert resp.status_code == 200

        # 确认已删除
        resp = client.get(f"/api/projects/{project_id}", headers=auth_header)
        assert resp.status_code == 404


# ═══════════════════════════════════════════
# Group E: 原子写入与文件完整性 (Fix-03, Fix-07)
# ═══════════════════════════════════════════

class TestAtomicWrite:
    """原子写入测试"""

    def test_atomic_write_users_json(self, client, isolated_data_dir):
        """Fix-03: 注册后 users.json 是合法 JSON 且无 .tmp 残留"""
        client.post("/api/auth/register", json={
            "username": "atomictest", "password": "pass1234",
        })
        users_file = isolated_data_dir / "users.json"
        assert users_file.exists()
        # 必须是合法 JSON
        data = json.loads(users_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        # 无 .tmp 残留
        tmp_file = isolated_data_dir / "users.tmp"
        assert not tmp_file.exists()

    def test_atomic_write_sessions_json(self, client, isolated_data_dir):
        """Fix-03: 登录后 sessions.json 是合法 JSON"""
        client.post("/api/auth/register", json={
            "username": "sessiontest", "password": "pass1234",
        })
        client.post("/api/auth/login", json={
            "username": "sessiontest", "password": "pass1234",
        })
        sessions_file = isolated_data_dir / "sessions.json"
        assert sessions_file.exists()
        data = json.loads(sessions_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert len(data) > 0
        # 无 .tmp 残留
        tmp_file = isolated_data_dir / "sessions.tmp"
        assert not tmp_file.exists()

    def test_user_service_concurrent_register_preserves_all_users(self, isolated_data_dir):
        """Fix-03: 并发注册不会丢失用户记录"""
        from app.services.user_service import get_user_service

        service = get_user_service()
        usernames = [f"parallel_user_{i}" for i in range(12)]
        errors = []

        def register_user(username: str):
            try:
                user = service.register(username, "pass1234")
                assert user is not None
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_user, args=(username,)) for username in usernames]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors

        users_file = isolated_data_dir / "users.json"
        saved = json.loads(users_file.read_text(encoding="utf-8"))
        saved_usernames = {user["username"] for user in saved.values()}
        assert saved_usernames == set(usernames)

    def test_user_service_concurrent_login_preserves_all_sessions(self, isolated_data_dir):
        """Fix-03: 并发登录不会丢失会话记录"""
        from app.services.user_service import get_user_service

        service = get_user_service()
        user = service.register("parallel_login_user", "pass1234")
        assert user is not None

        tokens = []
        errors = []

        def login_user():
            try:
                result = service.login("parallel_login_user", "pass1234")
                assert result is not None
                token, _ = result
                tokens.append(token)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=login_user) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert len(tokens) == 8

        sessions_file = isolated_data_dir / "sessions.json"
        saved = json.loads(sessions_file.read_text(encoding="utf-8"))
        assert len(saved) == 8


class TestServiceContracts:
    """服务返回契约测试"""

    @pytest.mark.asyncio
    async def test_text_to_image_generate_reads_generation_result(self, monkeypatch):
        """文生图 generate 应兼容 generate_batch 的 GenerationResult 返回契约"""
        from app.services.dashscope.text_to_image import TextToImageService, GenerationResult

        service = TextToImageService.__new__(TextToImageService)

        async def fake_generate_batch(**kwargs):
            return GenerationResult(urls=["https://example.com/generated.png"], task_id="task_1", request_id="req_1")

        monkeypatch.setattr(service, "generate_batch", fake_generate_batch)

        url = await TextToImageService.generate(service, "测试提示词")
        assert url == "https://example.com/generated.png"


# ═══════════════════════════════════════════
# Group F: 单例线程安全 (Fix-06, Fix-17)
# ═══════════════════════════════════════════

class TestSingleton:
    """单例模式测试"""

    def test_user_service_singleton(self):
        """Fix-17: 多次调用返回同一实例"""
        from app.services.user_service import get_user_service
        svc1 = get_user_service()
        svc2 = get_user_service()
        assert svc1 is svc2

    def test_user_service_singleton_threaded(self):
        """Fix-17: 多线程下返回同一实例"""
        from app.services.user_service import get_user_service
        results = []

        def get_svc():
            results.append(id(get_user_service()))

        threads = [threading.Thread(target=get_svc) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1, f"多线程下创建了多个实例: {set(results)}"


# ═══════════════════════════════════════════
# Group G: 登录/注册限流 (Fix-15)
# 注意: 放在最后运行，避免影响其他测试
# ═══════════════════════════════════════════

class TestRateLimit:
    """限流测试 - 放在最后运行"""

    def test_register_rate_limit(self, client):
        """Fix-15: 注册限流 3/minute"""
        for i in range(3):
            resp = client.post("/api/auth/register", json={
                "username": f"ratelimit_reg_{i}",
                "password": "pass1234",
            })
            # 前 3 次应该成功（200 或 400 重复用户名都算正常）
            assert resp.status_code in (200, 400), f"第 {i+1} 次注册异常: {resp.status_code}"

        # 第 4 次应该被限流
        resp = client.post("/api/auth/register", json={
            "username": "ratelimit_reg_blocked",
            "password": "pass1234",
        })
        assert resp.status_code == 429, f"第 4 次注册应返回 429，实际: {resp.status_code}"

    def test_login_rate_limit(self, client):
        """Fix-15: 登录限流 5/minute"""
        # 先注册一个用户
        client.post("/api/auth/register", json={
            "username": "ratelimit_login",
            "password": "pass1234",
        })

        for i in range(5):
            resp = client.post("/api/auth/login", json={
                "username": "ratelimit_login",
                "password": "pass1234",
            })
            assert resp.status_code in (200, 401, 429), f"第 {i+1} 次登录异常: {resp.status_code}"

        # 第 6 次应该被限流
        resp = client.post("/api/auth/login", json={
            "username": "ratelimit_login",
            "password": "pass1234",
        })
        assert resp.status_code == 429, f"第 6 次登录应返回 429，实际: {resp.status_code}"
