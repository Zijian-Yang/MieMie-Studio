#!/usr/bin/env python3
"""Generate a PostgreSQL migration domain coverage audit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = (
    ROOT_DIR
    / "docs"
    / "reports"
    / "artifacts"
    / "2026-06-07-postgres-upgrade-rollout"
    / "r67-postgres-domain-coverage"
)

MIGRATED_DOMAINS = [
    {
        "name": "video_studio_tasks",
        "summary": "Video generation task state.",
        "expected_files": [
            "backend/app/db/schema/video_studio_tasks.py",
            "backend/app/repositories/video_studio_tasks.py",
            "backend/app/repositories/video_studio_task_runtime.py",
            "backend/app/services/migration/backfill_video_studio_tasks.py",
            "backend/app/services/migration/reconcile_video_studio_tasks.py",
            "scripts/postgres_backfill_video_studio_tasks.py",
            "scripts/postgres_reconcile_video_studio_tasks.py",
        ],
    },
    {
        "name": "studio_tasks",
        "summary": "Image studio task state.",
        "expected_files": [
            "backend/app/db/schema/studio_tasks.py",
            "backend/app/repositories/studio_tasks.py",
            "backend/app/repositories/studio_task_runtime.py",
            "backend/app/services/migration/backfill_studio_tasks.py",
            "backend/app/services/migration/reconcile_studio_tasks.py",
            "scripts/postgres_backfill_studio_tasks.py",
            "scripts/postgres_reconcile_studio_tasks.py",
        ],
    },
    {
        "name": "projects",
        "summary": "Project metadata, script snapshot, and project-level counters.",
        "expected_files": [
            "backend/app/db/schema/projects.py",
            "backend/app/repositories/projects.py",
            "backend/app/repositories/project_runtime.py",
            "backend/app/services/migration/backfill_projects.py",
            "backend/app/services/migration/reconcile_projects.py",
            "scripts/postgres_backfill_projects.py",
            "scripts/postgres_reconcile_projects.py",
        ],
    },
    {
        "name": "media_metadata",
        "summary": "Generated media metadata and project media references.",
        "expected_files": [
            "backend/app/db/schema/media_assets.py",
            "backend/app/repositories/media_assets.py",
            "backend/app/repositories/media_asset_runtime.py",
            "backend/app/services/migration/backfill_media_metadata.py",
            "backend/app/services/migration/reconcile_media_metadata.py",
            "scripts/postgres_backfill_media_metadata.py",
            "scripts/postgres_reconcile_media_metadata.py",
        ],
    },
    {
        "name": "project_entities",
        "summary": "Characters, scenes, props, frames, videos, styles, and gallery-like project entities.",
        "expected_files": [
            "backend/app/db/schema/project_entities.py",
            "backend/app/repositories/project_entities.py",
            "backend/app/repositories/project_entity_runtime.py",
            "backend/app/services/migration/backfill_project_entities.py",
            "backend/app/services/migration/reconcile_project_entities.py",
            "scripts/postgres_backfill_project_entities.py",
            "scripts/postgres_reconcile_project_entities.py",
        ],
    },
    {
        "name": "benchmark_records",
        "summary": "Image/video benchmark suite, run, and result records.",
        "expected_files": [
            "backend/app/db/schema/benchmark_records.py",
            "backend/app/repositories/benchmark_records.py",
            "backend/app/repositories/benchmark_record_runtime.py",
            "backend/app/services/migration/backfill_benchmark_records.py",
            "backend/app/services/migration/reconcile_benchmark_records.py",
            "scripts/postgres_backfill_benchmark_records.py",
            "scripts/postgres_reconcile_benchmark_records.py",
        ],
    },
    {
        "name": "user_config",
        "summary": "User account and per-user configuration state.",
        "expected_files": [
            "backend/app/db/schema/user_config.py",
            "backend/app/repositories/user_config.py",
            "backend/app/repositories/user_config_runtime.py",
            "backend/app/services/migration/backfill_user_config.py",
            "backend/app/services/migration/reconcile_user_config.py",
            "scripts/postgres_backfill_user_config.py",
            "scripts/postgres_reconcile_user_config.py",
        ],
    },
    {
        "name": "sessions",
        "summary": "Session metadata with token hashes only.",
        "expected_files": [
            "backend/app/db/schema/sessions.py",
            "backend/app/repositories/sessions.py",
            "backend/app/repositories/session_runtime.py",
            "backend/app/services/migration/backfill_sessions.py",
            "backend/app/services/migration/reconcile_sessions.py",
            "scripts/postgres_backfill_sessions.py",
            "scripts/postgres_reconcile_sessions.py",
        ],
    },
]

AUDIO_STORAGE_METHODS = [
    "save_audio_studio_task",
    "get_audio_studio_task",
    "get_audio_studio_tasks",
    "delete_audio_studio_task",
    "save_voice_profile",
    "get_voice_profile",
    "get_voice_profiles",
    "get_voice_profile_by_voice_id",
    "delete_voice_profile",
]

PENDING_DOMAINS = [
    {
        "name": "audio_studio",
        "summary": "Audio studio task state and cloned voice profile state.",
        "json_surfaces": ["audio_studio/*.json", "voices/*.json"],
        "current_files": [
            "backend/app/routers/audio_studio.py",
            "backend/app/models/audio_studio.py",
            "backend/app/services/storage.py",
        ],
        "expected_files": [
            "backend/app/db/schema/audio_studio.py",
            "backend/app/repositories/audio_studio.py",
            "backend/app/repositories/audio_studio_runtime.py",
            "scripts/postgres_backfill_audio_studio.py",
            "scripts/postgres_reconcile_audio_studio.py",
        ],
        "storage_methods": AUDIO_STORAGE_METHODS,
        "recommended_rollout": [
            "R68 local schema/repository for audio tasks and voice profiles",
            "R69 backfill/reconcile with redacted voice metadata",
            "R70 runtime dual-write with JSON primary and PostgreSQL shadow writes",
            "R71 read-switch canary with JSON fallback",
            "R72 primary-write canary plus JSON archive mirror",
        ],
    }
]

COVERED_EMBEDDED_SURFACES = [
    {
        "surface": "scripts/shots",
        "covered_by": "projects.raw_project_snapshot",
        "evidence_files": [
            "backend/app/db/schema/projects.py",
            "backend/app/repositories/projects.py",
        ],
        "note": "Project script and shot details are restored from the project JSONB snapshot; indexed shot count is stored separately.",
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def exists(relative_path: str) -> bool:
    return (ROOT_DIR / relative_path).exists()


def read_text(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def audit_migrated_domain(domain: dict[str, object]) -> dict[str, object]:
    expected_files = list(domain["expected_files"])
    present_files = [path for path in expected_files if exists(path)]
    missing_files = [path for path in expected_files if not exists(path)]
    status = "covered" if not missing_files else "incomplete"
    return {
        "name": domain["name"],
        "summary": domain["summary"],
        "status": status,
        "present_files": present_files,
        "missing_files": missing_files,
    }


def audit_pending_domain(domain: dict[str, object]) -> dict[str, object]:
    expected_files = list(domain["expected_files"])
    current_files = list(domain["current_files"])
    storage_text = read_text("backend/app/services/storage.py")
    storage_methods = [
        method for method in domain["storage_methods"] if f"def {method}(" in storage_text
    ]
    return {
        "name": domain["name"],
        "summary": domain["summary"],
        "status": "pending",
        "json_surfaces": domain["json_surfaces"],
        "current_files": [path for path in current_files if exists(path)],
        "missing_current_files": [path for path in current_files if not exists(path)],
        "missing_expected_files": [path for path in expected_files if not exists(path)],
        "present_expected_files": [path for path in expected_files if exists(path)],
        "storage_methods": storage_methods,
        "missing_storage_methods": [
            method for method in domain["storage_methods"] if method not in storage_methods
        ],
        "recommended_rollout": domain["recommended_rollout"],
    }


def audit_embedded_surface(surface: dict[str, object]) -> dict[str, object]:
    evidence_files = list(surface["evidence_files"])
    evidence = {path: exists(path) for path in evidence_files}
    projects_schema = read_text("backend/app/db/schema/projects.py")
    projects_repo = read_text("backend/app/repositories/projects.py")
    return {
        "surface": surface["surface"],
        "covered_by": surface["covered_by"],
        "status": "covered"
        if "raw_project_snapshot" in projects_schema
        and "raw_project_snapshot" in projects_repo
        and "script_shot_count" in projects_schema
        else "needs_review",
        "evidence_files": evidence,
        "note": surface["note"],
    }


def build_summary(run_id: str) -> dict[str, object]:
    migrated = [audit_migrated_domain(domain) for domain in MIGRATED_DOMAINS]
    pending = [audit_pending_domain(domain) for domain in PENDING_DOMAINS]
    embedded = [audit_embedded_surface(surface) for surface in COVERED_EMBEDDED_SURFACES]
    migrated_covered = [domain for domain in migrated if domain["status"] == "covered"]
    pending_names = [domain["name"] for domain in pending if domain["status"] == "pending"]
    return {
        "run_id": run_id,
        "updated_at": utc_now(),
        "state": "ready_for_next_domain",
        "next_recommended_domain": "audio_studio",
        "migrated_domain_count": len(migrated_covered),
        "pending_domain_count": len(pending_names),
        "migrated_domains": migrated,
        "pending_domains": pending,
        "covered_embedded_surfaces": embedded,
        "notes": [
            "Generated assets remain file/OSS objects, not database-primary business state.",
            "Scripts and shots are covered through the projects domain snapshot rather than a separate first-class table in this phase.",
        ],
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def render_markdown(summary: dict[str, object]) -> str:
    migrated_rows = [
        [
            f"`{domain['name']}`",
            str(domain["status"]),
            str(len(domain["present_files"])),
            ", ".join(f"`{path}`" for path in domain["missing_files"]) or "-",
        ]
        for domain in summary["migrated_domains"]
    ]
    pending_rows = [
        [
            f"`{domain['name']}`",
            ", ".join(f"`{surface}`" for surface in domain["json_surfaces"]),
            ", ".join(f"`{path}`" for path in domain["missing_expected_files"]),
        ]
        for domain in summary["pending_domains"]
    ]
    rollout_steps = "\n".join(
        f"- {step}" for step in summary["pending_domains"][0]["recommended_rollout"]
    )
    embedded_rows = [
        [
            f"`{surface['surface']}`",
            f"`{surface['covered_by']}`",
            str(surface["status"]),
        ]
        for surface in summary["covered_embedded_surfaces"]
    ]

    return "\n".join(
        [
            "# R67 PostgreSQL Domain Coverage Audit",
            "",
            f"Run ID: `{summary['run_id']}`",
            f"Updated At: `{summary['updated_at']}`",
            f"State: `{summary['state']}`",
            "",
            "## Migrated Domains",
            "",
            markdown_table(
                ["Domain", "Status", "Present Files", "Missing Files"],
                migrated_rows,
            ),
            "",
            "## Pending Domains",
            "",
            markdown_table(
                ["Domain", "JSON surfaces", "Missing PostgreSQL files"],
                pending_rows,
            ),
            "",
            "## Covered Embedded Surfaces",
            "",
            markdown_table(["Surface", "Covered By", "Status"], embedded_rows),
            "",
            "## Next Recommended Domain",
            "",
            "`audio_studio` should be the next PostgreSQL migration domain because it is still direct JSON state under `audio_studio/*.json` and `voices/*.json`, is project-scoped, participates in project cleanup, and can follow the same schema/repository/backfill/reconcile/runtime-gate pattern without provider load testing.",
            "",
            "Recommended rollout:",
            "",
            rollout_steps,
            "",
            "## Notes",
            "",
            "- `projects.raw_project_snapshot` currently covers project scripts and shots for database migration purposes.",
            "- Binary/generated media objects remain file or OSS assets; this audit tracks business state domains only.",
            "",
        ]
    )


def write_outputs(summary: dict[str, object], artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "state": summary["state"],
        "stage": "domain-coverage",
        "run_id": summary["run_id"],
        "updated_at": summary["updated_at"],
        "migrated_domain_count": summary["migrated_domain_count"],
        "pending_domain_count": summary["pending_domain_count"],
        "next_recommended_domain": summary["next_recommended_domain"],
    }
    (artifact_dir / "domain-coverage.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "domain-coverage.md").write_text(
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
        default="r67-postgres-domain-coverage",
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
    print(f"postgres domain coverage: wrote {rel(artifact_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
