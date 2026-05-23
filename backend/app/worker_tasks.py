"""Celery task entrypoints."""

import asyncio

from app.celery_app import celery_app


@celery_app.task(name="studio.generate")
def run_studio_generation(task_id: str, user_id: str | None, user_config_dir: str | None) -> None:
    from app.routers.studio import _background_generate

    asyncio.run(_background_generate(task_id, user_id, user_config_dir))
