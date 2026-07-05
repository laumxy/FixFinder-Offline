#!/bin/bash
set -e

echo "=== FixFinder startup ==="

# ── 1. Initialise database from seed data if it doesn't exist ─────────────────
if [ ! -f "data/fixfinder.db" ]; then
    echo "[startup] Database not found — seeding from data/seed_data.json ..."
    python scripts/init_db.py
    echo "[startup] Loading extra seed data from data/seed_extra.json ..."
    python scripts/load_extra_seed.py
    echo "[startup] Database ready."
else
    echo "[startup] Database already exists — skipping seed."
fi

# ── 2. Build FAISS index (always rebuild to match database content) ────────────
echo "[startup] Building FAISS index ..."
python scripts/build_index.py
echo "[startup] FAISS index ready."

# ── 3. Start the API server ───────────────────────────────────────────────────
echo "[startup] Starting uvicorn on port ${PORT:-8000} ..."
exec python -m uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65
