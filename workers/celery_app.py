from celery import Celery

from api.core.config import settings

celery_app = Celery(
    "ds_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

if settings.CELERY_TASK_ALWAYS_EAGER:
    celery_app.conf.task_always_eager = True


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


celery_app.conf.beat_schedule = {
    "cleanup-old-jobs": {
        "task": "workers.tasks.cleanup_old_jobs",
        "schedule": 3600.0,  # every hour (in seconds)
    },
}
