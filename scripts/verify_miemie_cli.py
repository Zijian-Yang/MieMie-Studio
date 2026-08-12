#!/usr/bin/env python3
"""Verify the host operator CLI contract with fake Docker and curl commands."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "miemie"
LIBRARY = ROOT / "scripts" / "miemie_lib.sh"


def main() -> int:
    for script in (CLI, LIBRARY):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    with tempfile.TemporaryDirectory(prefix="miemie-cli-") as temp_dir:
        temp = Path(temp_dir)
        root = temp / "install"
        fake_bin = temp / "bin"
        fake_bin.mkdir()
        root.mkdir()
        (root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (root / "compose.env").write_text("MIEMIE_HOST_PORT=18100\n", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "deploy_doctor.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        config = temp / "miemie.conf"
        state = temp / "state"
        state.mkdir()
        config.write_text(
            f"MIEMIE_INSTALL_ROOT={root}\n"
            "MIEMIE_PROJECT_NAME=verify-miemie\n"
            f"MIEMIE_ENV_FILE={root / 'compose.env'}\n"
            f"MIEMIE_RELEASE_STATE_DIR={state}\n",
            encoding="utf-8",
        )
        calls = temp / "calls.log"
        (fake_bin / "docker").write_text(
            "#!/bin/sh\nprintf 'docker %s\\n' \"$*\" >> \"$MIEMIE_VERIFY_CALLS\"\n"
            "case \"$*\" in *'ps --format json'*) printf '%s\\n' '{\"Service\":\"api\",\"State\":\"running\",\"Health\":\"healthy\"}' ;; esac\n",
            encoding="utf-8",
        )
        (fake_bin / "curl").write_text(
            "#!/bin/sh\nprintf 'curl %s\\n' \"$*\" >> \"$MIEMIE_VERIFY_CALLS\"\nprintf '%s\\n' '{\"status\":\"ok\",\"database\":{\"ok\":true},\"redis\":{\"ok\":true}}'\n",
            encoding="utf-8",
        )
        (fake_bin / "flock").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        for path in fake_bin.iterdir():
            path.chmod(0o755)
        env = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "MIEMIE_CONFIG_FILE": str(config),
            "MIEMIE_VERIFY_CALLS": str(calls),
            "MIEMIE_ALLOW_NON_ROOT": "true",
        }
        for args in (
            ["status"],
            ["restart", "worker"],
            ["logs", "api"],
            ["doctor"],
            ["uninstall"],
        ):
            result = subprocess.run(
                ["bash", str(CLI), *args], env=env, capture_output=True, text=True
            )
            assert result.returncode == 0, f"{args}: {result.stdout}\n{result.stderr}"
        call_log = calls.read_text(encoding="utf-8")
        assert "--env-file" in call_log
        assert "restart worker" in call_log
        assert "logs --tail=200 api" in call_log
        assert "stop" in call_log
        assert " down -v" not in call_log

    source = CLI.read_text(encoding="utf-8") + LIBRARY.read_text(encoding="utf-8")
    for fragment in (
        "flock",
        "status) cmd_status",
        "update|rollback|restore)",
        "app.cli.admin",
        "app.services.platform_operations",
        "build_ops_runner",
        "MIEMIE_ADMIN_PASSWORD",
        "deploy_doctor.sh",
        "no-new-privileges",
    ):
        assert fragment in source, fragment
    for forbidden in ("set -x", "docker system prune", "git reset --hard"):
        assert forbidden not in source
    print("miemie CLI verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
