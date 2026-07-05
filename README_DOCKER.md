# FixFinder — Docker Setup Guide

FixFinder ships as a self-contained Docker image that bundles all three
versioned knowledge bases (Home Maintenance, Electronics, Industrial /
Automotive) and exposes them through a single REST API.

---

## Quick Start

```bash
# Clone / navigate to the project root
cd "FixFinder Backend"

# Build and start (detached)
./docker_build.sh

# Verify the API is running
curl http://localhost:8000/health
```

The API is now available at **http://localhost:8000** with interactive docs
at **http://localhost:8000/docs**.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Docker Engine | 24.x | Desktop or Engine |
| Docker Compose | v2 (plugin) or v1 (standalone) | `docker compose` or `docker-compose` |
| Free disk space | ~4 GB | Image + volumes |
| Free RAM | 2 GB | 4 GB recommended |

---

## File Overview

```
FixFinder Backend/
├── Dockerfile          Multi-stage build (builder → data-prep → runtime)
├── docker-compose.yml  Service + volume definitions
├── .dockerignore       Files excluded from the build context
├── docker_build.sh     Build/run helper script (Linux / macOS / WSL)
└── README_DOCKER.md    This file
```

---

## Build Commands

### Using `docker_build.sh` (recommended)

```bash
chmod +x docker_build.sh          # make executable (first time only)

./docker_build.sh                  # build image + start stack (detached)
./docker_build.sh build            # build image only, no start
./docker_build.sh rebuild          # force full rebuild — no Docker cache
./docker_build.sh run              # start pre-built stack (detached)
./docker_build.sh dev              # start with live log streaming (foreground)
./docker_build.sh stop             # stop running containers
./docker_build.sh clean            # stop + remove containers AND volumes
./docker_build.sh logs             # tail container logs
./docker_build.sh health           # query /health endpoint
./docker_build.sh shell            # open a bash shell inside the container
```

### Using Docker directly

```bash
# Build image
docker build -t fixfinder:latest .

# Run container
docker run -d \
  --name fixfinder_api \
  -p 8000:8000 \
  -e FIXFINDER_ENV=production \
  fixfinder:latest

# View logs
docker logs -f fixfinder_api

# Stop
docker stop fixfinder_api && docker rm fixfinder_api
```

### Using Docker Compose directly

```bash
docker compose up --build -d        # build + start detached
docker compose logs -f api          # follow logs
docker compose down                 # stop + remove containers
docker compose down -v              # also delete named volumes
```

---

## Environment Variables

Set these in a `.env` file next to `docker-compose.yml` or pass via
`-e KEY=VALUE` on the command line.

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8000` | Host port mapped to container port 8000 |
| `FIXFINDER_ENV` | `production` | Environment label (`development`, `production`) |
| `FIXFINDER_LOG_LEVEL` | `info` | Uvicorn log level (`debug`, `info`, `warning`, `error`) |
| `RATE_LIMIT_REQUESTS` | `60` | Max requests allowed per period per IP |
| `RATE_LIMIT_PERIOD` | `60` | Rate-limit window in seconds |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | Comma-separated CORS origins |

**Example `.env` file:**

```env
API_PORT=8000
FIXFINDER_ENV=production
FIXFINDER_LOG_LEVEL=info
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_PERIOD=60
ALLOWED_ORIGINS=https://your-frontend.com,http://localhost:3000
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API info + endpoint map |
| `GET` | `/health` | Engine health + rate-limiter stats |
| `POST` | `/search` | Semantic FAISS search (one or all versions) |
| `POST` | `/diagnose` | Symptom analysis + guided tree traversal |
| `POST` | `/repair-plan` | Full repair plan (recs + parts + cost + steps) |
| `GET` | `/systems/{id}?version=N` | System details from SQLite |
| `GET` | `/symptoms/{id}?version=N` | Symptom details from SQLite |
| `GET` | `/repairs/{id}?version=N` | Repair procedure from SQLite |

