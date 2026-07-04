# Single image used by web, worker, and beat services in docker-compose
# (docs/06-architecture.md §6) — the CMD is overridden per service there,
# not baked in here, since all three run the exact same codebase.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for psycopg[binary] / other C extensions, removed after install
# to keep the final image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS_FILE=requirements/prod.txt
COPY requirements/ requirements/
RUN pip install -r ${REQUIREMENTS_FILE}

COPY . .

# Default command is for the `web` service; docker-compose.yml overrides
# this for `worker` (celery worker) and `beat` (celery beat).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
