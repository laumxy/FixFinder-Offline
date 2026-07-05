"""
api_server.py
=============
FixFinder Standalone FastAPI Server.

Wraps all three AI engines (Retrieval, Diagnostic, Repair Reasoning) behind
a single, self-contained REST API.  No external auth or queue service required —
everything runs from the versioned SQLite databases and FAISS indices on disk.

Architecture
------------
  • Three engine pools (one instance per version, lazily loaded, thread-safe)
  • In-process token-bucket rate limiter (no external dependency)
  • CORS middleware configured for local + production origins
  • Structured JSON error responses throughout
  • OpenAPI docs at /docs  (Swagger UI)
  • ReDoc at           /redoc

Endpoints
---------
  GET  /                         – API info
  GET  /health                   – engine health + rate-limit stats
  POST /search                   – semantic FAISS search (all versions)
  POST /diagnose                 – symptom analysis + tree traversal
  POST /repair-plan              – full repair plan (recs + parts + cost)
  GET  /systems/{system_id}      – system details from SQLite
  GET  /symptoms/{symptom_id}    – symptom details from SQLite
  GET  /repairs/{repair_id}      – repair procedure from SQLite

Run
---
  # default (port 8000)
  python api_server.py

  # custom port / host
  python api_server.py --host 0.0.0.0 --port 9000

  # reload on file change (dev mode)
  python api_server.py --reload

  # via uvicorn directly
  uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Root / sys.path so engines import cleanly wherever this file is run from
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ai_engine.retrieval_engine        import AIRetrievalEngine        # noqa: E402
from ai_engine.diagnostic_engine       import AIDiagnosticEngine       # noqa: E402
from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt = "%H:%M:%S",
)
log = logging.getLogger("api_server")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_VERSIONS = {1, 2, 3}
_VERSION_LABELS = {
    1: "Home Maintenance",
    2: "Electronics",
    3: "Industrial / Automotive",
}

_API_VERSION   = "2.0.0"
_API_TITLE     = "FixFinder AI Engine API"
_API_DESC      = (
    "Standalone REST API for the FixFinder AI engines.  "
    "Provides semantic search, guided diagnosis, and full repair planning "
    "across three versioned knowledge bases."
)

# ===========================================================================
# Rate limiter  (token-bucket, in-process, no external dependency)
# ===========================================================================

class _TokenBucket:
    """
    Per-client token-bucket rate limiter stored in a shared dict.

    Default: 60 requests / 60 seconds per IP address.
    """

    def __init__(self, rate: int = 60, period: float = 60.0) -> None:
        self._rate   = rate       # max tokens
        self._period = period     # refill window in seconds
        self._lock   = threading.Lock()
        # {client_ip: [tokens_remaining, last_refill_timestamp]}
        self._buckets: dict[str, list[float]] = defaultdict(
            lambda: [float(rate), time.monotonic()]
        )
        self._request_counts: dict[str, int] = defaultdict(int)

    def is_allowed(self, client_ip: str) -> tuple[bool, int, int]:
        """
        Check if the request is allowed.

        Returns (allowed, remaining_tokens, retry_after_seconds).
        """
        with self._lock:
            bucket = self._buckets[client_ip]
            tokens, last_refill = bucket

            # Refill
            elapsed = time.monotonic() - last_refill
            refill  = elapsed * (self._rate / self._period)
            tokens  = min(self._rate, tokens + refill)
            bucket[1] = time.monotonic()

            if tokens >= 1:
                tokens -= 1
                bucket[0] = tokens
                self._request_counts[client_ip] += 1
                return True, int(tokens), 0
            else:
                bucket[0] = tokens
                retry_after = int((1 - tokens) * self._period / self._rate) + 1
                return False, 0, retry_after

    def stats(self) -> dict:
        with self._lock:
            return {
                "rate_limit":        self._rate,
                "period_seconds":    self._period,
                "active_clients":    len(self._buckets),
                "total_requests":    sum(self._request_counts.values()),
            }


_limiter = _TokenBucket(rate=60, period=60.0)


# ===========================================================================
# Engine pool  (lazy, thread-safe)
# ===========================================================================

_engine_lock      = threading.Lock()
_retrieval_pool:  dict[int, AIRetrievalEngine]        = {}
_diagnostic_pool: dict[int, AIDiagnosticEngine]       = {}
_repair_pool:     dict[int, AIRepairReasoningEngine]   = {}
_engine_errors:   dict[str, str]                      = {}   # for health reporting


def _get_retrieval(version: int) -> AIRetrievalEngine:
    with _engine_lock:
        if version not in _retrieval_pool:
            log.info("Loading AIRetrievalEngine v%d …", version)
            _retrieval_pool[version] = AIRetrievalEngine(version=version)
    return _retrieval_pool[version]


def _get_diagnostic(version: int) -> AIDiagnosticEngine:
    with _engine_lock:
        if version not in _diagnostic_pool:
            log.info("Loading AIDiagnosticEngine v%d …", version)
            _diagnostic_pool[version] = AIDiagnosticEngine(version=version)
    return _diagnostic_pool[version]


def _get_repair(version: int) -> AIRepairReasoningEngine:
    with _engine_lock:
        if version not in _repair_pool:
            log.info("Loading AIRepairReasoningEngine v%d …", version)
            _repair_pool[version] = AIRepairReasoningEngine(version=version)
    return _repair_pool[version]


def _preload_all_engines() -> None:
    """Pre-load all 9 engine instances at startup to avoid cold-start on first request."""
    for v in _VALID_VERSIONS:
        for loader, label in (
            (_get_retrieval,  "retrieval"),
            (_get_diagnostic, "diagnostic"),
            (_get_repair,     "repair"),
        ):
            key = f"v{v}_{label}"
            try:
                loader(v)
                log.info("  [OK] %s", key)
            except Exception as exc:
                _engine_errors[key] = str(exc)
                log.warning("  [WARN] %s failed to load: %s", key, exc)


# ===========================================================================
# Lifespan
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 56)
    log.info("  FixFinder API Server  v%s", _API_VERSION)
    log.info("=" * 56)
    log.info("Pre-loading all AI engines …")
    t = threading.Thread(target=_preload_all_engines, daemon=True, name="engine-preload")
    t.start()
    yield
    # Shutdown: close all SQLite connections
    log.info("Shutting down — releasing engine resources …")
    with _engine_lock:
        for eng in list(_retrieval_pool.values()):
            try: eng.close()
            except Exception: pass
        for eng in list(_diagnostic_pool.values()):
            try: eng.close()
            except Exception: pass
        for eng in list(_repair_pool.values()):
            try: eng.close()
            except Exception: pass
    log.info("Shutdown complete.")


# ===========================================================================
# App factory
# ===========================================================================

def create_app() -> FastAPI:
    application = FastAPI(
        title       = _API_TITLE,
        version     = _API_VERSION,
        description = _API_DESC,
        lifespan    = lifespan,
        docs_url    = "/docs",
        redoc_url   = "/redoc",
        openapi_url = "/openapi.json",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins     = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ],
        allow_credentials = True,
        allow_methods     = ["GET", "POST", "OPTIONS"],
        allow_headers     = ["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers    = ["X-RateLimit-Limit", "X-RateLimit-Remaining",
                             "X-RateLimit-Reset", "X-Process-Time"],
    )

    # ── Rate-limit + timing middleware ─────────────────────────────────────
    @application.middleware("http")
    async def _rate_limit_and_timing(request: Request, call_next):
        start = time.perf_counter()

        # Derive client IP (respects X-Forwarded-For when behind a proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )

        # Skip rate limiting on health / docs / openapi routes
        path = request.url.path
        skip_limit = path in ("/health", "/docs", "/redoc", "/openapi.json", "/")

        if not skip_limit:
            allowed, remaining, retry_after = _limiter.is_allowed(client_ip)
            if not allowed:
                return JSONResponse(
                    status_code = 429,
                    content     = {
                        "error":       "Too Many Requests",
                        "message":     f"Rate limit exceeded. Retry after {retry_after}s.",
                        "retry_after": retry_after,
                    },
                    headers = {
                        "Retry-After":           str(retry_after),
                        "X-RateLimit-Limit":     str(_limiter._rate),
                        "X-RateLimit-Remaining": "0",
                    },
                )

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"

        if not skip_limit:
            _, rem, _ = _limiter.is_allowed.__wrapped__(client_ip) \
                if hasattr(_limiter.is_allowed, "__wrapped__") else (True, 0, 0)
            response.headers["X-RateLimit-Limit"]     = str(_limiter._rate)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    return application


app = create_app()


# ===========================================================================
# Request / Response models
# ===========================================================================

class SearchRequest(BaseModel):
    """Search request across all three knowledge bases."""
    query:   str = Field(..., min_length=2, max_length=1000,
                         example="roof leaking after heavy rain near chimney")
    top_k:   int = Field(default=5, ge=1, le=20,
                         description="Max results to return per version")
    version: Optional[int] = Field(
        default=None,
        description="Restrict to version 1, 2, or 3 (default: search all)",
    )
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter to 'system', 'symptom', or 'repair'",
    )


class DiagnosticRequest(BaseModel):
    """Free-text symptom description plus optional guided-diagnosis inputs."""
    user_input: str = Field(..., min_length=3, max_length=2000,
                            example="electrical outlet stopped working in bathroom")
    version:    int = Field(..., ge=1, le=3,
                            description="Knowledge base version: 1, 2, or 3")
    top_k:      int = Field(default=5, ge=1, le=10,
                            description="Max symptom matches to return")
    symptom_code: Optional[str] = Field(
        default=None,
        description="If known, skip analysis and go straight to this symptom code",
    )
    responses: list[str] = Field(
        default=[],
        description="Yes/no answers for guided tree traversal (leave empty to skip)",
    )


class RepairRequest(BaseModel):
    """Repair plan request — wraps a symptom + optional prior diagnostic result."""
    symptom_code:      str  = Field(..., min_length=2, max_length=64,
                                    example="PRB-ROF-002")
    version:           int  = Field(..., ge=1, le=3)
    diagnostic_result: Optional[dict] = Field(
        default=None,
        description="Output from POST /diagnose to guide repair matching",
    )
    top_k:             int  = Field(default=3, ge=1, le=5)


def _validate_version(version: int) -> None:
    if version not in _VALID_VERSIONS:
        raise HTTPException(
            status_code = 422,
            detail      = f"version must be 1, 2, or 3 — got {version}",
        )


def _engine_error(exc: Exception, action: str) -> HTTPException:
    log.error("Engine error in %s: %s", action, exc, exc_info=True)
    return HTTPException(
        status_code = 500,
        detail      = {
            "error":   "Engine error",
            "action":  action,
            "message": f"{type(exc).__name__}: {exc}",
        },
    )


# ===========================================================================
# Endpoints
# ===========================================================================

# ── Root ────────────────────────────────────────────────────────────────────

@app.get(
    "/",
    summary       = "API info",
    tags          = ["Meta"],
    response_model= None,
)
def root() -> dict:
    """
    Returns API metadata, available versions, and the full endpoint map.
    No authentication required.
    """
    return {
        "api":         _API_TITLE,
        "version":     _API_VERSION,
        "description": _API_DESC,
        "versions": {
            "1": "Home Maintenance",
            "2": "Electronics",
            "3": "Industrial / Automotive",
        },
        "endpoints": {
            "GET  /":                      "This info page",
            "GET  /health":                "Engine health check",
            "POST /search":                "Semantic FAISS search (one or all versions)",
            "POST /diagnose":              "Symptom analysis + guided tree traversal",
            "POST /repair-plan":           "Full repair plan (recs + parts + cost)",
            "GET  /systems/{id}?version=": "System details from SQLite",
            "GET  /symptoms/{id}?version=":"Symptom details from SQLite",
            "GET  /repairs/{id}?version=": "Repair procedure from SQLite",
        },
        "docs":  "/docs",
        "redoc": "/redoc",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Health ───────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    summary = "Health check",
    tags    = ["Meta"],
)
def health() -> dict:
    """
    Checks that all nine engine instances (3 versions × 3 engines) are loaded
    and accessible.  Reports load errors without raising HTTP 500.
    Reports rate-limiter statistics.
    """
    result: dict[str, Any] = {
        "status":    "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_version": _API_VERSION,
        "rate_limiter": _limiter.stats(),
        "versions": {},
    }
    all_ok = True

    for v in sorted(_VALID_VERSIONS):
        vs: dict[str, Any] = {"label": _VERSION_LABELS[v]}

        for pool, label, loader in (
            (_retrieval_pool,  "retrieval",  _get_retrieval),
            (_diagnostic_pool, "diagnostic", _get_diagnostic),
            (_repair_pool,     "repair",     _get_repair),
        ):
            key = f"v{v}_{label}"
            if key in _engine_errors:
                vs[label] = {"ok": False, "error": _engine_errors[key]}
                all_ok = False
            elif v in pool:
                extra: dict = {}
                if label == "retrieval":
                    eng = pool[v]
                    extra = {
                        "vectors": eng._faiss_meta.get("total_entries")
                                   if eng._faiss_meta else None,
                        "dim":     eng._dimension,
                    }
                vs[label] = {"ok": True, **extra}
            else:
                vs[label] = {"ok": False, "error": "not loaded yet (warm-up in progress)"}
                all_ok = False

        result["versions"][str(v)] = vs

    if not all_ok:
        result["status"] = "degraded"

    return result


# ── Search ────────────────────────────────────────────────────────────────────

@app.post(
    "/search",
    summary = "Semantic search",
    tags    = ["Retrieval"],
)
def search(body: SearchRequest) -> dict:
    """
    Embeds the query with SHA-256 synthetic embeddings and runs cosine-similarity
    search over FAISS.

    - If `version` is supplied, searches only that version.
    - Otherwise searches all three versions and returns a combined ranked list.
    - Optional `entity_type` filter: `"system"`, `"symptom"`, or `"repair"`.
    """
    target_versions = [body.version] if body.version else sorted(_VALID_VERSIONS)

    all_results: list[dict] = []
    errors: list[dict]      = []

    for v in target_versions:
        try:
            eng     = _get_retrieval(v)
            results = eng.search(
                query_text         = body.query,
                top_k              = body.top_k,
                entity_type_filter = body.entity_type,
            )
            for r in results:
                r["version"]       = v
                r["version_label"] = _VERSION_LABELS[v]
            all_results.extend(results)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            errors.append({"version": v, "error": str(exc)})
            log.warning("Search failed for v%d: %s", v, exc)

    # Re-rank globally by score when multiple versions were searched
    if len(target_versions) > 1:
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:body.top_k]
        for i, r in enumerate(all_results):
            r["rank"] = i + 1

    return {
        "query":          body.query,
        "entity_type":    body.entity_type,
        "versions_searched": target_versions,
        "total_results":  len(all_results),
        "results":        all_results,
        "errors":         errors or None,
    }


# ── Diagnose ──────────────────────────────────────────────────────────────────

@app.post(
    "/diagnose",
    summary = "Symptom analysis + guided diagnosis",
    tags    = ["Diagnostic"],
)
def diagnose(body: DiagnosticRequest) -> dict:
    """
    Two-stage diagnostic:

    **Stage 1 — Symptom Analysis** (`analyze_symptoms`):
    Tokenises `user_input` and returns the top-k matching symptoms from the
    SQLite symptoms table, ranked by weighted keyword overlap.

    **Stage 2 — Tree Traversal** (optional, triggered when `symptom_code` is
    provided or a high-confidence match is found):
    Walks the diagnostic decision tree for the identified symptom, consuming
    each entry in `responses` (yes/no) as an answer to each decision point.
    Returns the traversal trace, `recommended_action`, and `repair_code` if
    reached.
    """
    _validate_version(body.version)

    try:
        diag_eng = _get_diagnostic(body.version)

        # Stage 1 — analyse
        matches = diag_eng.analyze_symptoms(body.user_input, top_k=body.top_k)

        # Stage 2 — tree traversal
        tree_result: Optional[dict] = None
        chosen_code = body.symptom_code

        # Auto-pick the top symptom match if no code given but high confidence
        if not chosen_code and matches:
            top_score = matches[0]["score"]
            if top_score >= 0.15:                    # confidence threshold
                chosen_code = matches[0]["symptom_code"]

        if chosen_code and (body.responses or body.symptom_code):
            tree_result = diag_eng.run_diagnostic(
                symptom_code   = chosen_code,
                user_responses = body.responses,
            )

        return {
            "version":       body.version,
            "version_label": _VERSION_LABELS[body.version],
            "user_input":    body.user_input,
            "symptom_analysis": {
                "total_matches": len(matches),
                "matches":       matches,
            },
            "diagnostic_tree": tree_result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _engine_error(exc, "diagnose")


# ── Repair Plan ───────────────────────────────────────────────────────────────

@app.post(
    "/repair-plan",
    summary = "Full repair plan",
    tags    = ["Repair"],
)
def repair_plan(body: RepairRequest) -> dict:
    """
    End-to-end repair plan for a symptom:

    1. Finds the best matching repair procedures (ranked by relevance → difficulty).
    2. Checks parts availability in `parts_inventory`.
    3. Calculates total estimated time and parts cost.
    4. Returns ordered `plan_steps` (pre-checks → tools → procedure → post-checks
       → warnings) and urgency classification.

    Pass the output from `POST /diagnose` as `diagnostic_result` to improve
    repair-code matching accuracy.
    """
    _validate_version(body.version)

    try:
        plan = _get_repair(body.version).generate_repair_plan(
            symptom_code      = body.symptom_code,
            diagnostic_result = body.diagnostic_result,
            top_k             = body.top_k,
        )
        return {
            "version":       body.version,
            "version_label": _VERSION_LABELS[body.version],
            **plan,
        }
    except Exception as exc:
        raise _engine_error(exc, "repair-plan")


# ── Entity detail lookups ─────────────────────────────────────────────────────

@app.get(
    "/systems/{system_id}",
    summary = "System details",
    tags    = ["Retrieval"],
)
def get_system(
    system_id: str = Path(..., min_length=1, max_length=64,
                          description="system_code e.g. ROF-001 or partial name"),
    version:   int = Query(..., ge=1, le=3,
                           description="Knowledge base version"),
) -> dict:
    """
    Fetch full system info from SQLite.
    Looks up by `system_code` first, then falls back to a partial name match.
    """
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_system_details(system_id)
    except Exception as exc:
        raise _engine_error(exc, "get_system_details")
    if result is None:
        raise HTTPException(
            status_code = 404,
            detail      = f"System '{system_id}' not found in version {version}.",
        )
    return result


@app.get(
    "/symptoms/{symptom_id}",
    summary = "Symptom details",
    tags    = ["Retrieval"],
)
def get_symptom(
    symptom_id: str = Path(..., min_length=1, max_length=64,
                           description="symptom_code e.g. PRB-ROF-002 or partial name"),
    version:    int = Query(..., ge=1, le=3),
) -> dict:
    """
    Fetch full symptom info from SQLite.
    Looks up by `symptom_code` first, then falls back to a partial name match.
    """
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_symptom_details(symptom_id)
    except Exception as exc:
        raise _engine_error(exc, "get_symptom_details")
    if result is None:
        raise HTTPException(
            status_code = 404,
            detail      = f"Symptom '{symptom_id}' not found in version {version}.",
        )
    return result


@app.get(
    "/repairs/{repair_id}",
    summary = "Repair procedure details",
    tags    = ["Retrieval"],
)
def get_repair(
    repair_id: str = Path(..., min_length=1, max_length=64,
                          description="repair_code e.g. rep_roof_shingle or partial name"),
    version:   int = Query(..., ge=1, le=3),
) -> dict:
    """
    Fetch a full repair procedure from SQLite.
    Looks up by `repair_code` first, then falls back to a partial name match.
    """
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_repair_procedure(repair_id)
    except Exception as exc:
        raise _engine_error(exc, "get_repair_procedure")
    if result is None:
        raise HTTPException(
            status_code = 404,
            detail      = f"Repair '{repair_id}' not found in version {version}.",
        )
    return result


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = "FixFinder AI Engine — standalone API server",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",   default="127.0.0.1",
                        help="Bind host address")
    parser.add_argument("--port",
                        default=int(os.environ.get("PORT", 8000)),
                        type=int,
                        help="Bind port (default: $PORT env var, then 8000)")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload on file changes (dev mode)")
    parser.add_argument("--workers", default=1, type=int,
                        help="Number of Uvicorn worker processes")
    parser.add_argument("--log-level", default="info",
                        choices=["debug", "info", "warning", "error"],
                        help="Uvicorn log level")
    args = parser.parse_args()

    print(f"\n  FixFinder API Server  v{_API_VERSION}")
    print(f"  Listening on  http://{args.host}:{args.port}")
    print(f"  Swagger UI    http://{args.host}:{args.port}/docs")
    print(f"  ReDoc         http://{args.host}:{args.port}/redoc\n")

    uvicorn.run(
        "api_server:app",
        host      = args.host,
        port      = args.port,
        reload    = args.reload,
        workers   = args.workers if not args.reload else 1,
        log_level = args.log_level,
    )
