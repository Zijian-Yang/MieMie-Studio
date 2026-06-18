#!/usr/bin/env python3
"""Generate a final JSON exit audit for the PostgreSQL migration.

The audit is read-only. It answers whether the platform has enough evidence to
move from PostgreSQL-primary with JSON safety rails to a final runtime policy
where JSON is no longer the primary or fallback business-state store.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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
    / "r80-final-json-exit-audit"
)
READINESS_SCRIPT = ROOT_DIR / "scripts" / "postgres_final_cutover_readiness.py"

REQUIRED_SEQUENCE = [
    "audit",
    "roll-runtime",
    "live-data-gate",
    "all-domain-dual-write-canary",
    "all-domain-read-switch-canary",
    "all-domain-rollback-read-switch",
    "all-domain-primary-write-canary",
    "all-domain-rollback-primary-write",
]

FINAL_RUNTIME_EXPECTATIONS = {
    "MIEMIE_DATABASE_ENABLED": {"true", "1", "yes"},
    "MIEMIE_DATABASE_WRITE_MODE": {"postgres", "postgres_primary", "primary"},
    "MIEMIE_DATABASE_READ_MODE": {"postgres"},
    "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS": {""},
    "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS": {""},
    "MIEMIE_DATABASE_READ_DOMAINS": {""},
    "MIEMIE_DATABASE_JSON_FALLBACK_READ": {"false", "0", "no"},
    "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES": {"false", "0", "no"},
    "MIEMIE_DATABASE_RECONCILE_STRICT": {"true", "1", "yes"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def load_readiness_module() -> Any:
    spec = importlib.util.spec_from_file_location("postgres_final_cutover_readiness", READINESS_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {rel(READINESS_SCRIPT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_results_tsv(path: Path) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t")
        rows.append(dict(zip(headers, values)))
    return rows


def check_cutover_readiness(run_id: str) -> dict[str, Any]:
    readiness = load_readiness_module()
    summary = readiness.build_summary(f"{run_id}-cutover-readiness")
    return {
        "name": "cutover_readiness_contract",
        "state": "passed" if summary["state"] == "ready_for_final_cutover_sequence" else "needs_work",
        "readiness_state": summary["state"],
        "next_recommended_step": summary["next_recommended_step"],
        "source": rel(READINESS_SCRIPT),
        "expected_domains": summary["expected_domains"],
    }


def check_server_sequence_evidence(sequence_artifact_dir: Path | None) -> dict[str, Any]:
    if sequence_artifact_dir is None:
        return {
            "name": "server_sequence_evidence",
            "state": "needs_work",
            "reason": "missing --sequence-artifact-dir",
            "required_sequence": REQUIRED_SEQUENCE,
        }

    status_path = sequence_artifact_dir / "status.json"
    results_path = sequence_artifact_dir / "results.tsv"
    missing_files = [
        rel(path)
        for path in [status_path, results_path]
        if not path.exists()
    ]
    if missing_files:
        return {
            "name": "server_sequence_evidence",
            "state": "needs_work",
            "reason": "missing sequence artifact files",
            "missing_files": missing_files,
            "artifact_dir": rel(sequence_artifact_dir),
            "required_sequence": REQUIRED_SEQUENCE,
        }

    status = read_json(status_path)
    rows = parse_results_tsv(results_path)
    rows_by_mode = {row.get("mode", ""): row for row in rows}
    missing_stages = [stage for stage in REQUIRED_SEQUENCE if stage not in rows_by_mode]
    failed_stages = [
        {
            "mode": stage,
            "exit_code": rows_by_mode[stage].get("exit_code"),
            "state": rows_by_mode[stage].get("state"),
        }
        for stage in REQUIRED_SEQUENCE
        if stage in rows_by_mode
        and (rows_by_mode[stage].get("exit_code") != "0" or rows_by_mode[stage].get("state") != "passed")
    ]
    state = (
        "passed"
        if status.get("state") == "passed" and not missing_stages and not failed_stages
        else "needs_work"
    )
    return {
        "name": "server_sequence_evidence",
        "state": state,
        "status_state": status.get("state"),
        "artifact_dir": rel(sequence_artifact_dir),
        "required_sequence": REQUIRED_SEQUENCE,
        "missing_stages": missing_stages,
        "failed_stages": failed_stages,
    }


def check_final_runtime_policy(env_file: Path | None) -> dict[str, Any]:
    if env_file is None:
        return {
            "name": "final_runtime_policy",
            "state": "needs_work",
            "reason": "missing --env-file",
            "required_values": render_required_policy_values(),
        }
    if not env_file.exists():
        return {
            "name": "final_runtime_policy",
            "state": "needs_work",
            "reason": f"missing env file: {rel(env_file)}",
            "required_values": render_required_policy_values(),
        }

    values = parse_env_file(env_file)
    mismatches: list[dict[str, Any]] = []
    observed: dict[str, str] = {}
    for key, accepted in FINAL_RUNTIME_EXPECTATIONS.items():
        value = values.get(key, "")
        normalized = value.strip().lower()
        observed[key] = value
        if normalized not in accepted:
            mismatches.append(
                {
                    "key": key,
                    "observed": value,
                    "expected": sorted(accepted),
                }
            )
    return {
        "name": "final_runtime_policy",
        "state": "passed" if not mismatches else "needs_work",
        "env_file": rel(env_file),
        "mismatches": mismatches,
        "observed_safe_values": observed,
        "required_values": render_required_policy_values(),
    }


def render_required_policy_values() -> dict[str, str]:
    return {
        "MIEMIE_DATABASE_ENABLED": "true",
        "MIEMIE_DATABASE_WRITE_MODE": "postgres",
        "MIEMIE_DATABASE_READ_MODE": "postgres",
        "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS": "",
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS": "",
        "MIEMIE_DATABASE_READ_DOMAINS": "",
        "MIEMIE_DATABASE_JSON_FALLBACK_READ": "false",
        "MIEMIE_DATABASE_JSON_ARCHIVE_WRITES": "false",
        "MIEMIE_DATABASE_RECONCILE_STRICT": "true",
    }


def build_summary(
    run_id: str,
    sequence_artifact_dir: Path | None,
    env_file: Path | None,
) -> dict[str, Any]:
    readiness = check_cutover_readiness(run_id)
    expected_domains = list(readiness["expected_domains"])
    checks = [
        readiness,
        check_server_sequence_evidence(sequence_artifact_dir),
        check_final_runtime_policy(env_file),
    ]
    checks_by_name = {check["name"]: check for check in checks}

    if readiness["state"] != "passed":
        state = "needs_cutover_contract_fix"
        next_step = readiness["next_recommended_step"]
    elif checks_by_name["server_sequence_evidence"]["state"] != "passed":
        state = "needs_server_sequence_evidence"
        next_step = "run_server_final_cutover_sequence"
    elif checks_by_name["final_runtime_policy"]["state"] != "passed":
        state = "needs_final_runtime_policy"
        next_step = "apply_final_postgres_primary_runtime_policy"
    else:
        state = "ready_for_post_json_exit_validation"
        next_step = "run_post_json_exit_health_reconcile_and_load_gates"

    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "state": state,
        "next_recommended_step": next_step,
        "expected_domains": expected_domains,
        "final_runtime_policy": render_required_policy_values(),
        "checks": checks,
        "checks_by_name": checks_by_name,
        "notes": [
            "This audit is read-only and does not mutate compose.env, containers, PostgreSQL, or JSON data.",
            "ready_for_post_json_exit_validation is not the final done state; it means the post-exit health, reconcile, and load gates can run.",
            "Final JSON exit requires server sequence evidence, PostgreSQL read/write primary policy, JSON fallback disabled, and JSON archive writes disabled.",
        ],
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def render_markdown(summary: dict[str, Any]) -> str:
    check_rows = [
        [f"`{check['name']}`", f"`{check['state']}`"]
        for check in summary["checks"]
    ]
    policy_rows = [
        [f"`{key}`", f"`{value}`", f"`{key}={value}`"]
        for key, value in summary["final_runtime_policy"].items()
    ]
    domains = ", ".join(f"`{domain}`" for domain in summary["expected_domains"])
    return "\n".join(
        [
            "# Final PostgreSQL JSON Exit Audit",
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
            markdown_table(["Check", "State"], check_rows),
            "",
            "## Final Runtime Policy",
            "",
            markdown_table(["Variable", "Required Value", "Assignment"], policy_rows),
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
        "stage": "final-json-exit-audit",
        "next_recommended_step": summary["next_recommended_step"],
        "expected_domain_count": len(summary["expected_domains"]),
        "updated_at": summary["updated_at"],
        "artifact_dir": rel(artifact_dir),
    }
    (artifact_dir / "final-json-exit-audit.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "final-json-exit-audit.md").write_text(
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
        default="r80-final-json-exit-audit",
        help="Run identifier written into the generated report.",
    )
    parser.add_argument(
        "--sequence-artifact-dir",
        type=Path,
        default=None,
        help="Server sequence artifact directory containing status.json and results.tsv.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="compose.env or sanitized final env file to audit.",
    )
    return parser.parse_args()


def normalize_optional_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def main() -> int:
    args = parse_args()
    artifact_dir = args.artifact_dir if args.artifact_dir.is_absolute() else ROOT_DIR / args.artifact_dir
    summary = build_summary(
        args.run_id,
        normalize_optional_path(args.sequence_artifact_dir),
        normalize_optional_path(args.env_file),
    )
    write_outputs(summary, artifact_dir)
    print(f"postgres final JSON exit audit: wrote {rel(artifact_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
