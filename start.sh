#!/bin/bash
# =============================================================================
# start.sh — FixFinder unified startup script (Railway + Docker)
# =============================================================================
set -e

echo "=== FixFinder startup ==="
echo "    PORT=${PORT:-8000}"
echo "    PWD=$(pwd)"

# ── 1. Original pipeline database (seed_data.json → data/fixfinder.db) ────────
if [ ! -f "data/fixfinder.db" ]; then
    echo "[startup] Seeding original pipeline database from data/seed_data.json ..."
    python scripts/init_db.py
    python scripts/load_extra_seed.py
    echo "[startup] Original database ready."
else
    echo "[startup] Original database exists — skipping seed."
fi

# ── 2. Original pipeline FAISS index ──────────────────────────────────────────
echo "[startup] Building original pipeline FAISS index ..."
python scripts/build_index.py
echo "[startup] Original FAISS index ready."

# ── 3. Versioned knowledge base databases ─────────────────────────────────────
# build_databases.py creates the schema AND seeds all data in one step.
# It is idempotent — it drops and recreates each DB so re-runs are safe.
DB_EXISTS=true
for V in 1 2 3; do
    if [ ! -f "Version_${V}/03_SQLite_Database/fixfinder_v${V}.db" ]; then
        DB_EXISTS=false
        break
    fi
done

if [ "$DB_EXISTS" = false ]; then
    echo "[startup] Building versioned databases (schema + seed data) ..."
    python build_databases.py
    echo "[startup] Versioned databases ready."
else
    echo "[startup] Versioned databases exist — skipping build."
fi

# ── 4. Import CSVs and seed RV-specific symptoms ──────────────────────────────
echo "[startup] Importing CSV data into versioned databases ..."
python master_import.py
echo "[startup] CSV import complete."

echo "[startup] Seeding RV and appliance-specific symptoms ..."
python seed_rv_symptoms.py
echo "[startup] RV symptoms seeded."

echo "[startup] Seeding RV repair procedures ..."
python seed_rv_repairs.py
echo "[startup] RV repair procedures seeded."

echo "[startup] Adding missing repairs to v2/v3 JSON ..."
python _add_missing_repairs.py
echo "[startup] Missing repairs added."

# ── 5. Generate embeddings (if missing) ───────────────────────────────────────
EMB_MISSING=false
for V in 1 2 3; do
    if [ ! -f "Version_${V}/06_Embeddings/embeddings.json" ]; then
        EMB_MISSING=true
        break
    fi
done

if [ "$EMB_MISSING" = true ]; then
    echo "[startup] Generating embeddings ..."
    python generate_embeddings.py
    echo "[startup] Embeddings generated."
else
    echo "[startup] Embeddings exist — skipping."
fi

# ── 6. Build versioned FAISS indices (if missing) ─────────────────────────────
FAISS_MISSING=false
for V in 1 2 3; do
    if [ ! -f "Version_${V}/12_FAISS/index.faiss" ]; then
        FAISS_MISSING=true
        break
    fi
done

if [ "$FAISS_MISSING" = true ]; then
    echo "[startup] Building versioned FAISS indices ..."
    python build_faiss_indices.py
    echo "[startup] Versioned FAISS indices ready."
else
    echo "[startup] Versioned FAISS indices exist — skipping."
fi

echo "[startup] All data assets ready."

# ── 7. Start the unified API server ───────────────────────────────────────────
echo "[startup] Starting uvicorn on port ${PORT:-8000} ..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65
