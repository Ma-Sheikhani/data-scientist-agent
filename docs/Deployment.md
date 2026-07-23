# 🚀 Deployment Guide

This document explains how to deploy the **Data Scientist Agent** on your own infrastructure.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: Docker Compose](#option-1-docker-compose)
  - [Clone the Repository](#clone-the-repository)
  - [Set Environment Variables](#set-environment-variables)
  - [Start the Stack](#start-the-stack)
  - [Verify Services](#verify-services)
  - [Shut Down](#shut-down)
- [Option 2: Kubernetes (Helm)](#option-2-kubernetes-helm)
- [Production Considerations](#production-considerations)
- [Troubleshooting](#troubleshooting)

---

# Prerequisites

Before deploying the project, ensure you have:

- **Docker** 20.10 or newer
- **Docker Compose** v2
- **Python 3.11+** *(optional, only required for running tests locally)*
- An **OpenRouter API key** (or any OpenAI-compatible endpoint)
- *(Optional)* **Langfuse** credentials for LLM observability

---

# Option 1: Docker Compose

Docker Compose is the recommended deployment method for local development, testing, and demonstrations.

## Clone the Repository

```bash
git clone https://github.com/Ma-Sheikhani/data-scientist-agent.git
cd data-scientist-agent
```

---

## Set Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the `.env` file and configure the required variables.

Required:

```env
OPENROUTER_API_KEY=your_key_here
```

Optional:

```env
# Enable Langfuse tracing
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Override the default agent timeout (seconds)
AGENT_TIMEOUT=300
```

The remaining default values are suitable for local development.

---

## Start the Stack

From the project root, run:

```bash
cd deployments/docker-compose
docker compose up --build -d
```

The first build may take several minutes because Docker installs all Python dependencies and downloads the spaCy language model required for optional PII redaction.

Subsequent starts will be significantly faster.

The following services will be started automatically:

| Service | Port | Purpose |
|---------|-----:|---------|
| FastAPI | 8000 | REST API |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Message broker and cache |
| Celery Worker | — | Background task processing |
| Sandbox | 8001 (internal) | Secure Python execution |
| Prometheus | 9090 | Metrics collection |
| Pushgateway | 9091 | Worker metrics |
| Grafana | 3000 | Monitoring dashboards |
| n8n | 5678 | Low-code web interface |

---

## Verify Services

### API Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### API Documentation

Open:

```text
http://localhost:8000/docs
```

### Grafana

Open:

```text
http://localhost:3000
```

Default credentials:

```text
Username: admin
Password: admin
```

The preconfigured **Data Scientist Agent** dashboard should already be available.

### n8n

Open:

```text
http://localhost:5678
```

Create an account (the first registered user becomes the workspace owner).

If you want to use the no-code interface, import the workflows from:

```text
deployments/n8n/workflows/
```

---

## Shut Down

Stop the containers while preserving volumes:

```bash
docker compose down
```

Stop the containers and remove all persistent data:

```bash
docker compose down -v
```

---

# Option 2: Kubernetes (Helm)

A Helm chart is included under:

```text
deployments/helm/
```

The Helm deployment is currently under active development.

The chart is intended to support:

- Kubernetes deployments
- Horizontal Pod Autoscaling
- Persistent storage
- Ingress configuration
- Secret management
- Production-ready monitoring

More documentation will be added as the Helm chart matures.

---

# Production Considerations

For production deployments, consider the following recommendations:

- Use a reverse proxy such as **Nginx** or **Traefik**.
- Enable HTTPS using TLS certificates.
- Store secrets in a dedicated secrets manager.
- Use managed PostgreSQL and Redis services where possible.
- Configure regular database backups.
- Enable Grafana authentication.
- Restrict network access to internal services.
- Monitor resource utilization and configure alerting.
- Scale Celery workers according to workload.
- Store uploaded files in object storage (S3, Azure Blob Storage, or Google Cloud Storage) instead of local volumes.

---

# Troubleshooting

## API Returns 500 with "relation ... does not exist"

The database tables were not created successfully.

Run the migrations manually:

```bash
docker compose exec api alembic upgrade head
```

If migrations still fail, create the tables manually:

```bash
docker compose exec api python -c "
import asyncio
from api.core.database import engine, Base
from api.models import User, Job

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created')

asyncio.run(main())
"
```

---

## Sandbox Returns Errors or Times Out

Verify that the sandbox container is running:

```bash
docker compose ps sandbox
```

View the sandbox logs:

```bash
docker compose logs sandbox
```

If you encounter `read_only` filesystem errors, ensure the `/tmp` directory is writable.

The provided Docker Compose configuration already mounts `/tmp` as a writable `tmpfs`.

---

## n8n Cannot Reach the API

The n8n container communicates with the API over Docker's internal network using:

```text
http://api:8000
```

If you renamed the API service inside `docker-compose.yml`, update the URLs in the n8n workflows accordingly.

To verify connectivity:

1. Open the n8n editor.
2. Add an **HTTP Request** node.
3. Send a request to:

```text
http://api:8000/health
```

A **200 OK** response confirms that communication is working.

---

## Rate Limiting Blocks Development Tests

During development you may temporarily disable rate limiting by setting:

```env
ENABLE_RATE_LIMIT=false
```

Restart the API service after changing the environment variable.

Alternatively, clear the Redis counters:

```bash
docker compose exec redis redis-cli FLUSHDB
```

---
