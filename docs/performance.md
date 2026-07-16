# Performance Baseline

Run with k6 on a fresh local deployment (Docker Compose, 5 VUs max).

```bash
docker run --rm -i --network host \
  -v $(pwd)/tests/load/test.csv:/data/test.csv:ro \
  grafana/k6 run - < tests/load/analysis_load.js
