# Data Scientist Agent

![CI](https://github.com/yourusername/data-scientist-agent/workflows/CI/badge.svg)

An industrial‑grade, LLM‑powered data analysis agent built with FastAPI, Celery, and LangGraph. Users upload a CSV, ask a natural language question, and the agent plans, executes code in a sandbox, and returns a complete answer with visualizations—all asynchronously and securely.

## Features
- JWT‑based authentication & user management.
- Background job processing with Celery and Redis.
- Sandboxed Python code execution (coming in Week 2).
- Full observability with structured logging, Prometheus metrics, and OpenTelemetry tracing (planned).
- Docker‑compose for local dev, Kubernetes Helm chart for production (in progress).
- Comprehensive test suite with coverage.

## Quick Start

**Prerequisites:** Docker, Docker Compose, Python 3.11+, Poetry.

1. Clone the repo:
   ```bash
   git clone https://github.com/yourusername/data-scientist-agent.git
   cd data-scientist-agent
