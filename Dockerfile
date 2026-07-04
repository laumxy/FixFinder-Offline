# ── Stage 1: dependency builder ───────────────────────────────────────────────
# Install Python deps into an isolated prefix so the final image stays clean.
FROM python:3.11-slim AS builder

WORKDIR /install

# System libs needed to compile faiss-cpu and numpy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install/deps --no-cache-dir -r requirements.txt


# ── Stage 2: model pre-download ───────────────────────────────────────────────
# Pull the embedding model into the image at build time so cold-start is fast
# and the container works fully offline at runtime.
FROM python:3.11-slim AS model-fetcher

COPY --from=builder /install/deps /usr/local
COPY requirements.txt .
RUN pip install --no-cache-dir sentence-transformers==3.3.1

RUN python - <<'EOF'
from sentence_transformers import SentenceTransformer
# Downloads model weights into HuggingFace cache inside the image
SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
EOF


# ── Stage 3: final runtime image ──────────────────────────────────────────────
FROM python:3.11-slim

# Non-root user for security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy pre-downloaded HuggingFace model cache
COPY --from=model-fetcher /root/.cache/huggingface /home/appuser/.cache/huggingface

# Copy application source
COPY . .

# Persist data and embeddings on a Railway volume (or ephemeral if not mounted)
# The startup script always regenerates them if missing, so this is safe.
RUN mkdir -p /app/data/packs /app/data/reports /app/embeddings \
 && chown -R appuser:appuser /app

USER appuser

# Make startup script executable
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
