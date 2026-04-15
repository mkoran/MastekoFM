# === BASE ===
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-calc-nogui && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY VERSION .
COPY backend/app/ ./backend/app/

# === TEST ===
FROM base AS test

RUN pip install --no-cache-dir pytest ruff httpx

COPY tests/ ./tests/
COPY pyproject.toml .

RUN ruff check backend/ tests/
RUN python -m pytest tests/ -v

# === PROD ===
FROM base AS prod

EXPOSE 8080
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