Interactive Swagger UI: **http://localhost:8000/docs**

**Quick test:**

```bash
# Search across all versions
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "roof leaking after rain", "top_k": 5}' \
  | python3 -m json.tool

# Full repair plan for a symptom
curl -s -X POST http://localhost:8000/repair-plan \
  -H "Content-Type: application/json" \
  -d '{"symptom_code": "PRB-ROF-002", "version": 1}' \
  | python3 -m json.tool
```

---

## Volumes

Named Docker volumes are used to persist data across container restarts.

| Volume | Mount path | Contents |
|--------|-----------|----------|
| `fixfinder_v1_data` | `/app/Version_1` | Home Maintenance DB, embeddings, FAISS |
| `fixfinder_v2_data` | `/app/Version_2` | Electronics DB, embeddings, FAISS |
| `fixfinder_v3_data` | `/app/Version_3` | Industrial DB, embeddings, FAISS |
| `fixfinder_logs` | `/app/logs` | Application logs |

To inspect a volume:

```bash
docker volume inspect fixfinder_v1_data
```

To back up a volume:

```bash
docker run --rm \
  -v fixfinder_v1_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/v1_backup.tar.gz /data
```

---

## Troubleshooting

### Container exits immediately

```bash
docker logs fixfinder_api
```

Common causes:
- **Port 8000 already in use** — change `API_PORT` in `.env` or stop the
  conflicting service.
- **Insufficient memory** — increase Docker Desktop memory allocation to
  at least 4 GB.
- **Missing data files** — ensure the `Version_*/03_SQLite_Database/*.db`
  files were generated before building the image (run `python master_import.py`).

### Health check fails / stays "starting"

The engines load all FAISS indices and SQLite connections at startup.
Allow up to **120 seconds** for the container to become healthy.

```bash
# Watch health status
watch docker inspect --format='{{.State.Health.Status}}' fixfinder_api

# Check engine status directly
curl http://localhost:8000/health | python3 -m json.tool
```

### FAISS import error inside container

The image installs `faiss-cpu`. If you see an import error, confirm the
build completed successfully:

```bash
docker exec fixfinder_api python -c "import faiss; print(faiss.__version__)"
```

### Slow cold start

The AI engines (FAISS index + SQLite) load lazily on first request.
The health check `start_period` is set to **120 seconds** to account for this.
Subsequent requests are fast once engines are warm.

### Reset everything

```bash
./docker_build.sh clean         # removes containers + volumes
./docker_build.sh rebuild       # full rebuild — no cache
```

### Windows (without WSL)

`docker_build.sh` is a Bash script. On Windows without WSL, use the
Docker commands directly:

```powershell
# Build
docker build -t fixfinder:latest .

# Run
docker run -d --name fixfinder_api -p 8000:8000 fixfinder:latest

# Logs
docker logs -f fixfinder_api
```

Or use **Git Bash** / **WSL 2** to run `./docker_build.sh` natively.

---

## Build Time Estimates

| Step | Approximate time |
|------|-----------------|
| Python base image pull | 1–2 min (first time) |
| Wheel compilation (faiss-cpu, numpy) | 3–8 min |
| CSV + JSON generation | < 30 s |
| Embedding generation (3 × 30 vectors) | < 30 s |
| FAISS index build | < 10 s |
| **Total (first build)** | **5–12 min** |
| **Subsequent builds (cached)** | **< 1 min** |

---

## Deployment Notes

- The `Dockerfile` and `railway.toml` are already configured for
  **Railway** deployment. Push to Railway and it will detect the Dockerfile
  automatically.
- For **production** deployments behind a reverse proxy (nginx, Caddy),
  set `ALLOWED_ORIGINS` to your frontend domain and bind to
  `0.0.0.0` inside the container (already the default).
- The rate limiter is in-process (per container). For multi-replica
  deployments, use Redis-backed rate limiting instead.
