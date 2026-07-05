#!/bin/bash
# =============================================================================
# start.sh — FixFinder unified startup script (Railway + Docker)
# =============================================================================
set -e

echo "=== FixFinder startup ==="
echo "    PORT=${PORT:-8000}"
echo "    PWD=$(pwd)"

# ── 1. Original pipeline: seed the fixfinder.db if absent ─────────────────────
if [ ! -f "data/fixfinder.db" ]; then
    echo "[startup] Seeding original pipeline database ..."
    python scripts/init_db.py
    python scripts/load_extra_seed.py
    echo "[startup] Original database ready."
else
    echo "[startup] Original database exists — skipping seed."
fi

# ── 2. Original pipeline: FAISS index ─────────────────────────────────────────
echo "[startup] Building original FAISS index ..."
python scripts/build_index.py
echo "[startup] Original FAISS index ready."

# ── 3. Versioned knowledge bases (Version_1 / Version_2 / Version_3) ──────────
for V in 1 2 3; do
    DB="Version_${V}/03_SQLite_Database/fixfinder_v${V}.db"
    if [ ! -f "$DB" ]; then
        echo "[startup] v${V} database not found — rebuilding from CSVs ..."
        python master_import.py
        echo "[startup] v${V} database ready."
        break  # master_import.py rebuilds all three at once
    else
        echo "[startup] v${V} database exists."
    fi
done

# ── 4. Versioned embeddings ────────────────────────────────────────────────────
for V in 1 2 3; do
    EMB="Version_${V}/06_Embeddings/embeddings.json"
    if [ ! -f "$EMB" ]; then
        echo "[startup] Generating embeddings ..."
        python generate_embeddings.py
        break
    fi
done

# ── 5. Versioned FAISS indices ────────────────────────────────────────────────
for V in 1 2 3; do
    IDX="Version_${V}/12_FAISS/index.faiss"
    if [ ! -f "$IDX" ]; then
        echo "[startup] Building versioned FAISS indices ..."
        python build_faiss_indices.py
        break
    fi
done

echo "[startup] All data assets ready."

# ── 6. Start the unified API server ───────────────────────────────────────────
echo "[startup] Starting uvicorn on port ${PORT:-8000} ..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65
