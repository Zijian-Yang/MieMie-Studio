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
    user_id: Optional[str],
    user_config_dir: Optional[str],
) -> str:
    mode = task_dispatcher_mode()
    if mode == "celery":
        try:
            from app.worker_tasks import run_studio_generation

            result = run_studio_generation.delay(task_id, user_id, user_config_dir)
            logger.info("[任务调度] 图片工作室任务 %s 已入队 Celery: %s", task_id, result.id)
            return str(result.id)
        except Exception as exc:
            logger.error("[任务调度] Celery 入队失败，回退 asyncio: %s", exc)

    from app.routers.studio import _background_generate

    asyncio.create_task(
        _background_generate(
            task_id=task_id,
            user_id=user_id,
            user_config_dir=user_config_dir,
        )
    )
    logger.info("[任务调度] 图片工作室任务 %s 已使用 asyncio 后台执行", task_id)
    return "asyncio"
