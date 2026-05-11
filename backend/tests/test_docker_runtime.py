from pathlib import Path


def test_dockerfile_runs_gunicorn_without_login_shell_path_reset():
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert '"sh", "-c"' in content
    assert '"sh", "-lc"' not in content
    assert "exec /opt/venv/bin/gunicorn app.main:app" in content
