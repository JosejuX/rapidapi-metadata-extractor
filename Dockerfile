# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — installs Python deps in an isolated layer
# §70: multi-stage build for minimal final image size
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only requirements first for layer caching
COPY rapidapi_service/requirements.txt .

# Install into a prefix we'll copy into the final stage
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — lean image, non-root user
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# §70: non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source. The real application now lives under app/ (a
# modular package split out from the original monolith) — main.py is a thin
# backward-compatibility shim re-exporting `app` from `app.main`, so both
# must be copied for `gunicorn main:app` to resolve.
COPY rapidapi_service/main.py .
COPY rapidapi_service/openapi.json .
COPY rapidapi_service/assets ./assets
COPY rapidapi_service/app ./app

# §70: drop to non-root
USER appuser

# Expose port
EXPOSE 8000

# §70: healthcheck using the lightweight /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# §70: correct signal handling for graceful shutdown via gunicorn
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 4 workers (2×CPU+1 heuristic for I/O-bound async workload)
# Uses UvicornWorker for asyncio event loop per worker
CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "30", \
     "--graceful-timeout", "10", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
