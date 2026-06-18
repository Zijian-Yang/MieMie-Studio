#!/usr/bin/env python3
"""Audit whether final JSON exit is actually complete.

This is a read-only evidence audit. It intentionally runs after the server final
exit sequence and refuses to treat dry-run plans or partial gates as completion.
"""

from __future__ import annotations

import argparse
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
    / "r86-final-exit-completion-audit"
)


REQUIRED_STATUS_PATHS = {
    "server_final_exit_status": "status.json",
    "server_sequence_wrapper": "server-sequence/status.json",
    "server_sequence_inner": "server-sequence/sequence/status.json",
    "apply_final_policy": "apply-final-json-exit-policy/status.json",
    "apply_final_policy_audit": "apply-final-json-exit-policy/final-json-exit-audit/status.json",
    "post_json_exit_validation": "post-json-exit-validation/status.json",
    "post_validation_audit": "post-json-exit-validation/final-json-exit-audit/status.json",
}

EXPECTED_STATES = {
    "server_final_exit_status": "passed",
    "server_sequence_wrapper": "passed",
    "server_sequence_inner": "passed",
    "apply_final_policy": "passed",
    "apply_final_policy_audit": "ready_for_post_json_exit_validation",
    "post_json_exit_validation": "passed",
    "post_validation_audit": "ready_for_post_json_exit_validation",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_status_file(final_exit_artifact_dir: Path | None, name: str, relative_path: str) -> dict[str, Any]:
    if final_exit_artifact_dir is None:
        return {
            "name": name,
            "state": "needs_work",
            "reason": "missing --final-exit-artifact-dir",
            "relative_path": relative_path,
            "expected_state": EXPECTED_STATES[name],
        }

    path = final_exit_artifact_dir / relative_path
    if not path.exists():
        return {
            "name": name,
            "state": "needs_work",
            "reason": "missing status file",
            "path": rel(path),
            "expected_state": EXPECTED_STATES[name],
        }

    status = read_json(path)
    observed_state = str(status.get("state", ""))
    expected_state = EXPECTED_STATES[name]
    return {
        "name": name,
        "state": "passed" if observed_state == expected_state else "needs_work",
        "path": rel(path),
        "observed_state": observed_state,
        "expected_state": expected_state,
        "stage": status.get("stage", ""),
        "reason": status.get("reason", ""),
    }


def check_rollback_not_triggered(final_exit_artifact_dir: Path | None) -> dict[str, Any]:
    if final_exit_artifact_dir is None:
        return {
            "name": "rollback_not_triggered",
            "state": "needs_work",
            "reason": "missing --final-exit-artifact-dir",
        }

    rollback_status = final_exit_artifact_dir / "rollback-final-json-exit-policy" / "status.json"
    if not rollback_status.exists():
        return {
            "name": "rollback_not_triggered",
            "state": "passed",
            "reason": "no rollback status artifact found",
        }

    status = read_json(rollback_status)
    observed_state = str(status.get("state", ""))
    if observed_state == "dry_run":
        state = "passed"
        reason = "rollback artifact is dry-run only"
    elif observed_state == "passed":
        state = "failed"
        reason = "rollback passed after final exit attempt"
    else:
        state = "needs_work"
        reason = f"rollback artifact state is {observed_state}"

    return {
        "name": "rollback_not_triggered",
        "state": state,
        "reason": reason,
        "path": rel(rollback_status),
        "observed_state": observed_state,
    }


def build_summary(run_id: str, final_exit_artifact_dir: Path | None) -> dict[str, Any]:
    checks = [
        check_status_file(final_exit_artifact_dir, name, relative_path)
        for name, relative_path in REQUIRED_STATUS_PATHS.items()
    ]
    checks.append(check_rollback_not_triggered(final_exit_artifact_dir))
    checks_by_name = {check["name"]: check for check in checks}

    if any(check["state"] == "failed" for check in checks):
        state = "rolled_back_after_final_exit_attempt"
        next_step = "diagnose_final_exit_failure_before_retry"
    elif any(check["state"] != "passed" for check in checks):
        state = "needs_final_exit_evidence"
        next_step = "run_server_final_exit_sequence"
    else:
        state = "postgres_only_complete"
        next_step = "archive_json_and_monitor_postgres_runtime"

    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "state": state,
        "next_recommended_step": next_step,
        "final_exit_artifact_dir": rel(final_exit_artifact_dir) if final_exit_artifact_dir else "",
        "checks": checks,
        "checks_by_name": checks_by_name,
        "completion_requirements": [
            "server final exit sequence status is passed",
            "server staging sequence wrapper and inner sequence are passed",
            "final PostgreSQL-only policy application is passed",
            "final JSON exit audit is ready_for_post_json_exit_validation before and during post validation",
            "post JSON exit validation is passed",
            "rollback did not pass after the final exit attempt",
        ],
        "notes": [
            "This audit is read-only and never mutates compose.env, PostgreSQL, JSON files, or containers.",
            "postgres_only_complete means runtime evidence says JSON is no longer primary or fallback business-state storage.",
            "It does not delete historical JSON files; archival/deletion is a separate operator action after monitoring.",
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
            f"`{check.get('observed_state', '')}`",
            check.get("reason", ""),
        ]
        for check in summary["checks"]
    ]
    requirements = "\n".join(f"- {item}" for item in summary["completion_requirements"])
    notes = "\n".join(f"- {item}" for item in summary["notes"])
    return f"""# PostgreSQL Final Exit Completion Audit

- Run ID: `{summary['run_id']}`
- State: `{summary['state']}`
- Next recommended step: `{summary['next_recommended_step']}`
- Final exit artifact dir: `{summary['final_exit_artifact_dir']}`

## Checks

{markdown_table(["Check", "State", "Observed", "Reason"], rows)}

## Completion Requirements

{requirements}

## Notes

{notes}
"""


def write_outputs(summary: dict[str, Any], artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "final-exit-completion.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "final-exit-completion.md").write_text(
        render_markdown(summary),
        encoding="utf-8",
    )
    (artifact_dir / "status.json").write_text(
        json.dumps(
            {
                "run_id": summary["run_id"],
                "state": summary["state"],
                "next_recommended_step": summary["next_recommended_step"],
                "artifact_dir": rel(artifact_dir),
                "final_exit_artifact_dir": summary["final_exit_artifact_dir"],
                "updated_at": summary["updated_at"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-exit-artifact-dir", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--run-id", default="postgres-final-exit-completion-audit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(args.run_id, args.final_exit_artifact_dir)
    write_outputs(summary, args.artifact_dir)
    print(f"final exit completion audit state: {summary['state']}")
    print(f"next recommended step: {summary['next_recommended_step']}")
    print(f"artifact dir: {rel(args.artifact_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
