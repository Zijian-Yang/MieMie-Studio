#!/usr/bin/env python3
"""Exercise the self-hosted lifecycle state machine with isolated fake commands."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "miemie"
LIBRARY = ROOT / "scripts" / "miemie_lib.sh"
OLD_COMMIT = "a" * 40
NEW_COMMIT = "b" * 40


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def fixture(temp: Path) -> tuple[dict[str, str], Path, Path, Path]:
    install = temp / "install"
    fake_bin = temp / "bin"
    state = temp / "state"
    for directory in (
        install / "backend/data",
        install / "backend/logs",
        install / "backups/postgres",
        install / "scripts",
        temp / "installed-bin",
        fake_bin,
        state,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "scripts/postgres_restore_rehearsal.sh", install / "scripts")
    shutil.copy(ROOT / "scripts/miemie", install / "scripts")
    (install / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (install / "compose.env").write_text(
        "MIEMIE_HOST_PORT=18100\n"
        f"MIEMIE_RUNTIME_UID={os.getuid()}\n"
        f"MIEMIE_RUNTIME_GID={os.getgid()}\n"
        "MIEMIE_POSTGRES_DB=miemie\n"
        "MIEMIE_IMAGE=miemie-studio:pre-aaaaaaaaaaaa\n"
        f"MIEMIE_RUNTIME_GIT_COMMIT={OLD_COMMIT}\n",
        encoding="utf-8",
    )
    config = temp / "miemie.conf"
    config.write_text(
        f"MIEMIE_INSTALL_ROOT={install}\n"
        "MIEMIE_PROJECT_NAME=verify-lifecycle\n"
        f"MIEMIE_ENV_FILE={install / 'compose.env'}\n"
        f"MIEMIE_RELEASE_STATE_DIR={state}\n",
        encoding="utf-8",
    )
    (state / "current.env").write_text(
        f"commit={OLD_COMMIT}\n"
        "image=miemie-studio:pre-aaaaaaaaaaaa\n"
        f"previous_commit={'c' * 40}\n"
        "previous_image=miemie-studio:pre-cccccccccccc\n"
        "state=healthy\n",
        encoding="utf-8",
    )
    calls = temp / "calls.log"
    source = install / "backups/postgres/source.dump"
    source.write_bytes(b"PGDMP lifecycle fixture")
    (source.with_suffix(".dump.sha256")).write_text(
        hashlib.sha256(source.read_bytes()).hexdigest() + "  source.dump\n",
        encoding="utf-8",
    )
    safety = install / "backups/postgres/safety.dump"
    safety.write_bytes(b"PGDMP safety fixture")
    checksum = hashlib.sha256(safety.read_bytes()).hexdigest()
    safety.with_name(safety.name + ".sha256").write_text(
        f"{checksum}  {safety.name}\n", encoding="ascii"
    )

    write_executable(
        fake_bin / "git",
        """#!/bin/sh
printf 'git %s\n' "$*" >> "$MIEMIE_VERIFY_CALLS"
case "$*" in
  'status --porcelain --untracked-files=no') [ "${MIEMIE_GIT_DIRTY:-false}" = true ] && echo ' M tracked' ;;
  'rev-parse HEAD') echo "$MIEMIE_OLD_COMMIT" ;;
  'rev-parse origin/pre') echo "$MIEMIE_NEW_COMMIT" ;;
  'merge-base --is-ancestor '*) [ "${MIEMIE_NON_FF:-false}" = true ] && exit 1 || exit 0 ;;
  'switch --detach '*) exit 0 ;;
  'cat-file -e '*) exit 0 ;;
esac
""",
    )
    write_executable(
        fake_bin / "docker",
        """#!/bin/sh
printf 'docker %s\n' "$*" >> "$MIEMIE_VERIFY_CALLS"
case "$*" in
  *"${MIEMIE_FAIL_MATCH:-__never__}"*) exit 1 ;;
  *'run --rm -T worker-ops python -'*) printf '%s\t%s\t%s\n' 'backup-run' 'postgres/safety.dump' "$MIEMIE_SAFETY_SHA" ;;
  *'ps --status running -q '*) echo 'container-id' ;;
  *'select version_num from alembic_version'*) echo '20260812_0011' ;;
