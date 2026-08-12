from app.celery_app import celery_app


def test_ops_tasks_are_routed_only_to_ops_queue():
    routes = celery_app.conf.task_routes

    assert routes["ops.backup"] == {"queue": "ops"}
    assert routes["ops.test_oss"] == {"queue": "ops"}
    assert routes["ops.test_webhook"] == {"queue": "ops"}
    assert routes["studio.generate"] == {"queue": "studio"}
    assert routes["video_studio.generate"] == {"queue": "video_studio"}
