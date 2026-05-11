from pathlib import Path


def test_run_sh_test_uses_project_virtualenv():
    """./run.sh test 应使用项目 venv，而不是系统 Python。"""
    repo_root = Path(__file__).resolve().parents[2]
    run_sh = repo_root / "run.sh"
    content = run_sh.read_text(encoding="utf-8")
    start = content.index("run_tests() {")
    end = content.index("\n}", start) + 2
    run_tests_body = content[start:end]

    assert "install_backend_deps" in run_tests_body
    assert 'PYTHON="$VENV_DIR/bin/python"' in run_tests_body
    assert '"$PYTHON" -m pytest tests/ -v' in run_tests_body
