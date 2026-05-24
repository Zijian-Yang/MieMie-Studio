"""Background task dispatcher abstraction."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def task_dispatcher_mode() -> str:
    return os.environ.get("MIEMIE_TASK_DISPATCHER", "asyncio").strip().lower() or "asyncio"


def dispatch_studio_generation(
    *,
    task_id: str,
    attempt_id: str,
    user_id: Optional[str],
    user_config_dir: Optional[str],
) -> dict:
    mode = task_dispatcher_mode()
    if mode == "celery":
        try:
            from app.worker_tasks import run_studio_generation

            result = run_studio_generation.apply_async(
                args=(task_id, user_id, user_config_dir, attempt_id),
                queue="studio",
            )
            logger.info("[任务调度] 图片工作室任务 %s 已入队 Celery: %s", task_id, result.id)
            return {"dispatcher": "celery", "task_id": str(result.id)}
        except Exception as exc:
            logger.error("[任务调度] Celery 入队失败，回退 asyncio: %s", exc)

    from app.routers.studio import _background_generate

    asyncio.create_task(
        _background_generate(
            task_id=task_id,
            user_id=user_id,
            user_config_dir=user_config_dir,
            attempt_id=attempt_id,
        )
    )
    logger.info("[任务调度] 图片工作室任务 %s 已使用 asyncio 后台执行", task_id)
    return {"dispatcher": "asyncio", "task_id": "asyncio"}


def video_studio_dispatcher_mode() -> str:
    return (
        os.environ.get("MIEMIE_VIDEO_STUDIO_DISPATCHER")
        or os.environ.get("MIEMIE_TASK_DISPATCHER")
        or "asyncio"
    ).strip().lower() or "asyncio"


def dispatch_video_studio_generation(
    *,
    task_id: str,
    submit_attempt_id: str,
    user_id: Optional[str],
    user_config_dir: Optional[str],
) -> dict:
    mode = video_studio_dispatcher_mode()
    if mode == "celery":
        try:
            from app.worker_tasks import run_video_studio_generation

            result = run_video_studio_generation.apply_async(
                args=(task_id, user_id, user_config_dir, submit_attempt_id),
                queue="video_studio",
            )
            logger.info("[任务调度] 视频工作室任务 %s 已入队 Celery: %s", task_id, result.id)
            return {"dispatcher": "celery", "task_id": str(result.id)}
        except Exception as exc:
            logger.error("[任务调度] 视频工作室 Celery 入队失败，回退 asyncio: %s", exc)

    from app.routers.video_studio import _background_create_video_tasks_by_id

    asyncio.create_task(
        _background_create_video_tasks_by_id(
            task_id=task_id,
            user_id=user_id,
            user_config_dir=user_config_dir,
            submit_attempt_id=submit_attempt_id,
        )
    )
    logger.info("[任务调度] 视频工作室任务 %s 已使用 asyncio 后台执行", task_id)
    return {"dispatcher": "asyncio", "task_id": "asyncio"}
