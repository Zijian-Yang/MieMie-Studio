"""Database runtime domain flag parsing."""

from __future__ import annotations

import importlib

import pytest


RUNTIME_FLAG_CASES = [
    (
        "app.repositories.video_studio_task_runtime",
        "video_studio_tasks",
        "video_studio_task_dual_write_enabled",
        "video_studio_task_read_enabled",
        "video_studio_task_primary_write_enabled",
    ),
    (
        "app.repositories.studio_task_runtime",
        "studio_tasks",
        "studio_task_dual_write_enabled",
        "studio_task_read_enabled",
        "studio_task_primary_write_enabled",
    ),
    (
        "app.repositories.project_runtime",
        "projects",
        "project_dual_write_enabled",
        "project_read_enabled",
        "project_primary_write_enabled",
    ),
    (
        "app.repositories.media_asset_runtime",
        "media_metadata",
        "media_metadata_dual_write_enabled",
        "media_metadata_read_enabled",
        "media_metadata_primary_write_enabled",
    ),
    (
        "app.repositories.project_entity_runtime",
        "project_entities",
        "project_entity_dual_write_enabled",
        "project_entity_read_enabled",
        "project_entity_primary_write_enabled",
    ),
    (
        "app.repositories.benchmark_record_runtime",
        "benchmark_records",
        "benchmark_record_dual_write_enabled",
        "benchmark_record_read_enabled",
        "benchmark_record_primary_write_enabled",
    ),
    (
        "app.repositories.user_config_runtime",
        "user_config",
        "user_config_dual_write_enabled",
        "user_config_read_enabled",
        "user_config_primary_write_enabled",
    ),
    (
        "app.repositories.session_runtime",
        "sessions",
        "session_dual_write_enabled",
        "session_read_enabled",
        "session_primary_write_enabled",
    ),
    (
        "app.repositories.audio_studio_runtime",
        "audio_studio",
        "audio_studio_dual_write_enabled",
        "audio_studio_read_enabled",
        "audio_studio_primary_write_enabled",
    ),
]


@pytest.mark.parametrize(
    ("module_name", "domain", "dual_func", "read_func", "primary_func"),
    RUNTIME_FLAG_CASES,
)
def test_runtime_domain_flags_accept_whitespace_and_comma_lists(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    domain: str,
    dual_func: str,
    read_func: str,
    primary_func: str,
) -> None:
    module = importlib.import_module(module_name)

    monkeypatch.setenv("MIEMIE_DATABASE_ENABLED", "true")
    monkeypatch.setenv("MIEMIE_DATABASE_WRITE_MODE", "file")
    monkeypatch.setenv("MIEMIE_DATABASE_READ_MODE", "file")
    monkeypatch.setenv(
        "MIEMIE_DATABASE_DUAL_WRITE_DOMAINS",
        f"video_studio_tasks studio_tasks,{domain}\nuser_config",
    )
    monkeypatch.setenv(
        "MIEMIE_DATABASE_READ_DOMAINS",
        f"projects media_metadata,{domain}\naudio_studio",
    )
    monkeypatch.setenv(
        "MIEMIE_DATABASE_PRIMARY_WRITE_DOMAINS",
        f"benchmark_records sessions,{domain}\nproject_entities",
    )

    assert getattr(module, dual_func)() is True
    assert getattr(module, read_func)() is True
    assert getattr(module, primary_func)() is True
