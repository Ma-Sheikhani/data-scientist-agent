import socket

from celery.utils.log import get_task_logger
from prometheus_client import push_to_gateway

from workers.celery_app import celery_app
from workers.metrics import PUSHGATEWAY_URL, WORKER_HEARTBEAT, worker_registry

logger = get_task_logger(__name__)


@celery_app.task(name="heartbeat")
def heartbeat():
    """Periodic task that pushes a heartbeat metric to the Pushgateway."""
    WORKER_HEARTBEAT.set(1)
    worker_id = socket.gethostname()
    try:
        push_to_gateway(
            PUSHGATEWAY_URL,
            job="celery_worker",
            grouping_key={"instance": worker_id},
            registry=worker_registry,
        )
    except Exception as e:
        logger.error("Heartbeat push failed: %s", e)