esac
exit 0
""",
    )
    write_executable(
        fake_bin / "curl",
        """#!/bin/sh
printf 'curl %s\n' "$*" >> "$MIEMIE_VERIFY_CALLS"
[ "${MIEMIE_HEALTH_FAIL:-false}" = true ] && exit 1
printf '%s\n' '{"status":"ok"}'
""",
    )
    write_executable(fake_bin / "timeout", "#!/bin/sh\nshift\nexec \"$@\"\n")
    write_executable(fake_bin / "flock", "#!/bin/sh\nexit 0\n")
    write_executable(fake_bin / "sleep", "#!/bin/sh\nexit 0\n")
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MIEMIE_CONFIG_FILE": str(config),
        "MIEMIE_ALLOW_NON_ROOT": "true",
        "MIEMIE_VERIFY_CALLS": str(calls),
        "MIEMIE_OLD_COMMIT": OLD_COMMIT,
        "MIEMIE_NEW_COMMIT": NEW_COMMIT,
        "MIEMIE_SAFETY_SHA": checksum,
        "MIEMIE_HEALTH_ATTEMPTS": "1",
        "MIEMIE_INSTALL_BIN_DIR": str(temp / "installed-bin"),
    }
    return env, calls, install, state


def run_cli(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CLI), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_update_guards_and_success() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-lifecycle-update-") as raw:
        env, calls, install, state = fixture(Path(raw))
        result = run_cli({**env, "MIEMIE_GIT_DIRTY": "true"}, "update", "--check")
        assert result.returncode == 2 and "dirty" in result.stderr
        result = run_cli({**env, "MIEMIE_NON_FF": "true"}, "update", "--check")
        assert result.returncode == 2 and "fast-forward" in result.stderr
        result = run_cli(env, "update", "--apply")
        assert result.returncode == 0, result.stdout + result.stderr
        current = (state / "current.env").read_text(encoding="utf-8")
        assert f"commit={NEW_COMMIT}" in current and "state=healthy" in current
        assert (Path(env["MIEMIE_INSTALL_BIN_DIR"]) / "miemie").exists()
        assert "MIEMIE_IMAGE=miemie-studio:pre-bbbbbbbbbbbb" in (install / "compose.env").read_text()
        log = calls.read_text(encoding="utf-8")
        assert "build migrate api worker worker-video worker-ops scheduler" in log
        assert "run --rm -T migrate" in log


def test_update_failures_restore_application_release() -> None:
    for failure in (
        "run --rm -T worker-ops python -",
        "build migrate api",
        "run --rm -T migrate",
    ):
        with tempfile.TemporaryDirectory(prefix="miemie-lifecycle-failure-") as raw:
            env, calls, install, state = fixture(Path(raw))
            result = run_cli({**env, "MIEMIE_FAIL_MATCH": failure}, "update", "--apply")
            assert result.returncode != 0, failure
            if "worker-ops" not in failure:
                values = (install / "compose.env").read_text(encoding="utf-8")
                assert "MIEMIE_IMAGE=miemie-studio:pre-aaaaaaaaaaaa" in values
                assert f"MIEMIE_RUNTIME_GIT_COMMIT={OLD_COMMIT}" in values
                assert f"git switch --detach {OLD_COMMIT}" in calls.read_text()
                assert "state=rolled_back" in next(state.glob("release-*.env")).read_text()

    with tempfile.TemporaryDirectory(prefix="miemie-lifecycle-health-") as raw:
        env, _calls, install, _state = fixture(Path(raw))
        result = run_cli({**env, "MIEMIE_HEALTH_FAIL": "true"}, "update", "--apply")
        assert result.returncode != 0
        assert "application_rollback" in result.stderr
        assert "MIEMIE_IMAGE=miemie-studio:pre-aaaaaaaaaaaa" in (install / "compose.env").read_text()


def test_rollback_restore_and_purge_contracts() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-lifecycle-restore-") as raw:
        env, calls, install, _state = fixture(Path(raw))
        result = run_cli({**env, "MIEMIE_LIFECYCLE_DRY_RUN": "true"}, "rollback")
        assert result.returncode == 0 and "schema_forward_only" in result.stdout

        result = run_cli(env, "rollback")
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"commit={'c' * 40}" in (_state / "current.env").read_text()

        env, calls, install, _state = fixture(Path(raw) / "failed-rollback")
        result = run_cli({**env, "MIEMIE_HEALTH_FAIL": "true"}, "rollback")
        assert result.returncode != 0
        assert "restore_pre_rollback_release" in result.stderr
        values = (install / "compose.env").read_text(encoding="utf-8")
        assert "MIEMIE_IMAGE=miemie-studio:pre-aaaaaaaaaaaa" in values

        env, _calls, install, _state = fixture(Path(raw) / "failed-rollback-up")
        result = run_cli(
            {**env, "MIEMIE_FAIL_MATCH": "up -d --no-build"}, "rollback"
        )
        assert result.returncode != 0
        values = (install / "compose.env").read_text(encoding="utf-8")
        assert "MIEMIE_IMAGE=miemie-studio:pre-aaaaaaaaaaaa" in values

        env, calls, install, _state = fixture(Path(raw) / "restore")
        backup = install / "backups/postgres/source.dump"
        confirmation = {
            **env,
            "MIEMIE_RESTORE_CONFIRM_BACKUP": backup.name,
            "MIEMIE_RESTORE_CONFIRM_PHRASE": "RESTORE MIEMIE DATABASE",
            "MIEMIE_LIFECYCLE_DRY_RUN": "true",
        }
        result = run_cli(confirmation, "restore", "postgres/source.dump")
        assert result.returncode == 0 and "isolated_rehearsal" in result.stdout
        result = run_cli(
            {**confirmation, "MIEMIE_RESTORE_CONFIRM_PHRASE": "WRONG"},
            "restore",
            "postgres/source.dump",
        )
        assert result.returncode == 2 and "confirmation mismatch" in result.stderr

        result = run_cli(
            {
                **env,
                "MIEMIE_RESTORE_CONFIRM_BACKUP": backup.name,
                "MIEMIE_RESTORE_CONFIRM_PHRASE": "RESTORE MIEMIE DATABASE",
                "MIEMIE_FAIL_MATCH": "pg_restore --exit-on-error",
            },
            "restore",
            "postgres/source.dump",
        )
        assert result.returncode != 0
        assert "stop api worker" not in calls.read_text(encoding="utf-8")

        calls.write_text("", encoding="utf-8")
        result = run_cli(
            {
                **env,
                "MIEMIE_RESTORE_CONFIRM_BACKUP": backup.name,
                "MIEMIE_RESTORE_CONFIRM_PHRASE": "RESTORE MIEMIE DATABASE",
            },
            "restore",
            "postgres/source.dump",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        log = calls.read_text(encoding="utf-8")
        assert "run --rm -T worker-ops python -" in log
        assert "stop api worker worker-video worker-ops scheduler" in log
        assert log.index("run --rm -T worker-ops python -") < log.index("stop api worker")

        result = run_cli(
            {
                **env,
                "MIEMIE_PURGE_CONFIRMATION": "DELETE MIEMIE DATA",
                "MIEMIE_LIFECYCLE_DRY_RUN": "true",
            },
            "uninstall",
            "--purge",
        )
        assert result.returncode == 0 and "state=dry_run" in result.stdout
        result = run_cli(
            {**env, "MIEMIE_PURGE_CONFIRMATION": "WRONG"}, "uninstall", "--purge"
        )
        assert result.returncode == 2 and "confirmation mismatch" in result.stderr


def check_static_safety_contract() -> None:
    source = CLI.read_text(encoding="utf-8") + LIBRARY.read_text(encoding="utf-8")
    for fragment in (
        "git merge-base --is-ancestor",
        "status --porcelain --untracked-files=no",
        "miemie_create_backup",
        "miemie_write_release_manifest",
        '"rolled_back"',
        "database schema is forward-only",
        "postgres_restore_rehearsal.sh",
        "miemie_confirm_restore",
        "miemie_confirm_purge",
        "DELETE MIEMIE DATA",
        "readlink -f",
    ):
        assert fragment in source, fragment
    for forbidden in ("git reset --hard", "docker system prune", "eval "):
        assert forbidden not in source, forbidden


def main() -> int:
    for script in (CLI, LIBRARY):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    test_update_guards_and_success()
    test_update_failures_restore_application_release()
    test_rollback_restore_and_purge_contracts()
    check_static_safety_contract()
    print("miemie lifecycle verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
