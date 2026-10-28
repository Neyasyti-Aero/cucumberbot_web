FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl — для healthcheck, fonts-dejavu-core — кириллица в подписях QR-меток.
# asyncpg / psycopg2-binary / Pillow ставятся колёсами, компилятор не нужен.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt


# Линт + юнит-тесты: `docker build --target test` падает, если они не прошли.
# Образ также запускает системные тесты (tests/system) в CI.
FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
RUN ruff check . && pytest -q -p no:cacheprovider


FROM base AS runtime
COPY . .
RUN rm -rf tests requirements-dev.txt pyproject.toml \
    && mkdir -p /app/sandbox \
    && useradd -m -u 1001 botuser && chown -R botuser:botuser /app
USER botuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# --proxy-headers: реальный IP клиента из X-Forwarded-For от nginx
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
