# ── RAITO Dashboard — Cloud Run Container ──────────────────────────────
# Serves the unified dashboard from PostgreSQL via Flask + Gunicorn.
#
# Build:  docker build -t raito-dashboard .
# Run:    docker run -p 8080:8080 \
#           -e DATABASE_URL="postgresql://raito:raito@host.docker.internal:5432/raito" \
#           raito-dashboard
#
# Cloud Run: gcloud run deploy raito --source . --region ...

FROM python:3.12-slim

# System deps for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure scripts/ and scripts/db/ are on the Python path so imports like
# `from config import ...`, `from db.database_manager import ...` and
# `from migrate_transactions import ...` (used inside raito_loader.py) all work
ENV PYTHONPATH="/app/scripts:/app/scripts/db:/app"

# Create docs/ directory for dashboard output (if generators write to disk)
RUN mkdir -p /app/docs

EXPOSE 8080

# Gunicorn finds the Flask `app` object at scripts.db.db_dashboard:app
# --workers 1: dashboard generation is memory-heavy, single worker is safer
# --threads 4: handle concurrent HTTP requests within the worker
# --timeout 120: dashboard generation can take 30-60s on first request
CMD ["gunicorn", \
     "--bind", ":8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "scripts.db.db_dashboard:app"]
