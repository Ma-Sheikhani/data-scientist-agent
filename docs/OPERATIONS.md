# Operations Runbook

## Common Tasks
- **Start the stack:** `cd deployments/docker-compose && docker compose up -d`
- **View logs:** `docker compose logs -f api worker`
- **Restart a service:** `docker compose restart worker`

## Troubleshooting
- **Job stuck in pending?** Check that the Celery worker is running (`docker compose ps worker`). Look for Redis connection errors in worker logs.
- **Database migration issues?** Run `docker compose exec api alembic upgrade head` manually.
- **API returns 401 on valid token?** Verify JWT secret hasn't changed; token may have been issued with a different key. Re‑login.

## Health Checks
- API: `http://localhost:8000/health`
- Flower: `http://localhost:5555`
- PostgreSQL: `docker compose exec postgres pg_isready -U agent`
- Redis: `docker compose exec redis redis-cli ping`

## Scaling
- Increase Celery workers: `docker compose up -d --scale worker=3`
- In Kubernetes, adjust HPA parameters in the Helm chart.
