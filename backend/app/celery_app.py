"""Celery application for background generation workers."""

import os

from celery import Celery


def _broker_url() -> str:
    return (
        os.environ.get("MIEMIE_CELERY_BROKER_URL")
        or os.environ.get("MIEMIE_REDIS_URL")
        or "redis://redis:6379/2"
    )


def _result_backend_url() -> str:
    return (
        os.environ.get("MIEMIE_CELERY_RESULT_BACKEND")
        or os.environ.get("MIEMIE_REDIS_URL")
        or "redis://redis:6379/3"
    )


celery_app = Celery(
    "miemie",
    broker=_broker_url(),
    backend=_result_backend_url(),
    include=["app.worker_tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=int(os.environ.get("MIEMIE_WORKER_TASK_TIME_LIMIT", "1800")),
    task_soft_time_limit=int(os.environ.get("MIEMIE_WORKER_TASK_SOFT_TIME_LIMIT", "1500")),
)
