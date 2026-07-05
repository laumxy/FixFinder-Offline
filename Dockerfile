# =============================================================================
# FixFinder AI Engine — Dockerfile
# =============================================================================
#
# Multi-stage build:
#   Stage 1 (builder)   — compile Python wheels
#   Stage 2 (runtime)   — lean final image, no build tools
#
# Data artefacts (SQLite DBs, FAISS indices) are built at container startup
# by start.sh, not baked into the image.  This keeps the image small and
# avoids committing binary files to git.
#
# Railway / Docker run:
#   The PORT environment variable is respected — Railway injects it automatically.
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

RUN pip install --upgrade pip \
 && pip install --prefix=/install/deps --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.10-slim

LABEL maintainer="FixFinder" \
      version="2.0.0" \
      description="FixFinder AI Engine — unified REST API"

WORKDIR /app

# Runtime system dependencies (libgomp1 required by faiss-cpu)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install/deps /usr/local

# Copy all application source + data files (binaries excluded via .dockerignore)
COPY . .

# Create required runtime directories
RUN mkdir -p /app/data /app/logs /app/embeddings \
    && mkdir -p /app/Version_1/03_SQLite_Database \
                /app/Version_1/06_Embeddings \
                /app/Version_1/12_FAISS \
                /app/Version_2/03_SQLite_Database \
                /app/Version_2/06_Embeddings \
                /app/Version_2/12_FAISS \
                /app/Version_3/03_SQLite_Database \
                /app/Version_3/06_Embeddings \
                /app/Version_3/12_FAISS

# Make start.sh executable
RUN chmod +x /app/start.sh

# Health check — Railway also uses healthcheckPath in railway.toml
HEALTHCHECK --interval=30s --timeout=15s --start-period=180s --retries=5 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" \
    || exit 1

EXPOSE 8000

# Railway overrides CMD via startCommand in railway.toml
CMD ["/app/start.sh"]
