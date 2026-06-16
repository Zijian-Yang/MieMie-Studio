#!/usr/bin/env python3
"""Verify the pre-studio connectivity preflight script without network access."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "pre_studio_connectivity_preflight.sh"


def run_shell_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)


def run_dry_run_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-preflight-verify-") as temp_dir:
        temp = Path(temp_dir)
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "RUN_ID": "verify-connectivity-preflight",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
            "MIEMIE_PREFLIGHT_DRY_RUN": "true",
            "HTTP_PROXY": "http://user:password@example.invalid:8080",
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"expected dry-run to exit 0, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")
        commands = (artifact_dir / "commands.log").read_text(encoding="utf-8")
        proxy_env = (artifact_dir / "proxy-env.sanitized").read_text(encoding="utf-8")
        remediation = (artifact_dir / "remediation.md").read_text(encoding="utf-8")

        assert status["state"] == "dry_run"
        assert status["stage"] == "planned"
        assert "set MIEMIE_PREFLIGHT_DRY_RUN=false" in status["reason"]
        assert status["remediation_file"].endswith("remediation.md")
        assert "dry_run\tpassed\tno network checks executed" in results
        assert "HTTP_PROXY=<set>" in proxy_env
        assert "password" not in proxy_env
        assert "Dry run only" in remediation
        if re.search(r"\b(ssh|curl|dig|route|nc)\b", commands):
            raise AssertionError(f"dry-run executed network command unexpectedly:\n{commands}")


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'HOST="${HOST:-pre-studio.miemie.co}"',
        'ORIGIN_IP="${ORIGIN_IP:-47.79.99.190}"',
        "proxy-env.sanitized",
        "198\\.18\\.|198\\.19\\.",
        "interface:[[:space:]]*utun",
        "gateway:[[:space:]]*198\\.18\\.",
        "nc -vz",
        "ssh -o BatchMode=yes",
        'curl --noproxy "*"',
        "x-request-id:",
        "x-deployment-version:",
        "remediation.md",
        "DNS is returning a Clash fake-IP",
        "Do not run the remote PostgreSQL sequence",
        '"blocked" "connectivity"',
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing safety fragment: {fragment}")


def main() -> int:
    run_shell_syntax_check()
    run_dry_run_contract()
    check_safety_contract()
    print("pre-studio connectivity preflight verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
