from prometheus_client import Counter, Histogram

# Counters for job status transitions
ANALYSIS_REQUESTS = Counter(
    "analysis_requests_total",
    "Number of analysis requests submitted",
    ["status"],  # 'submitted' initially
)

JOB_COMPLETED = Counter(
    "jobs_completed_total",
    "Number of jobs successfully completed",
)

JOB_FAILED = Counter(
    "jobs_failed_total",
    "Number of jobs that failed",
)

# Histogram for job processing time (seconds)
JOB_DURATION_SECONDS = Histogram(
    "job_duration_seconds",
    "Time spent processing a job",
    buckets=[1, 5, 10, 30, 60, 120, 300, float("inf")],
)
