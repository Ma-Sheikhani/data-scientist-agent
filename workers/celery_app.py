import os

from celery import Celery

from api.core.config import settings

celery_app = Celery(
    "ds_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


celery_app.conf.task_always_eager = (
    os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # re-deliver on worker crash
    worker_prefetch_multiplier=1,  # one task at a time
)

celery_app.conf.imports = ("workers.tasks",)

celery_app.conf.beat_schedule = {
    "cleanup-old-jobs": {
        "task": "workers.tasks.cleanup_old_jobs",
        "schedule": 3600.0,  # every hour
    },
    "heartbeat": {
        "task": "heartbeat",
        "schedule": 30.0,  # every 30 seconds
    },
}

import workers.beat_tasks  # noqa: E402, F401 (beat schedule & heartbeat)
import workers.tasks  # noqa: E402, F401 (process_analysis, cleanup_old_jobs)
