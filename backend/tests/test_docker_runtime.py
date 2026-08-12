from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_runs_gunicorn_without_login_shell_path_reset():
    dockerfile = ROOT / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert '"sh", "-c"' in content
    assert '"sh", "-lc"' not in content
    assert "exec /opt/venv/bin/gunicorn app.main:app" in content


def test_compose_runs_database_migrations_before_application_services():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    migrate = services["migrate"]
    assert migrate["image"] == "${MIEMIE_IMAGE:-miemie-studio:local}"
    assert migrate["restart"] == "no"
    assert migrate["command"] == [
        "/opt/venv/bin/alembic",
        "-c",
        "/app/backend/alembic.ini",
        "upgrade",
        "head",
    ]
    assert migrate["depends_on"]["postgres"]["condition"] == "service_healthy"

    for service_name in ("api", "worker", "worker-video"):
        assert services[service_name]["image"] == migrate["image"]
        dependency = services[service_name]["depends_on"]["migrate"]
        assert dependency["condition"] == "service_completed_successfully"


def test_compose_fresh_install_defaults_to_postgres_only_runtime():
    content = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert '${MIEMIE_DATABASE_ENABLED:-true}' in content
    assert '${MIEMIE_DATABASE_WRITE_MODE:-postgres}' in content
    assert '${MIEMIE_DATABASE_READ_MODE:-postgres}' in content
    assert '${MIEMIE_DATABASE_JSON_FALLBACK_READ:-false}' in content
    assert '${MIEMIE_DATABASE_JSON_ARCHIVE_WRITES:-false}' in content
    assert '${MIEMIE_DATABASE_RECONCILE_STRICT:-true}' in content


def test_compose_example_uses_local_bind_and_rejectable_secret_placeholders():
    content = (ROOT / "compose.env.example").read_text(encoding="utf-8")

    assert "MIEMIE_HOST_BIND=127.0.0.1" in content
    assert "MIEMIE_DATABASE_ENABLED=true" in content
    assert "MIEMIE_DATABASE_WRITE_MODE=postgres" in content
    assert "MIEMIE_DATABASE_READ_MODE=postgres" in content
    assert "MIEMIE_DATABASE_JSON_FALLBACK_READ=false" in content
    assert "MIEMIE_DATABASE_RECONCILE_STRICT=true" in content
    assert "MIEMIE_POSTGRES_PASSWORD=replace-with-strong-password" in content
