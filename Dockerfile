FROM python:3.12-slim

# Install system dependencies (ffmpeg for media inspection, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /app

# Install python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY bot/ /app/bot/

# Create data directory for SQLite WAL database
RUN mkdir -p /app/data && chown -R botuser:botuser /app

USER botuser

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/tasks.db

CMD ["python", "-m", "bot.main"]
