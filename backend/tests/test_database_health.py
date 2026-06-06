from app.db.engine import database_health, sanitized_database_url


def test_database_health_disabled(monkeypatch, client):
    monkeypatch.delenv("MIEMIE_DATABASE_ENABLED", raising=False)
    monkeypatch.delenv("MIEMIE_DATABASE_URL", raising=False)

    assert database_health() == {"configured": False, "ok": None}

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == {"configured": False, "ok": None}


def test_database_health_enabled_without_url(monkeypatch):
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.delenv("MIEMIE_DATABASE_URL", raising=False)

    assert database_health() == {
        "configured": False,
        "ok": False,
        "error": "MissingDatabaseUrl",
    }


def test_database_health_invalid_url_does_not_leak_password(monkeypatch):
    secret = "super-secret-password"
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv(
        "MIEMIE_DATABASE_URL",
        f"postgresql+psycopg://miemie:{secret}@127.0.0.1:1/miemie",
    )

    health = database_health(timeout_seconds=1)
    assert health["configured"] is True
    assert health["ok"] is False
    assert "error" in health
    assert secret not in str(health)

    sanitized = sanitized_database_url()
    assert sanitized is not None
    assert secret not in sanitized
    assert "miemie:***@" in sanitized
