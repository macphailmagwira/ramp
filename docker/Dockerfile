# === Base stage ===
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PIP_RETRIES=20

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# === Dependencies installation stage ===
FROM base AS dependencies

COPY pyproject.toml poetry.lock ./

ENV POETRY_VERSION=2.2.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN curl -sSL https://install.python-poetry.org | python3 - && \
    /opt/poetry/bin/poetry --version && \
    /opt/poetry/bin/poetry self add poetry-plugin-export

RUN /opt/poetry/bin/poetry export -f requirements.txt \
    --output requirements.txt \
    --without-hashes \
    --only main && \
    pip install --no-cache-dir -r requirements.txt

RUN python -c "import uvicorn; import gunicorn; import fastapi; print('✓ Core packages installed successfully')"

# === Development stage ===
FROM base AS development

ENV POETRY_VERSION=2.2.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org | python3 - && \
    /opt/poetry/bin/poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock ./

# Install all dependencies (including dev) + watchfiles for reliable hot reload
RUN poetry install --no-root && \
    pip install watchfiles

# Copy only entrypoint — source code comes from volume mount at runtime
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

# === Production stage ===
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

RUN python -c "import uvicorn; import gunicorn; import fastapi; print('✓ Production packages verified')" && \
    which uvicorn && which gunicorn

COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser logging.json ./
COPY --chown=appuser:appuser gunicorn.conf.py ./
COPY --chown=appuser:appuser docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

USER appuser
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]