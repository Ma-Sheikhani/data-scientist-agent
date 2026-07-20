# Performance & Load Testing

This document describes how to run load tests against the Data Scientist Agent API and provides baseline results.

## Test Setup

- **Tool:** [k6](https://k6.io) (open-source load testing)
- **Script:** `tests/load/analysis_load.js`
- **Scenario:** Ramp up to 3 virtual users, sustain for 1 minute, then ramp down
- **Environment:** Docker Compose stack (API, worker, PostgreSQL, Redis, sandbox) running on a single host

## How to Run

1. Ensure the full stack is running:

```bash
docker compose up -d
```

2. Find your Docker host IP:

```bash
ip addr show docker0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1
```

This is usually:

```text
172.17.0.1
```

3. Run the k6 load test:

```bash
docker run --rm -i \
  -v $(pwd)/tests/load:/tests \
  -e BASE_URL=http://<HOST_IP>:8000 \
  grafana/k6 run /tests/analysis_load.js
```

Replace `<HOST_IP>` with the IP address obtained in Step 2.

## Baseline Results (v0.2.0)

**Run Date:** 2026-07-20

| Metric | Value |
|--------|-------|
| Total HTTP requests | 245 |
| Failed requests | 0 (0.00%) |
| p95 latency | 12.15 ms |
| Maximum latency | 207.15 ms |
| Average latency | 12.25 ms |
| Requests per second | 2.44 |
| Iterations completed | 243 |
| Test duration | 1m40s |
| Maximum virtual users | 3 |
| Checks passed | 245 / 245 (100%) |

## Observations

- All endpoints (registration, login, and analysis submission) responded successfully under load.
- Latency remained low and stable throughout the test.
- No HTTP errors or timeouts were observed.
- The current single-instance deployment is well suited for development and light production workloads.
- For higher concurrency and production-scale deployments, horizontally scaling the API and worker services (for example, using Kubernetes Horizontal Pod Autoscaler) is recommended.
