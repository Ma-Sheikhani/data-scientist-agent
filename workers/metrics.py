import os

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Shared registry for worker metrics (used by tasks + beat)
worker_registry = CollectorRegistry()

# Job counters
JOB_COMPLETED = Counter(
    "jobs_completed_total", "Jobs completed", registry=worker_registry
)
JOB_FAILED = Counter("jobs_failed_total", "Jobs failed", registry=worker_registry)
JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Job duration",
    buckets=[1, 5, 10, 30, 60, 120, 300, float("inf")],
    registry=worker_registry,
)

# Sandbox errors
SANDBOX_ERRORS = Counter(
    "sandbox_execution_errors_total",
    "Number of sandbox code steps that returned an error",
    registry=worker_registry,
)

# Heartbeat gauge
WORKER_HEARTBEAT = Gauge(
    "worker_heartbeat",
    "Heartbeat from the Celery beat (1 = alive)",
    registry=worker_registry,
)

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")
