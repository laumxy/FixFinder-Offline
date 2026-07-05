# FixFinder Knowledge Library

> **Offline-first AI repair guidance system** — semantic search, guided diagnosis,
> and complete repair planning across three versioned knowledge bases.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![FAISS](https://img.shields.io/badge/FAISS-1.9.0-orange.svg)](https://github.com/facebookresearch/faiss)
[![Tests](https://img.shields.io/badge/Tests-230%20passed-brightgreen.svg)](#testing)
[![Validation](https://img.shields.io/badge/Validation-285%2F285-brightgreen.svg)](#validation)

---

## Overview

FixFinder is a complete AI-powered knowledge library that helps diagnose problems
and generate step-by-step repair plans for three domains:

| Version | Domain | Systems | Symptoms | Repairs | Parts |
|---------|--------|---------|----------|---------|-------|
| **v1** 🏠 | Home Maintenance | 39 | 51 | 15 | 47 |
| **v2** 📱 | Electronics | 41 | 48 | 15 | 41 |
| **v3** 🔧 | Industrial / Automotive | 37 | 47 | 15 | 43 |
| **Total** | | **117** | **146** | **45** | **131** |

Each version is fully self-contained with its own SQLite database, 768-dim
FAISS embeddings index, diagnostic decision trees, and repair procedures.

---

## Architecture

```
FixFinder Backend/
│
├── Version_1/                    # Home Maintenance knowledge base
│   ├── 01_Master_Taxonomy/       # Category and system taxonomy
│   ├── 02_Master_Schema/         # Database schema definitions
│   ├── 03_SQLite_Database/       # fixfinder_v1.db (188 KB)
│   ├── 04_CSV/                   # systems.csv, symptoms.csv, parts.csv
│   ├── 05_JSON/                  # diagnostic_trees.json, repair_procedures.json
│   ├── 06_Embeddings/            # embeddings.json (30 × 768-dim vectors)
│   ├── 12_FAISS/                 # index.faiss + metadata.json
│   └── 13_Validation/            # validation_report.json
│
├── Version_2/                    # Electronics knowledge base (same structure)
├── Version_3/                    # Industrial / Automotive (same structure)
│
├── ai_engine/                    # Core AI components
│   ├── __init__.py               # Package exports (v1.2.0)
│   ├── retrieval_engine.py       # FAISS semantic search + SQLite lookups
│   ├── diagnostic_engine.py      # Symptom scoring + decision tree traversal
│   └── repair_reasoning_engine.py# Repair matching + parts availability + plans
│
├── app/                          # Original FastAPI pipeline (v1 routes)
│   ├── api/routes.py             # Original /diagnose endpoint
│   └── api/v2_routes.py          # New /v2/* AI engine endpoints
│
├── scripts/                      # Build and utility scripts
│   ├── master_build.py           # Orchestrates all 11 build phases
│   └── validation_suite.py       # 7-group data quality validation (95 tests/version)
│
├── tests/                        # Test suites
│   ├── test_retrieval.py         # 33 tests — AIRetrievalEngine
│   ├── test_diagnostic.py        # 51 tests — AIDiagnosticEngine
│   ├── test_repair_reasoning.py  # 84 tests — AIRepairReasoningEngine
│   └── test_api_v2.py            # 62 tests — /v2 REST API endpoints
│
├── api_server.py                 # Standalone FastAPI server (all engines)
├── fixfinder.py                  # Unified CLI + FixFinderSystem class
├── generate_csvs.py              # Phase 4: CSV generation
├── generate_jsons.py             # Phase 5: JSON generation
├── generate_embeddings.py        # Phase 6: Embedding generation
├── build_faiss_indices.py        # Phase 7: FAISS index builder
├── master_import.py              # Import CSVs into SQLite
├── embedding_utils.py            # Embedding utility functions
├── faiss_utils.py                # FAISS query utilities
├── Dockerfile                    # Multi-stage Docker build (Python 3.10-slim)
├── docker-compose.yml            # Service + volume definitions
├── docker_build.sh               # Docker build/run helper (Bash)
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## Quick Start

### Option 1 — Python (direct)

```bash
# Clone / navigate to project
cd "FixFinder Backend"

# Install dependencies
pip install -r requirements.txt

# Verify everything is built
python scripts/master_build.py --skip-tests

# Run the unified CLI
python fixfinder.py --list-versions
python fixfinder.py --search "roof leaking after rain"
python fixfinder.py --demo

# Start the API server
python api_server.py --host 0.0.0.0 --port 8000
```

### Option 2 — Docker

```bash
# Build and start (detached)
./docker_build.sh

# Or with Docker Compose directly
docker compose up --build -d

# Test
curl http://localhost:8000/health
```

### Option 3 — Programmatic

```python
from fixfinder import FixFinderSystem

with FixFinderSystem() as ff:
    # Search all versions
    results = ff.search_all("battery drains fast", top_k=5)

    # Diagnose a problem
    diagnosis = ff.diagnose_all("outlet dead no power", top_k=5)

    # Get a repair plan
    plan = ff.repair_all("PRB-ROF-002")

    # Get entity details
    system  = ff.get_system_info("ROF-001", version=1)
    symptom = ff.get_symptom_info("PRB-PHN-001", version=2)

    # Version statistics
    stats = ff.get_version_stats(1)
```

---

## Installation

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.12 recommended |
| pip | 24+ | |
| RAM | 2 GB+ | 4 GB recommended for all 3 versions |
| Disk | 500 MB | For databases, indices, and artefacts |

### Install dependencies

```bash
pip install -r requirements.txt
```

Core packages installed:

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.111.0 | REST API framework |
| `uvicorn` | 0.34.0 | ASGI server |
| `pydantic` | 2.13.4 | Request/response validation |
| `faiss-cpu` | 1.9.0 | Vector similarity search |
| `numpy` | 2.2.1 | Numerical operations |
| `pytest` | 9.0.3 | Test runner |

### Rebuild all artefacts (if needed)

```bash
# Full rebuild from scratch
python scripts/master_build.py --force

# Individual phases
python generate_csvs.py          # Phase 4 - CSVs
python generate_jsons.py         # Phase 5 - JSON trees + procedures
python generate_embeddings.py    # Phase 6 - 768-dim embeddings
python build_faiss_indices.py    # Phase 7 - FAISS indices
```

---

## Usage

### CLI Reference

```bash
# Semantic search across all versions
python fixfinder.py --search "roof leaking near chimney"
python fixfinder.py --search "battery not charging" --version 2 --top-k 3
python fixfinder.py --search "engine light" --entity-type symptom

# Symptom analysis + guided diagnosis
python fixfinder.py --diagnose "electrical outlet completely dead"
python fixfinder.py --diagnose "laptop overheating shuts down" --version 2

# Generate full repair plan
python fixfinder.py --repair "PRB-ROF-002"
python fixfinder.py --repair "PRB-PHN-001"

# Entity detail lookups
python fixfinder.py --info "ROF-001" --version 1
python fixfinder.py --info "PRB-CAR-001" --version 3

# Version statistics
python fixfinder.py --stats 1
python fixfinder.py --stats 2
python fixfinder.py --list-versions

# Full demo (all steps, all versions)
python fixfinder.py --demo

# Output raw JSON for any command
python fixfinder.py --search "battery" --json
```

### API Server

Start the standalone server:

```bash
python api_server.py                          # localhost:8000
python api_server.py --host 0.0.0.0 --port 9000
python api_server.py --reload                 # dev mode with auto-reload
```

Interactive docs: **http://localhost:8000/docs** (Swagger UI)

#### REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | API info + endpoint map |
| `GET`  | `/health` | Engine health + rate-limiter stats |
| `POST` | `/search` | Semantic FAISS search (one or all versions) |
| `POST` | `/diagnose` | Symptom analysis + guided decision-tree traversal |
| `POST` | `/repair-plan` | Full repair plan with steps, parts, cost |
| `GET`  | `/systems/{id}?version=N` | System details from SQLite |
| `GET`  | `/symptoms/{id}?version=N` | Symptom details from SQLite |
| `GET`  | `/repairs/{id}?version=N` | Repair procedure from SQLite |

Also available under `/v2/`:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v2/{v}/search` | FAISS search for a specific version |
| `POST` | `/v2/{v}/analyze` | Keyword-scored symptom analysis |
| `GET`  | `/v2/{v}/tree/{code}` | Full diagnostic decision tree |
| `POST` | `/v2/{v}/diagnose` | Guided tree traversal |
| `POST` | `/v2/{v}/recommend` | Ranked repair recommendations |
| `GET`  | `/v2/{v}/parts/{id}` | Parts availability + stock status |
| `POST` | `/v2/{v}/plan` | Full repair plan |

#### Example API calls

```bash
# Search all versions
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "roof leaking after rain", "top_k": 5}' | python3 -m json.tool

# Diagnose a problem
curl -s -X POST http://localhost:8000/diagnose \
  -H "Content-Type: application/json" \
  -d '{"user_input": "outlet dead no power bathroom", "version": 1}' \
  | python3 -m json.tool

# Full repair plan
curl -s -X POST http://localhost:8000/repair-plan \
  -H "Content-Type: application/json" \
  -d '{"symptom_code": "PRB-ROF-002", "version": 1}' | python3 -m json.tool

# System lookup
curl "http://localhost:8000/systems/ROF-001?version=1"
```

---

## AI Engine Details

### AIRetrievalEngine

```python
from ai_engine.retrieval_engine import AIRetrievalEngine

with AIRetrievalEngine(version=1) as eng:
    # Semantic FAISS search
    results = eng.search("roof leaking", top_k=5, entity_type_filter="symptom")

    # Entity lookups
    system  = eng.get_system_details("ROF-001")
    symptom = eng.get_symptom_details("PRB-ROF-002")
    repair  = eng.get_repair_procedure("rep_roof_shingle")
```

**How it works:**
- Generates a deterministic 768-dim embedding using SHA-256 → NumPy `RandomState`
- Normalises with `faiss.normalize_L2` for cosine similarity via `IndexFlatIP`
- Queries SQLite with `check_same_thread=False` for thread-safe use in FastAPI

### AIDiagnosticEngine

```python
from ai_engine.diagnostic_engine import AIDiagnosticEngine

with AIDiagnosticEngine(version=1) as eng:
    # Symptom matching (weighted keyword overlap)
    matches = eng.analyze_symptoms("outlet dead no power", top_k=5)

    # Load a decision tree
    tree = eng.get_diagnostic_tree("PRB-ELC-002")

    # Walk the tree with yes/no responses
    result = eng.run_diagnostic("PRB-ELC-002", ["no", "yes", "no"])
    print(result["recommended_action"])   # "Replace outlet receptacle"
    print(result["repair_code"])          # "RP-ELC-001"
```

**Symptom scoring algorithm:**
- Tokenise input, remove 40+ stop-words
- Score each symptom: name tokens ×3, description ×2, causes ×1
- Normalised to [0,1] with +0.20 substring bonus for exact matches

### AIRepairReasoningEngine

```python
from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine

with AIRepairReasoningEngine(version=1) as eng:
    # Ranked repair recommendations
    recs = eng.recommend_repair("PRB-ROF-002", diagnostic_result={
        "repair_code": "RP-ROF-001", "category": "Roofing"
    })

    # Parts availability check
    parts = eng.check_parts_availability("RP-ROF-001")
    print(parts["total_parts_cost"])        # $69.48
    print(parts["all_parts_available"])     # False (some out of stock)

    # Complete repair plan
    plan = eng.generate_repair_plan("PRB-ROF-002")
    print(plan["summary"])          # "Replacing Asphalt Shingles (Moderate, 2-3 hours, $69.48 parts)"
    print(plan["urgency"])          # "Urgent"
    print(len(plan["plan_steps"]))  # 23 ordered steps
```

**Repair scoring tiers:**
1. `1.00` — Direct `repair_code` match from diagnostic result
2. `0.90` — Resolution path repair code match
3. `0.70+` — Category match (with action-token bonus)
4. `0.40–0.69` — Keyword overlap with repair name/materials

---

## Data Model

### SQLite Schema (per version)

Each `fixfinder_vX.db` contains 13 tables:

```
categories          category_id, version_id, category_name, ...
subcategories       subcategory_id, category_id, subcategory_name
systems             system_id, subcategory_id, system_name, system_code,
                    brand, lifespan_years, specifications (JSON), ...
symptoms            symptom_id, system_id, category_id, symptom_name,
                    symptom_code, severity, common_causes (JSON), ...
diagnostic_trees    tree_id, symptom_id, tree_name, steps (JSON),
                    decision_points (JSON), resolution_paths (JSON)
repair_procedures   repair_id, system_id, repair_name, repair_code,
                    procedure_steps (JSON), difficulty, estimated_time_minutes
parts_inventory     part_id, part_name, part_code, average_cost,
                    current_stock, reorder_level, supplier, ...
embeddings          embedding_id, entity_type, entity_id, embedding_vector
faiss_metadata      index metadata
repair_records      historical repair tracking
validation_results  test result history
ai_prompts          prompt templates
```

### Embedding Format (embeddings.json)

```json
{
  "version": "1.0",
  "dimension": 768,
  "total_embeddings": 30,
  "embeddings": [
    {
      "entity_type": "system",
      "entity_id":   "ROF-001",
      "text":        "Asphalt Shingle Roof GAF Asphalt Shingles 20-year ...",
      "embedding":   [0.06467, -0.00439, 0.00642, ...]
    }
  ]
}
```

### FAISS Metadata (metadata.json)

```json
{
  "version": "1.0",
  "dimension": 768,
  "index_type": "IndexFlatIP",
  "total_entries": 30,
  "id_mapping": {"0": "ROF-001", "1": "ROF-002", ...},
  "mapping": {
    "Roofing": {"range": [0, 29], "ids": ["ROF-001", ...]},
    "Plumbing": {"range": [3, 26], "ids": ["PLM-001", ...]}
  }
}
```

---

## Testing

Run all test suites from the project root:

```bash
# Individual suites
python tests/test_retrieval.py --tests-only          # 33 tests
python tests/test_diagnostic.py --tests-only         # 51 tests
python tests/test_repair_reasoning.py --tests-only   # 84 tests
python tests/test_api_v2.py --tests-only             # 62 tests

# All at once via pytest
pytest tests/ -v

# With rich output + demo
python tests/test_retrieval.py
python tests/test_diagnostic.py
python tests/test_repair_reasoning.py --demo
```

### Test coverage

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_retrieval.py` | 33 | Engine lifecycle, FAISS search, entity lookups, entity-type filter, determinism |
| `test_diagnostic.py` | 51 | Symptom scoring, score ranges, sorting, tree loading, traversal, yes/no paths |
| `test_repair_reasoning.py` | 84 | Recommendations, ranking, parts availability, plan structure, urgency |
| `test_api_v2.py` | 62 | All 11 endpoints × 3 versions, 404/422 validation |
| **Total** | **230** | All passing ✅ |

### Validation suite

```bash
# Run 7-group data quality validation for all versions
python scripts/validation_suite.py

# Single version
python scripts/validation_suite.py --version 1 --verbose
```

| Group | Tests | What it checks |
|-------|-------|----------------|
| Schema Integrity | 24 | All tables exist, required columns present, FK declarations |
| Data Completeness | 26 | No nulls in key fields, valid enum values, positive ranges |
| Referential Integrity | 11 | All FK values resolve, no orphaned rows, unique codes |
| Embedding Quality | 8 | JSON exists, 768-dim, L2-normalised, FAISS metadata consistent |
| Diagnostic Coverage | 8 | JSON trees exist, steps/decisions/resolutions complete |
| Repair Procedures | 10 | JSON repairs have steps/tools/materials, DB rows validated |
| Parts Availability | 8 | Cost positive, stock non-negative, in-stock rate ≥50% |
| **Total per version** | **95** | **100% passing** ✅ |

**285 / 285 validation checks passing** across all three versions.

---

## Build System

### Master build script

```bash
# Full build — all phases, all versions
python scripts/master_build.py

# Options
python scripts/master_build.py --version 1          # single version
python scripts/master_build.py --skip-tests         # skip test phases
python scripts/master_build.py --force              # rebuild existing artefacts
python scripts/master_build.py --dry-run            # print what would run
python scripts/master_build.py --summary-only       # show last build report
```

### Build phases

| Phase | Script | Description |
|-------|--------|-------------|
| 1 | — | Master Taxonomy (manually authored) |
| 2 | DB check | SQLite schema verification |
| 3 | DB check | Row count validation |
| 4 | `generate_csvs.py` | systems / symptoms / parts CSVs |
| 5 | `generate_jsons.py` | diagnostic trees + repair procedures |
| 6 | `generate_embeddings.py` | 30 × 768-dim SHA-256 embeddings per version |
| 7 | `build_faiss_indices.py` | `IndexFlatIP` FAISS index per version |
| 8 | `tests/test_retrieval.py` | Retrieval engine tests |
| 9 | `tests/test_diagnostic.py` | Diagnostic engine tests |
| 10 | `tests/test_repair_reasoning.py` | Repair reasoning tests |
| 11 | `scripts/validation_suite.py` | 95-check data quality validation |

---

## Docker

```bash
# Build and start
./docker_build.sh              # full build + detached start
./docker_build.sh build        # build image only
./docker_build.sh dev          # foreground with live logs
./docker_build.sh health       # query /health endpoint
./docker_build.sh logs         # tail container logs
./docker_build.sh shell        # bash inside container

# Or with Docker Compose
docker compose up --build -d
docker compose logs -f api
docker compose down
```

Environment variables (`.env` file):

```env
API_PORT=8000
FIXFINDER_ENV=production
FIXFINDER_LOG_LEVEL=info
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_PERIOD=60
ALLOWED_ORIGINS=http://localhost:3000
```

See [README_DOCKER.md](README_DOCKER.md) for full Docker documentation.

---

## Version Details

### Version 1 — Home Maintenance 🏠

**Coverage:** Roofing, plumbing, electrical, HVAC, windows, garage, foundation, appliances

| Metric | Value |
|--------|-------|
| Systems | 39 |
| Symptoms | 51 (Medium=22, High=19, Critical=6, Low=4) |
| Repair procedures | 15 |
| Parts inventory | 47 (51% in stock) |
| Diagnostic trees | 12 (DB) + 4 (JSON) |
| Categories | 19 |
| Database size | 188 KB |
| Embeddings | 30 × 768-dim, L2-normalised |
| Validation | 95/95 PASS |

Sample systems: Asphalt Shingle Roof, 200A Electrical Panel, Gas Furnace, Central AC,
Copper Plumbing, Sump Pump, Double-Pane Windows, Garage Door Opener

### Version 2 — Electronics 📱

**Coverage:** Smartphones, tablets, laptops, desktops, TVs, gaming consoles,
audio, cameras, networking, wearables

| Metric | Value |
|--------|-------|
| Systems | 41 |
| Symptoms | 48 (High=21, Medium=18, Critical=8, Low=1) |
| Repair procedures | 15 |
| Parts inventory | 41 (56% in stock) |
| Diagnostic trees | 12 (DB) + 4 (JSON) |
| Categories | 30 |
| Database size | 184 KB |
| Embeddings | 30 × 768-dim, L2-normalised |
| Validation | 95/95 PASS |

Sample systems: iPhone 15 Pro Max, Samsung Galaxy S24 Ultra, MacBook Pro 16",
Dell XPS 15, Samsung QLED 65", PlayStation 5, Cisco RV340 Router

### Version 3 — Industrial / Automotive 🔧

**Coverage:** Cars, trucks, motorcycles, heavy equipment, generators,
compressors, electric motors, solar systems

| Metric | Value |
|--------|-------|
| Systems | 37 |
| Symptoms | 47 (High=23, Medium=12, Critical=11, Variable=1) |
| Repair procedures | 15 |
| Parts inventory | 43 (54% in stock) |
| Diagnostic trees | 12 (DB) + 4 (JSON) |
| Categories | 31 |
| Database size | 192 KB |
| Embeddings | 30 × 768-dim, L2-normalised |
| Validation | 95/95 PASS |

Sample systems: Toyota Camry, Ford F-150, Tesla Model 3,
Caterpillar 320 Excavator, Cummins Diesel Generator 20kW, ABB AC Motor 5HP

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total systems across all versions | **117** |
| Total symptoms across all versions | **146** |
| Total repair procedures | **45** |
| Total parts inventory records | **131** |
| Total diagnostic trees | **36** |
| Total embedding vectors | **90** (30 × 3 versions) |
| Embedding dimension | 768 |
| FAISS index type | IndexFlatIP (cosine similarity) |
| Test suites | 4 |
| Total tests | **230** (all passing) |
| Validation checks | **285** (all passing) |
| Python source files | ~34 |
| API endpoints | 19 (8 standalone + 11 v2) |
| Rate limit | 60 req / 60s per IP |

---

## Development

### Project structure conventions

- **Engine classes** follow the context-manager protocol (`__enter__` / `__exit__`)
  — always use `with` or call `.close()` to release SQLite connections
- **Embedding generation** is deterministic: the same text always produces the
  same 768-dim vector (SHA-256 → NumPy `RandomState` → L2-normalise)
- **SQLite connections** use `check_same_thread=False` for thread-safe FastAPI use
- **FAISS IndexFlatIP** stores L2-normalised vectors so inner product == cosine similarity
- **Symptom codes** (`PRB-*`) and **repair codes** (`RP-*`) are from the JSON layer;
  the SQLite DB uses its own `sym_*` / `rep_*` codes — both schemes are supported
  by the engine lookup methods

### Adding a new knowledge base version

1. Create `Version_4/` with the standard subdirectory structure
2. Add DB configuration to `_VERSION_CONFIG` in all three engine files
3. Add `4: {...}` to `VERSION_META` in `fixfinder.py`
4. Add `"4.0"` to `_VALID_VERSIONS` in `api_server.py` and `v2_routes.py`
5. Run `python scripts/master_build.py --version 4`

---

## Roadmap

### Near-term
- [ ] **Real sentence embeddings** — replace synthetic SHA-256 embeddings with
  a real model (e.g. `sentence-transformers/all-MiniLM-L6-v2`) for true semantic
  similarity
- [ ] **Larger knowledge bases** — expand each version to 500+ systems, 2000+ symptoms
- [ ] **IVF FAISS index** — switch from `IndexFlatIP` to `IndexIVFFlat` for
  sub-linear search as vector count grows
- [ ] **Streaming responses** — Server-Sent Events for step-by-step repair walkthroughs
- [ ] **Redis rate limiting** — replace in-process token bucket for multi-replica deployments

### Medium-term
- [ ] **Version 4 — Marine / Boating** — engines, outboards, bilge pumps
- [ ] **Version 5 — HVAC / Commercial** — chillers, AHUs, building automation
- [ ] **Multilingual support** — leverage existing `translations` table in DB
- [ ] **Repair record tracking** — populate `repair_records` table with outcomes
- [ ] **Analytics dashboard** — visualise `analytics_events` table data

### Long-term
- [ ] **LLM integration** — connect `ai_prompts` table to a local or cloud LLM
  for natural-language repair explanations
- [ ] **Mobile SDK** — React Native or Flutter wrapper for offline field use
- [ ] **Parts ordering integration** — link `parts_inventory` to supplier APIs
- [ ] **Computer vision** — photo-based symptom identification

---

## License

This project is proprietary software. All rights reserved.

---

## Contributing

1. Run the full build before submitting: `python scripts/master_build.py`
2. All 230 tests must pass: `pytest tests/ -v`
3. All 285 validation checks must pass: `python scripts/validation_suite.py`
4. Follow existing code style (type hints, docstrings, context managers)

---

*Built with Python 3.12 · FastAPI · FAISS · SQLite · NumPy · Pydantic*
