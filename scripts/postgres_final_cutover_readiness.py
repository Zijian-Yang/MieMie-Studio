#!/usr/bin/env python3
"""Generate a final PostgreSQL cutover readiness audit.

This audit does not mutate application data. It combines the domain coverage
report with the server-side staging scripts and highlights whether the current
automation is sufficient to leave JSON as a temporary archive/fallback rather
than the primary business-state store.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = (
    ROOT_DIR
    / "docs"
    / "reports"
    / "artifacts"
    / "2026-06-07-postgres-upgrade-rollout"
    / "r75-final-cutover-readiness"
)

COVERAGE_SCRIPT = ROOT_DIR / "scripts" / "postgres_domain_coverage.py"
LIVE_DATA_GATE_SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_live_data_gate.sh"
SEQUENCE_SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_video_task_sequence.sh"
SERVER_FALLBACK_SCRIPT = ROOT_DIR / "scripts" / "pre_studio_server_postgres_sequence.sh"
CANARY_SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_video_task_canary.sh"
ALL_DOMAIN_CANARY_SCRIPT = ROOT_DIR / "scripts" / "postgres_staging_all_domain_canary.sh"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def load_coverage_module() -> Any:
    spec = importlib.util.spec_from_file_location("postgres_domain_coverage", COVERAGE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {rel(COVERAGE_SCRIPT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def shell_default_value(script: str, variable: str) -> str:
    pattern = rf'^{re.escape(variable)}="\$\{{{re.escape(variable)}:-(.*?)\}}"'
    match = re.search(pattern, script, re.MULTILINE)
    if not match:
        return ""
    return match.group(1)


def shell_constant_value(script: str, variable: str) -> str:
    pattern = rf'^{re.escape(variable)}="([^"]*)"'
    match = re.search(pattern, script, re.MULTILINE)
    if not match:
        return ""
    return match.group(1)


def check_domain_coverage(run_id: str) -> dict[str, Any]:
    coverage = load_coverage_module()
    summary = coverage.build_summary(f"{run_id}-domain-coverage")
    expected_domains = [item["name"] for item in summary["migrated_domains"]]
    state = (
        "passed"
        if summary["state"] == "ready_for_staging_live_data_canary"
        and summary["pending_domain_count"] == 0
        and all(item["status"] == "covered" for item in summary["migrated_domains"])
        else "needs_work"
    )
    return {
        "name": "domain_coverage",
        "state": state,
        "expected_domains": expected_domains,
        "migrated_domain_count": summary["migrated_domain_count"],
        "pending_domain_count": summary["pending_domain_count"],
        "coverage_state": summary["state"],
        "source": rel(COVERAGE_SCRIPT),
    }


def check_live_data_gate_domains(expected_domains: list[str]) -> dict[str, Any]:
    script = read_text(LIVE_DATA_GATE_SCRIPT)
    domains = shell_default_value(script, "DOMAINS").split()
    missing = sorted(set(expected_domains) - set(domains))
    extra = sorted(set(domains) - set(expected_domains))
    return {
        "name": "live_data_gate_domains",
        "state": "passed" if not missing else "needs_work",
        "domains": domains,
        "missing_domains": missing,
        "extra_domains": extra,
        "source": rel(LIVE_DATA_GATE_SCRIPT),
    }


def check_staging_sequence_order() -> dict[str, Any]:
    script = read_text(SEQUENCE_SCRIPT)
    sequence = shell_default_value(script, "SEQUENCE").split()
    required = [
        "audit",
        "roll-runtime",
        "live-data-gate",
        "all-domain-dual-write-canary",
        "all-domain-read-switch-canary",
        "all-domain-rollback-read-switch",
        "all-domain-primary-write-canary",
        "all-domain-rollback-primary-write",
    ]
    missing = [stage for stage in required if stage not in sequence]
    live_index = sequence.index("live-data-gate") if "live-data-gate" in sequence else -1
    app_stage_indexes = [
        sequence.index(stage)
        for stage in [
            "all-domain-dual-write-canary",
            "all-domain-read-switch-canary",
            "all-domain-primary-write-canary",
        ]
        if stage in sequence
    ]
    ordered = live_index >= 0 and app_stage_indexes and all(live_index < index for index in app_stage_indexes)
    return {
        "name": "staging_sequence_order",
        "state": "passed" if not missing and ordered else "needs_work",
        "sequence": sequence,
        "missing_stages": missing,
        "live_data_gate_before_app_canaries": bool(ordered),
        "source": rel(SEQUENCE_SCRIPT),
    }


def check_server_fallback_contract() -> dict[str, Any]:
    script = read_text(SERVER_FALLBACK_SCRIPT)
    required_fragments = [
        "CONFIRM_STAGING_SEQUENCE=run",
        "verify_sequence_runner_contract",
        "live-data-gate",
        "git merge --ff-only",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in script]
    return {
        "name": "server_fallback_contract",
        "state": "passed" if not missing else "needs_work",
        "missing_fragments": missing,
        "source": rel(SERVER_FALLBACK_SCRIPT),
    }


def check_app_canary_domain_coverage(expected_domains: list[str]) -> dict[str, Any]:
    if ALL_DOMAIN_CANARY_SCRIPT.exists():
        script = read_text(ALL_DOMAIN_CANARY_SCRIPT)
        domains = shell_default_value(script, "ALL_DOMAINS").split()
        covered = [domain for domain in expected_domains if domain in domains]
        missing = sorted(set(expected_domains) - set(covered))
        return {
            "name": "app_canary_domain_coverage",
            "state": "passed" if not missing else "needs_work",
            "covered_domains": covered,
            "missing_domains": missing,
            "source": rel(ALL_DOMAIN_CANARY_SCRIPT),
            "note": (
                "The all-domain provider-free canary is present and covers every migrated domain "
                "declared by the domain coverage audit."
            ),
        }

    script = read_text(CANARY_SCRIPT)
    domain = shell_constant_value(script, "DOMAIN")
    covered = [domain] if domain else []
    missing = sorted(set(expected_domains) - set(covered))
    return {
        "name": "app_canary_domain_coverage",
        "state": "passed" if not missing else "needs_work",
        "covered_domains": covered,
        "missing_domains": missing,
        "source": rel(CANARY_SCRIPT),
        "note": (
            "The current app-level canary proves the video task path only. "
            "Final database-primary cutover needs provider-free smoke/canary coverage for every migrated domain."
        ),
    }


def build_summary(run_id: str) -> dict[str, Any]:
    domain_coverage = check_domain_coverage(run_id)
    expected_domains = list(domain_coverage["expected_domains"])
    checks = [
        domain_coverage,
        check_live_data_gate_domains(expected_domains),
        check_staging_sequence_order(),
        check_server_fallback_contract(),
        check_app_canary_domain_coverage(expected_domains),
    ]
    failed = [check for check in checks if check["state"] != "passed"]
    if not failed:
        state = "ready_for_final_cutover_sequence"
        next_step = "run_server_final_cutover_sequence"
    elif [check["name"] for check in failed] == ["app_canary_domain_coverage"]:
        state = "needs_all_domain_app_canary"
        next_step = "add_all_domain_app_canary"
    else:
        state = "needs_cutover_contract_fix"
        next_step = failed[0]["name"]
    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "state": state,
        "next_recommended_step": next_step,
        "expected_domains": expected_domains,
        "checks": checks,
        "notes": [
            "This audit is read-only and does not touch server containers or business data.",
            "A passed domain coverage audit is necessary but not sufficient for final JSON exit.",
            "Final cutover still requires live server execution evidence for live-data, app canaries, rollback, and post-cutover health/load gates.",
        ],
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def render_markdown(summary: dict[str, Any]) -> str:
    rows = [
        [
            f"`{check['name']}`",
            f"`{check['state']}`",
            f"`{check['source']}`",
        ]
        for check in summary["checks"]
    ]
    app_canary = next(
        check for check in summary["checks"] if check["name"] == "app_canary_domain_coverage"
    )
    missing = ", ".join(f"`{domain}`" for domain in app_canary["missing_domains"]) or "-"
    covered = ", ".join(f"`{domain}`" for domain in app_canary["covered_domains"]) or "-"
    domains = ", ".join(f"`{domain}`" for domain in summary["expected_domains"])
    if app_canary["missing_domains"]:
        app_canary_note = (
            "The current staging app-level canary is intentionally provider-free but only proves "
            "`video_studio_tasks`. Before final database-primary cutover, add an all-domain "
            "provider-free canary or smoke gate that exercises write/read/delete semantics for every migrated domain."
        )
    else:
        app_canary_note = (
            "The all-domain provider-free canary contract is present and covers every tracked migrated domain. "
            "Final cutover still requires server execution evidence for the live-data gate, all-domain canaries, "
            "rollback checks, and post-cutover health/load gates."
        )
    return "\n".join(
        [
            "# Final PostgreSQL Cutover Readiness Audit",
            "",
            f"Run ID: `{summary['run_id']}`",
            f"Updated At: `{summary['updated_at']}`",
            f"State: `{summary['state']}`",
            f"Next Recommended Step: `{summary['next_recommended_step']}`",
            "",
            "## Expected Domains",
            "",
            domains,
            "",
            "## Checks",
            "",
            markdown_table(["Check", "State", "Source"], rows),
            "",
            "## App Canary Coverage Gap",
            "",
            f"Covered domains: {covered}",
            "",
            f"Missing domains: {missing}",
            "",
            app_canary_note,
            "",
            "## Notes",
            "",
            *[f"- {note}" for note in summary["notes"]],
            "",
        ]
    )


def write_outputs(summary: dict[str, Any], artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "run_id": summary["run_id"],
        "state": summary["state"],
        "stage": "final-cutover-readiness",
        "next_recommended_step": summary["next_recommended_step"],
        "expected_domain_count": len(summary["expected_domains"]),
        "updated_at": summary["updated_at"],
        "artifact_dir": rel(artifact_dir),
    }
    (artifact_dir / "final-cutover-readiness.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "final-cutover-readiness.md").write_text(
        render_markdown(summary),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Directory for status and report artifacts.",
    )
    parser.add_argument(
        "--run-id",
        default="r75-final-cutover-readiness",
        help="Run identifier written into the generated report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = args.artifact_dir
    if not artifact_dir.is_absolute():
        artifact_dir = ROOT_DIR / artifact_dir
    summary = build_summary(args.run_id)
    write_outputs(summary, artifact_dir)
    print(f"postgres final cutover readiness: wrote {rel(artifact_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
