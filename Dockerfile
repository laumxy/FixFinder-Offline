# =============================================================================
# FixFinder AI Engine — Dockerfile
# =============================================================================
#
# Multi-stage build:
#   Stage 1 (builder)      — compile Python wheels
#   Stage 2 (data-prep)    — generate CSVs, JSON, embeddings, FAISS indices
#   Stage 3 (runtime)      — lean final image, no build tools
#
# The resulting image is self-contained: all three versioned SQLite databases,
# embeddings, and FAISS indices are baked in.  No network access is needed
# at runtime.
#
# Build:
#   docker build -t fixfinder:latest .
#
# Run:
#   docker run -p 8000:8000 fixfinder:latest
# =============================================================================

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /install

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all deps into a prefix directory for clean copying later
RUN pip install --upgrade pip \
 && pip install --prefix=/install/deps --no-cache-dir -r requirements.txt


# ── Stage 2: data preparation ─────────────────────────────────────────────────
# Runs the build scripts so the data artefacts are ready inside the image.
# This stage is skipped on re-builds if the source data hasn't changed
# (Docker layer cache) — keeping iterative builds fast.
FROM python:3.10-slim AS data-prep

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy everything needed for the build scripts
COPY . .

# Run data pipeline (only if artefacts are not already present in source tree)
RUN python generate_csvs.py      && echo "[OK] CSVs generated" \
 && python generate_jsons.py     && echo "[OK] JSONs generated" \
 && python generate_embeddings.py && echo "[OK] Embeddings generated" \
 && python build_faiss_indices.py && echo "[OK] FAISS indices built"


# ── Stage 3: final runtime image ──────────────────────────────────────────────
FROM python:3.10-slim

LABEL maintainer="FixFinder" \
      version="2.0.0" \
      description="FixFinder AI Engine — standalone REST API"

# Non-root user for security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Runtime system dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source + data artefacts generated in Stage 2
COPY --from=data-prep --chown=appuser:appuser /app /app

# Create log and report directories
RUN mkdir -p /app/logs \
 && chown -R appuser:appuser /app

USER appuser

# Health check — hits /health every 30s, allows 120s startup for engine warm-up
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

EXPOSE 8000

# Default: run the standalone api_server
CMD ["python", "api_server.py", "--host", "0.0.0.0", "--port", "8000"]
