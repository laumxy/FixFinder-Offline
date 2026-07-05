#!/usr/bin/env bash
# =============================================================================
# docker_build.sh — FixFinder Docker build & run helper
# =============================================================================
#
# Usage:
#   ./docker_build.sh              # build image + start stack (detached)
#   ./docker_build.sh build        # build image only
#   ./docker_build.sh run          # run pre-built image
#   ./docker_build.sh dev          # run with live log streaming
#   ./docker_build.sh stop         # stop running containers
#   ./docker_build.sh clean        # stop + remove containers + volumes
#   ./docker_build.sh logs         # tail container logs
#   ./docker_build.sh health       # query /health endpoint
#   ./docker_build.sh shell        # open a shell inside the running container
#   ./docker_build.sh rebuild      # force full rebuild (no cache)
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
IMAGE_NAME="fixfinder"
IMAGE_TAG="${FIXFINDER_VERSION:-latest}"
CONTAINER_NAME="fixfinder_api"
API_PORT="${API_PORT:-8000}"
COMPOSE_FILE="docker-compose.yml"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $*"; }
ok()   { echo -e "${GREEN}[OK]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }
err()  { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()  { err "$*"; exit 1; }

# ── Prerequisite check ────────────────────────────────────────────────────────
check_prerequisites() {
    log "Checking prerequisites …"
    command -v docker      >/dev/null 2>&1 || die "docker not found — install Docker Desktop or Docker Engine."
    command -v docker      >/dev/null 2>&1 && docker info >/dev/null 2>&1 || die "Docker daemon is not running."

    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        die "Neither 'docker compose' nor 'docker-compose' found."
    fi

    ok "Prerequisites OK  (${COMPOSE_CMD})"
}

# ── Build ─────────────────────────────────────────────────────────────────────
cmd_build() {
    log "Building image ${BOLD}${IMAGE_NAME}:${IMAGE_TAG}${RESET} …"
    docker build \
        --tag  "${IMAGE_NAME}:${IMAGE_TAG}" \
        --file Dockerfile \
        --progress=plain \
        .
    ok "Image built: ${IMAGE_NAME}:${IMAGE_TAG}"
    docker images "${IMAGE_NAME}:${IMAGE_TAG}"
}

# ── Rebuild (no cache) ────────────────────────────────────────────────────────
cmd_rebuild() {
    log "Force-rebuilding (no cache) …"
    docker build \
        --no-cache \
        --tag  "${IMAGE_NAME}:${IMAGE_TAG}" \
        --file Dockerfile \
        --progress=plain \
        .
    ok "Rebuild complete."
}

# ── Run (compose) ─────────────────────────────────────────────────────────────
cmd_run() {
    log "Starting FixFinder stack (detached) …"
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up --build --detach
    echo ""
    ok "Stack started."
    echo -e "  ${BOLD}API:${RESET}    http://localhost:${API_PORT}"
    echo -e "  ${BOLD}Docs:${RESET}   http://localhost:${API_PORT}/docs"
    echo -e "  ${BOLD}Health:${RESET} http://localhost:${API_PORT}/health"
    echo ""
    log "Waiting for health check (up to 120s) …"
    _wait_healthy
}

# ── Dev (foreground with streaming logs) ──────────────────────────────────────
cmd_dev() {
    log "Starting in DEV mode (foreground) — press Ctrl+C to stop"
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up --build
}

# ── Stop ──────────────────────────────────────────────────────────────────────
cmd_stop() {
    log "Stopping containers …"
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" stop
    ok "Containers stopped."
}

# ── Clean ─────────────────────────────────────────────────────────────────────
cmd_clean() {
    warn "This will remove containers AND named volumes (data will be lost)."
    read -r -p "Continue? [y/N] " confirm
    [[ "${confirm,,}" == "y" ]] || { log "Aborted."; exit 0; }
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" down --volumes --remove-orphans
    ok "Containers and volumes removed."
}

# ── Logs ──────────────────────────────────────────────────────────────────────
cmd_logs() {
    ${COMPOSE_CMD} -f "${COMPOSE_FILE}" logs --follow --tail=100 api
}

# ── Health ────────────────────────────────────────────────────────────────────
cmd_health() {
    log "Querying http://localhost:${API_PORT}/health …"
    if command -v curl >/dev/null 2>&1; then
        curl -s "http://localhost:${API_PORT}/health" | python3 -m json.tool
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "
import urllib.request, json
r = urllib.request.urlopen('http://localhost:${API_PORT}/health')
print(json.dumps(json.load(r), indent=2))
"
    else
        die "Neither curl nor python3 found for health check."
    fi
}

# ── Shell ─────────────────────────────────────────────────────────────────────
cmd_shell() {
    log "Opening shell in ${CONTAINER_NAME} …"
    docker exec -it "${CONTAINER_NAME}" /bin/bash \
        || docker exec -it "${CONTAINER_NAME}" /bin/sh
}

# ── Wait for healthy ─────────────────────────────────────────────────────────
_wait_healthy() {
    local max=24   # 24 × 5s = 120s
    local n=0
    while [[ $n -lt $max ]]; do
        if docker inspect --format='{{.State.Health.Status}}' \
               "${CONTAINER_NAME}" 2>/dev/null | grep -q "healthy"; then
            ok "Container is healthy!"
            return 0
        fi
        n=$(( n + 1 ))
        echo -n "."
        sleep 5
    done
    echo ""
    warn "Container did not become healthy within 120s."
    warn "Run:  ./docker_build.sh logs  to investigate."
    return 1
}

# ── Entry point ───────────────────────────────────────────────────────────────
main() {
    local cmd="${1:-run}"

    echo ""
    echo -e "${BOLD}${CYAN}=====================================${RESET}"
    echo -e "${BOLD}${CYAN}  FixFinder Docker Build Tool${RESET}"
    echo -e "${BOLD}${CYAN}=====================================${RESET}"
    echo ""

    check_prerequisites

    case "${cmd}" in
        build)   cmd_build   ;;
        rebuild) cmd_rebuild ;;
        run)     cmd_run     ;;
        dev)     cmd_dev     ;;
        stop)    cmd_stop    ;;
        clean)   cmd_clean   ;;
        logs)    cmd_logs    ;;
        health)  cmd_health  ;;
        shell)   cmd_shell   ;;
        *)
            err "Unknown command: ${cmd}"
            echo "Usage: $0 {build|rebuild|run|dev|stop|clean|logs|health|shell}"
            exit 1
            ;;
    esac
}

main "$@"
