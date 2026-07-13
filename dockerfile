FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies for psycopg2/asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project code (will be overridden by volume mount in dev, but needed for prod)
COPY . .

EXPOSE 8000
COPY scripts/prestart.sh /app/prestart.sh
RUN chmod +x /app/prestart.sh
CMD ["/app/prestart.sh", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
