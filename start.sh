#!/bin/bash
set -e

echo "=== FixFinder startup ==="

# ── 1. Initialise database from seed data if it doesn't exist ─────────────────
if [ ! -f "data/fixfinder.db" ]; then
    echo "[startup] Database not found — seeding from data/seed_data.json ..."
    python scripts/init_db.py
    echo "[startup] Database ready."
else
    echo "[startup] Database already exists — skipping seed."
fi

# ── 2. Build FAISS index if it doesn't exist ──────────────────────────────────
if [ ! -f "embeddings/index.faiss" ]; then
    echo "[startup] FAISS index not found — building ..."
    python scripts/build_index.py
    echo "[startup] FAISS index ready."
else
    echo "[startup] FAISS index already exists — skipping rebuild."
fi

# ── 3. Start the API server ───────────────────────────────────────────────────
echo "[startup] Starting uvicorn on port ${PORT:-8000} ..."
exec python -m uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65
