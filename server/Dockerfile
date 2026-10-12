FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    UPLOAD_DIR="/app/uploads"

WORKDIR /app

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications first for layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies without installing root project
RUN uv sync --frozen --no-dev --no-install-project

# Copy remaining server application code
COPY . .

# Finalize virtual environment with server package
RUN uv sync --frozen --no-dev

# Ensure uploads directory exists
RUN mkdir -p /app/uploads

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
