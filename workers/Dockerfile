FROM python:3.11-slim-bookworm

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    C_FORCE_ROOT=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

COPY src ./src

RUN python -c "import celery; import boto3; import botocore; print('Dependencies OK')"

CMD ["celery", "-A", "src.core.celery_app:app", "worker", "--queues=s3-events,default,celery", "-l", "INFO"]