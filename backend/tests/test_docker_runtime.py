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

    for service_name in ("api", "worker", "worker-video", "worker-ops", "scheduler"):
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
    assert "MIEMIE_PLATFORM_ENCRYPTION_KEY=replace-with-urlsafe-base64-32-byte-key" in content
    assert "MIEMIE_INSTANCE_ID=miemie-studio" in content


def test_ops_services_have_fixed_queue_scheduler_backup_root_and_no_host_privileges():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    worker = services["worker-ops"]
    assert worker["command"][-2:] == ["-Q", "ops"]
    assert "--concurrency=${MIEMIE_OPS_WORKER_CONCURRENCY:-1}" in worker["command"]
    assert "./backups:/var/lib/miemie/backups" in worker["volumes"]
    assert worker["environment"]["MIEMIE_PLATFORM_ENCRYPTION_KEY"] == "${MIEMIE_PLATFORM_ENCRYPTION_KEY:-}"

    scheduler = services["scheduler"]
    assert scheduler["command"] == ["/opt/venv/bin/python", "-m", "app.ops_scheduler"]
    assert scheduler["environment"]["MIEMIE_PLATFORM_ENCRYPTION_KEY"] == "${MIEMIE_PLATFORM_ENCRYPTION_KEY:-}"
    assert scheduler["environment"]["TZ"] == "${TZ:-Asia/Shanghai}"

    for name, service in services.items():
        if name != "api":
            assert not service.get("ports"), f"{name} must not publish host ports"
        mounts = " ".join(service.get("volumes", []))
        assert "docker.sock" not in mounts


def test_api_and_ops_runtime_receive_platform_identity_and_encryption_key():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    for service_name in ("api", "worker-ops", "scheduler"):
        environment = compose["services"][service_name]["environment"]
        assert environment["MIEMIE_INSTANCE_ID"] == "${MIEMIE_INSTANCE_ID:-miemie-studio}"
        assert environment["MIEMIE_PLATFORM_ENCRYPTION_KEY"] == "${MIEMIE_PLATFORM_ENCRYPTION_KEY:-}"


def test_runtime_image_contains_postgresql_client_without_docker_cli():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG POSTGRESQL_CLIENT_MAJOR=16" in content
    assert "postgresql-client-${POSTGRESQL_CLIENT_MAJOR}" in content
    assert "docker-ce-cli" not in content
    assert "docker.io" not in content
