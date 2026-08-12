"""Celery task entrypoints."""

import asyncio

from app.celery_app import celery_app


@celery_app.task(name="studio.generate")
def run_studio_generation(
    task_id: str,
    user_id: str | None,
    user_config_dir: str | None,
    attempt_id: str | None = None,
) -> None:
    from app.routers.studio import _background_generate

    asyncio.run(_background_generate(task_id, user_id, user_config_dir, attempt_id))


@celery_app.task(
    name="video_studio.generate",
    time_limit=3600,
    soft_time_limit=3300,
)
def run_video_studio_generation(
    task_id: str,
    user_id: str | None,
    user_config_dir: str | None,
    submit_attempt_id: str | None = None,
) -> None:
    from app.routers.video_studio import _background_create_video_tasks_by_id

    asyncio.run(_background_create_video_tasks_by_id(task_id, user_id, user_config_dir, submit_attempt_id))


@celery_app.task(name="ops.backup", time_limit=3600, soft_time_limit=3300)
def run_ops_backup(run_id: str) -> None:
    from app.services.ops_runner import build_ops_runner

    build_ops_runner().run_backup(run_id)


@celery_app.task(name="ops.test_oss", time_limit=120, soft_time_limit=90)
def run_ops_oss_test(run_id: str) -> None:
    from app.services.ops_runner import build_ops_runner

    build_ops_runner().run_oss_test(run_id)


@celery_app.task(name="ops.test_webhook", time_limit=120, soft_time_limit=90)
def run_ops_webhook_test(run_id: str) -> None:
    from app.services.ops_runner import build_ops_runner

    build_ops_runner().run_webhook_test(run_id)
