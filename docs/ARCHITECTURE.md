# Architecture

This document describes the high‑level architecture of the **Data Scientist Agent** platform.

## System Overview

The platform is a distributed, asynchronous service that accepts CSV uploads, enqueues background analysis jobs, and returns structured results. It is designed for reliability, observability, and future extensibility toward LLM‑powered agentic workflows.

## Diagram

```mermaid
graph TD
    Client[Client (curl, Swagger, k6)] -->|JWT| API[FastAPI REST API]
    API --> DB[(PostgreSQL)]
    API --> Redis[(Redis)]
    API --> FS[File Storage<br/>(/app/uploads)]
    Redis --> Worker[Celery Worker]
    Worker --> DB
    Worker --> FS
    Worker -.->|future| Sandbox[Sandbox Service]
    Worker -.->|future| LLM[LLM API / vLLM]
    Worker -.->|future| LangGraph[LangGraph Agent]


    # Architecture Overview

## Components

### 1. FastAPI REST API (`api/`)
Serves as the entry point for all client interactions.

- Handles user authentication (JWT), file uploads, and job submission.
- Communicates with PostgreSQL for persistent data and Redis for task queuing.
- Built with async SQLAlchemy and Pydantic v2 for validation.

### 2. Celery Worker (`workers/`)
Processes analysis jobs asynchronously from Redis.

- Picks up analysis jobs from Redis and executes them asynchronously.
- Currently performs a dummy analysis (reads a CSV and stores its shape).
- Future versions will orchestrate the LLM agent, code execution, and sandboxed computations.
- Supports retries, dead-letter queues, and graceful error handling.

### 3. PostgreSQL Database
Stores persistent application data.

- User accounts
- Job metadata
- Planned audit logs

Database schema migrations are managed with Alembic.

### 4. Redis
Provides messaging infrastructure.

- Message broker for Celery job queues.
- Result backend for Celery task status and polling.

### 5. File Storage
Uploaded datasets are stored locally.

- CSV files are saved to a shared volume (`/app/uploads`) accessible by both API and worker containers.
- Planned migration to object storage (MinIO/S3) for production deployments.

### 6. Sandbox Service *(Planned – Week 2)*
Provides secure execution of untrusted Python code.

- Isolated environment for LLM-generated code.
- Communicates with workers via HTTP or gRPC.
- Restricts network access, filesystem permissions, CPU, and memory usage.

### 7. LLM / Agent Engine *(Planned – Weeks 2–3)*
Responsible for intelligent data analysis.

- LangGraph-based state machine for planning and execution.
- Generates and executes Python code.
- Performs reflection and iterative reasoning.
- Connects to an LLM backend (vLLM or OpenRouter).

---

# Request Lifecycle

## 1. Registration / Login

```text
Client
    │
    ▼
POST /auth/register
or
POST /auth/token
    │
    ▼
FastAPI API
    │
    ▼
JWT Access Token
```

---

## 2. Analysis Submission

1. The client uploads:
   - a CSV dataset
   - a natural language question

2. The request is sent to:

```http
POST /v1/analyze
```

3. The API:

- saves the uploaded file
- creates a `Job` record with status `PENDING`
- enqueues a Celery task (`process_analysis`)
- returns the generated `job_id`

---

## 3. Background Processing

The Celery worker:

1. Retrieves the queued task.
2. Updates the job status to `RUNNING`.
3. Performs analysis.

Current implementation:

- Reads the CSV.
- Stores its dimensions.

Future implementation:

- Invokes the LangGraph agent.
- Generates Python code.
- Executes code in the sandbox.
- Produces structured analysis.

Finally:

- Stores the resulting JSON.
- Updates the status to `COMPLETED` or `FAILED`.

---

## 4. Result Polling

The client periodically requests:

```http
GET /v1/analyze/{job_id}/status
```

until the returned status is either:

- `COMPLETED`
- `FAILED`

---

# Key Design Decisions

## Asynchronous Database Access

- Uses SQLAlchemy Async with `asyncpg`.
- Prevents blocking the FastAPI event loop.
- Improves scalability under concurrent load.

## Stateless Authentication

- JWT-based authentication.
- No server-side sessions.
- Simplifies horizontal scaling.

## Background Task Queue

- Long-running AI analysis is delegated to Celery workers.
- Keeps API response times low.
- Allows API and workers to scale independently.

## Containerized Development

- Docker Compose mirrors the intended production architecture.
- Images can later be deployed to Kubernetes with minimal changes.

## Code Quality

The project uses automated quality gates including:

- Black
- isort
- Flake8
- Mypy
- Bandit
- Pre-commit hooks
- Continuous Integration (CI)

---

# Directory Structure

```text
data-scientist-agent/
├── api/                     # FastAPI application
│   ├── core/                # Configuration, database, security
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # API endpoints
│   ├── schemas/             # Pydantic request/response schemas
│   └── services/            # Business logic
│
├── workers/                 # Celery configuration and tasks
├── agent/                   # (Future) LangGraph agent
├── sandbox/                 # (Future) Secure execution service
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── load/
│
├── deployments/
│   ├── docker-compose/
│   └── kubernetes/          # (Planned) Helm chart
│
├── docs/
├── .github/
│   └── workflows/           # CI pipeline
│
├── Dockerfile
└── README.md
```

---

# Future Enhancements

- Replace the dummy analysis with a full LangGraph-powered agent.
- Add a secure sandbox service (e.g., nsjail or gVisor) for executing LLM-generated Python code.
- Integrate observability using OpenTelemetry, Prometheus, and Grafana.
- Migrate file storage from local volumes to MinIO/S3.
- Add automatic PII detection and redaction.
- Deploy to Kubernetes using Helm with horizontal auto-scaling.
