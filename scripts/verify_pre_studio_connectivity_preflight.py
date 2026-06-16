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


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_network_scope_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-preflight-network-") as temp_dir:
        temp = Path(temp_dir)
        bin_dir = temp / "bin"
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        bin_dir.mkdir()

        write_executable(
            bin_dir / "dig",
            "#!/usr/bin/env bash\nprintf '%s\\n' 104.21.85.29 172.67.201.59\n",
        )
        write_executable(
            bin_dir / "route",
            "#!/usr/bin/env bash\n"
            "cat <<'OUT'\n"
            "   route to: 47.79.99.190\n"
            "destination: default\n"
            "    gateway: 192.168.50.1\n"
            "  interface: en0\n"
            "OUT\n",
        )
        for forbidden in ("nc", "ssh", "curl"):
            write_executable(
                bin_dir / forbidden,
                f"#!/usr/bin/env bash\necho '{forbidden} should not run in network scope' >&2\nexit 99\n",
            )

        env = {
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')}",
            "RUN_ID": "verify-network-scope",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
            "MIEMIE_PREFLIGHT_SCOPE": "network",
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
                f"expected network scope to exit 0, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")
        remediation = (artifact_dir / "remediation.md").read_text(encoding="utf-8")

        assert status["state"] == "passed"
        assert status["stage"] == "network"
        assert status["scope"] == "network"
        assert "scope\tpassed\tnetwork" in results
        assert "dns\tpassed\t104.21.85.29 172.67.201.59" in results
        assert "route\tpassed" in results
        assert "tcp_ssh" not in results
        assert "ssh_banner" not in results
        assert "public_health" not in results
        assert "Network-only checks are clear" in remediation


def run_tun_route_remediation_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="miemie-preflight-tun-") as temp_dir:
        temp = Path(temp_dir)
        bin_dir = temp / "bin"
        artifact_dir = temp / "artifact"
        tmp_dir = temp / "tmp"
        bin_dir.mkdir()

        write_executable(
            bin_dir / "dig",
            "#!/usr/bin/env bash\nprintf '%s\\n' 104.21.85.29 172.67.201.59\n",
        )
        write_executable(
            bin_dir / "route",
            "#!/usr/bin/env bash\n"
            "cat <<'OUT'\n"
            "   route to: 47.79.99.190\n"
            "destination: 32.0.0.0\n"
            "       mask: 224.0.0.0\n"
            "    gateway: 198.18.0.1\n"
            "  interface: utun1024\n"
            "OUT\n",
        )
        for forbidden in ("nc", "ssh", "curl"):
            write_executable(
                bin_dir / forbidden,
                f"#!/usr/bin/env bash\necho '{forbidden} should not run in network scope' >&2\nexit 99\n",
            )

        env = {
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')}",
            "RUN_ID": "verify-tun-route-remediation",
            "ARTIFACT_DIR": str(artifact_dir),
            "TMP_DIR": str(tmp_dir),
            "MIEMIE_PREFLIGHT_SCOPE": "network",
        }
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 2:
            raise AssertionError(
                f"expected network scope to exit 2, got {result.returncode}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        status = json.loads((artifact_dir / "status.json").read_text(encoding="utf-8"))
        results = (artifact_dir / "results.tsv").read_text(encoding="utf-8")
        remediation = (artifact_dir / "remediation.md").read_text(encoding="utf-8")

        assert status["state"] == "blocked"
        assert status["stage"] == "network"
        assert "route\tblocked\tTUN/fake-ip route detected" in results
        assert "32.0.0.0/3" in remediation
        assert "IP-CIDR,47.79.99.190/32,DIRECT,no-resolve" in remediation
        assert "Rule Providers" in remediation


def check_safety_contract() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        'HOST="${HOST:-pre-studio.miemie.co}"',
        'ORIGIN_IP="${ORIGIN_IP:-47.79.99.190}"',
        'MIEMIE_PREFLIGHT_SCOPE="${MIEMIE_PREFLIGHT_SCOPE:-full}"',
        '"network" "$failures network check(s) failed or blocked"',
        "proxy-env.sanitized",
        "198\\.18\\.|198\\.19\\.",
        "interface:[[:space:]]*utun",
        "gateway:[[:space:]]*198\\.18\\.",
        "IP-CIDR,%s/32,DIRECT,no-resolve",
        "32.0.0.0/3",
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
    run_network_scope_contract()
    run_tun_route_remediation_contract()
    check_safety_contract()
    print("pre-studio connectivity preflight verifier: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
