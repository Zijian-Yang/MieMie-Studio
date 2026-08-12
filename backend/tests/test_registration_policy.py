def test_registration_is_closed_by_default(monkeypatch):
    monkeypatch.delenv("MIEMIE_REGISTRATION_ENABLED", raising=False)
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "false")

    from app.services.admin_bootstrap import registration_enabled

    assert registration_enabled() is False


def test_register_returns_stable_closed_error(client, monkeypatch):
    monkeypatch.setattr("app.routers.auth.registration_enabled", lambda: False)

    response = client.post(
        "/api/auth/register",
        json={"username": "closed", "password": "pass1234"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "registration_disabled",
        "message": "管理员已关闭公开注册",
    }


def test_bootstrap_status_is_public(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth.bootstrap_status",
        lambda: {"admin_configured": True, "registration_enabled": False},
    )

    response = client.get("/api/bootstrap/status")

    assert response.status_code == 200
    assert response.json() == {
        "admin_configured": True,
        "registration_enabled": False,
    }
