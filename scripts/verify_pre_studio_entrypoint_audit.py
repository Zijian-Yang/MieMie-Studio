#!/usr/bin/env python3
"""Verify pre-studio entrypoint audit script contract."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "pre_studio_entrypoint_audit.py"


def run_dry_run(artifact: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    env = {
        **os.environ,
        "RUN_ID": "verify-pre-studio-entrypoint-audit",
        "ARTIFACT_DIR": str(artifact),
        "CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT": "dry-run",
    }
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT_DIR,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    status = json.loads((artifact / "status.json").read_text(encoding="utf-8"))
    return result, status


def main() -> int:
    py_compile.compile(str(SCRIPT), doraise=True)

    with tempfile.TemporaryDirectory(prefix="miemie-entrypoint-audit-") as temp_dir:
        temp = Path(temp_dir)
        result, status = run_dry_run(temp / "dry-run")
        if result.returncode != 0:
            raise AssertionError(f"dry-run failed: {result.returncode}\n{result.stdout}\n{result.stderr}")
        assert status["state"] == "dry_run"
        assert status["public_base_url"] == "https://pre-studio.miemie.co"
        plan = (temp / "dry-run" / "pre-studio-entrypoint-audit-plan.md").read_text(encoding="utf-8")
        assert "public `/api/health`" in plan
        assert "Cloudflare `HIT`" in plan
        assert "LOCAL_BASE_URL=http://127.0.0.1:18100" in plan

    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        "CONFIRM_PRE_STUDIO_ENTRYPOINT_AUDIT",
        "curl",
        "--noproxy",
        "public-health",
        "public-root",
        "public-static-first",
        "public-static-second",
        "cf-cache-status",
        "X-Request-ID",
        "X-Deployment-Version",
        "Cache-Control: no-store",
        "max-age",
        "immutable",
        "alt-svc advertises h3",
        "deployment_version_match",
        "responses.summary.json",
        "results.tsv",
        "body_sha256",
    ]
    for fragment in required_fragments:
        if fragment not in content:
            raise AssertionError(f"missing contract fragment: {fragment}")

    print("pre-studio entrypoint audit verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
