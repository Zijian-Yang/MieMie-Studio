import sys
import types

from app.db.engine import (
    clear_database_health_engine,
    database_health,
    sanitized_database_url,
)


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
    clear_database_health_engine()
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
    clear_database_health_engine()


def test_database_health_reuses_engine(monkeypatch):
    clear_database_health_engine()
    created_engines = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, statement):
            assert statement == "select 1"

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def connect(self):
            return FakeConnection()

        def dispose(self):
            self.disposed = True

    def fake_create_engine(url, **kwargs):
        assert url == "postgresql+psycopg://miemie:secret@127.0.0.1:5432/miemie"
        assert kwargs["connect_args"] == {"connect_timeout": 1}
        engine = FakeEngine()
        created_engines.append(engine)
        return engine

    monkeypatch.setitem(
        sys.modules,
        "sqlalchemy",
        types.SimpleNamespace(create_engine=fake_create_engine, text=lambda statement: statement),
    )
    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv(
        "MIEMIE_DATABASE_URL",
        "postgresql+psycopg://miemie:secret@127.0.0.1:5432/miemie",
    )

    assert database_health(timeout_seconds=1) == {"configured": True, "ok": True}
    assert database_health(timeout_seconds=1) == {"configured": True, "ok": True}
    assert len(created_engines) == 1

    clear_database_health_engine()
    assert created_engines[0].disposed is True
