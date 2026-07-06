"""
app/api/v2_routes.py
=====================
FixFinder v2 AI Engine REST API.

Exposes the three versioned AI engines (Retrieval, Diagnostic, Repair
Reasoning) as clean REST endpoints under the /v2 prefix.  The original
/diagnose pipeline is untouched.

Mount point: /v2
Auth:        all endpoints are public (no Bearer token required) so that
             the engines can be tested without an auth setup.  Individual
             routes can add Depends(_require_auth) when needed.

Endpoint map
------------
  GET  /v2/                        – version info & endpoint list
  GET  /v2/health                  – engine health check for all versions

  # ── Retrieval ──────────────────────────────────────────────────────
  POST /v2/{version}/search        – semantic FAISS search
  GET  /v2/{version}/systems/{id}  – system details from SQLite
  GET  /v2/{version}/symptoms/{id} – symptom details from SQLite
  GET  /v2/{version}/repairs/{id}  – repair procedure from SQLite

  # ── Diagnostic ─────────────────────────────────────────────────────
  POST /v2/{version}/analyze       – match symptoms from free text
  GET  /v2/{version}/tree/{code}   – load a diagnostic tree by symptom code
  POST /v2/{version}/diagnose      – run guided tree traversal

  # ── Repair Reasoning ───────────────────────────────────────────────
  POST /v2/{version}/recommend     – ranked repair recommendations
  GET  /v2/{version}/parts/{id}    – parts availability for a repair
  POST /v2/{version}/plan          – full repair plan (recs + parts + cost)
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ai_engine.retrieval_engine        import AIRetrievalEngine
from ai_engine.diagnostic_engine       import AIDiagnosticEngine
from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine
from ai_engine.rqu_engine              import RQUEngine
from ai_engine.ice_engine              import ICEEngine
from ai_engine.cie_engine              import ComponentIdentifier
from ai_engine.tee_engine              import TechnicalEntityExtractor
from ai_engine.equipment_engine        import EquipmentResolver

router = APIRouter(prefix="/v2", tags=["AI Engine v2"])

# ---------------------------------------------------------------------------
# Engine pool – one instance per version, lazily loaded, thread-safe
# ---------------------------------------------------------------------------

_engine_lock   = threading.Lock()
_retrieval_pool: dict[int, AIRetrievalEngine]        = {}
_diagnostic_pool: dict[int, AIDiagnosticEngine]      = {}
_repair_pool:  dict[int, AIRepairReasoningEngine]     = {}

# RQU / ICE / CIE — stateless, one shared instance each
_rqu = RQUEngine()
_ice = ICEEngine()
_cie = ComponentIdentifier()
_tee = TechnicalEntityExtractor()
_equipment_resolver = EquipmentResolver()

_VALID_VERSIONS = {1, 2, 3}
_VERSION_LABELS = {
    1: "Home Maintenance",
    2: "Electronics",
    3: "Industrial / Automotive",
}


def _get_retrieval(version: int) -> AIRetrievalEngine:
    with _engine_lock:
        if version not in _retrieval_pool:
            _retrieval_pool[version] = AIRetrievalEngine(version=version)
    return _retrieval_pool[version]


def _get_diagnostic(version: int) -> AIDiagnosticEngine:
    with _engine_lock:
        if version not in _diagnostic_pool:
            _diagnostic_pool[version] = AIDiagnosticEngine(version=version)
    return _diagnostic_pool[version]


def _get_repair(version: int) -> AIRepairReasoningEngine:
    with _engine_lock:
        if version not in _repair_pool:
            _repair_pool[version] = AIRepairReasoningEngine(version=version)
    return _repair_pool[version]


def _validate_version(version: int) -> None:
    if version not in _VALID_VERSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"version must be 1, 2, or 3 — got {version}",
        )


def _engine_error(exc: Exception, action: str) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"Engine error during {action}: {type(exc).__name__}: {exc}",
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000,
                       description="Free-text search query")
    top_k: int = Field(default=5, ge=1, le=20,
                       description="Number of results to return")
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter to 'system', 'symptom', or 'repair'",
    )


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000,
                      description="Natural-language problem description")
    top_k: int = Field(default=5, ge=1, le=20)


class DiagnoseRequest(BaseModel):
    symptom_code: str = Field(..., min_length=2, max_length=64,
                              description="Symptom code e.g. PRB-ROF-002")
    responses: list[str] = Field(
        default=[],
        description="Ordered yes/no answers to diagnostic questions",
    )


class RecommendRequest(BaseModel):
    symptom_code: str = Field(..., min_length=2, max_length=64)
    diagnostic_result: Optional[dict] = Field(
        default=None,
        description="Optional output from /diagnose to guide repair matching",
    )
    top_k: int = Field(default=5, ge=1, le=10)


class PlanRequest(BaseModel):
    symptom_code: str = Field(..., min_length=2, max_length=64)
    diagnostic_result: Optional[dict] = Field(
        default=None,
        description="Optional output from /diagnose",
    )
    top_k: int = Field(default=3, ge=1, le=5)


class UnderstandRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000,
                       description="Raw user repair query to parse")


class IntentSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000,
                       description="Raw user repair query to classify and route")
    top_k: int = Field(default=5, ge=1, le=20,
                       description="Number of knowledge matches to return")


# ===========================================================================
# Root / Health
# ===========================================================================

@router.get("/", summary="v2 API info")
def v2_info() -> dict:
    return {
        "api":     "FixFinder AI Engine v2",
        "versions": {
            "1": "Home Maintenance",
            "2": "Electronics",
            "3": "Industrial / Automotive",
        },
        "endpoints": {
            "health":           "GET  /v2/health",
            "understand":       "POST /v2/understand",
            "classify":         "POST /v2/classify",
            "components":       "POST /v2/components",
            "resolve_equipment":"POST /v2/resolve-equipment",
            "extract_entities": "POST /v2/extract-entities",
            "intent_search":    "POST /v2/intent-search",
            "search":           "POST /v2/{version}/search",
            "system":           "GET  /v2/{version}/systems/{id}",
            "symptom":          "GET  /v2/{version}/symptoms/{id}",
            "repair_db":        "GET  /v2/{version}/repairs/{id}",
            "analyze":          "POST /v2/{version}/analyze",
            "tree":             "GET  /v2/{version}/tree/{symptom_code}",
            "diagnose":         "POST /v2/{version}/diagnose",
            "recommend":        "POST /v2/{version}/recommend",
            "parts":            "GET  /v2/{version}/parts/{repair_id}",
            "plan":             "POST /v2/{version}/plan",
        },
    }


@router.get("/health", summary="Engine health check")
def v2_health() -> dict:
    """
    Attempt to load all six engine instances (3 retrieval + 3 repair) and
    report their status without raising on failure.
    """
    health: dict[str, Any] = {"status": "ok", "versions": {}}
    all_ok = True

    for v in _VALID_VERSIONS:
        v_status: dict[str, Any] = {"label": _VERSION_LABELS[v]}

        # Retrieval
        try:
            eng = _get_retrieval(v)
            v_status["retrieval"] = {
                "ok":      True,
                "vectors": eng._faiss_meta.get("total_entries") if eng._faiss_meta else None,
                "dim":     eng._dimension,
            }
        except Exception as exc:
            v_status["retrieval"] = {"ok": False, "error": str(exc)}
            all_ok = False

        # Diagnostic
        try:
            _get_diagnostic(v)
            v_status["diagnostic"] = {"ok": True}
        except Exception as exc:
            v_status["diagnostic"] = {"ok": False, "error": str(exc)}
            all_ok = False

        # Repair
        try:
            _get_repair(v)
            v_status["repair"] = {"ok": True}
        except Exception as exc:
            v_status["repair"] = {"ok": False, "error": str(exc)}
            all_ok = False

        health["versions"][str(v)] = v_status

    if not all_ok:
        health["status"] = "degraded"

    return health


# ===========================================================================
# RQU — Repair Query Understanding
# ===========================================================================

@router.post(
    "/understand",
    summary="Repair Query Understanding (RQU)",
    tags=["RQU"],
    description=(
        "Parse a raw user repair query into a structured Repair Understanding "
        "Object (RUO).  Detects intent, equipment, component, symptoms, failure "
        "types, environment, severity, safety risk, and ambiguity — entirely from "
        "deterministic NLP rules.  No AI guessing.  Returns JSON only."
    ),
)
def understand_query(body: UnderstandRequest) -> dict:
    """
    Transform a raw repair query into a structured RUO.

    Example input:  `"My fridge won't light on propane"`

    Returns a fully populated Repair Understanding Object with 16 fields
    including equipment_category, symptoms, failure_types, severity,
    safety_risk, ambiguity_score, and confidence.
    """
    try:
        ruo = _rqu.understand(body.query)
        return ruo
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RQU engine error: {type(exc).__name__}: {exc}",
        )


@router.post(
    "/resolve-equipment",
    summary="Equipment Resolution",
    tags=["Equipment"],
    description=(
        "Determine exactly which equipment the user is referring to. Returns "
        "equipment_category, equipment_name, and confidence only. This endpoint "
        "does not diagnose or provide repair guidance."
    ),
)
def resolve_equipment(body: UnderstandRequest) -> dict:
    """
    Resolve the target equipment from a raw query.

    Example input: `"My water pump runs but no water comes out"`
    """
    try:
        return _equipment_resolver.resolve(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Equipment resolver error: {type(exc).__name__}: {exc}",
        )


@router.post(
    "/extract-entities",
    summary="Technical Entity Extraction (TEE)",
    tags=["TEE"],
    description=(
        "Extract technical entities from a raw repair query. Returns brands, "
        "models, equipment, components, parts, measurements, temperatures, "
        "voltages, error codes, locations, and units. This endpoint never "
        "diagnoses or provides repair guidance."
    ),
)
def extract_entities(body: UnderstandRequest) -> dict:
    """
    Extract technical entities only.

    Example input: `"Dometic RM2652 fridge shows E1 at 12.4V near the burner"`
    """
    try:
        return _tee.extract(body.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"TEE engine error: {type(exc).__name__}: {exc}",
        )


@router.post(
    "/classify",
    summary="Intent Classification Engine (ICE)",
    tags=["ICE"],
    description=(
        "Accepts either a raw query (string) or a pre-built RUO dict and "
        "returns an Intent Classification Object with primary_intent, "
        "secondary_intent, user_goal, intent_confidence, and routing_hint. "
        "Allowed intents: DIAGNOSE_PROBLEM, REPAIR_GUIDANCE, IDENTIFY_COMPONENT, "
        "ERROR_CODE_LOOKUP, MAINTENANCE, INSTALLATION, CONFIGURATION, "
        "PART_LOOKUP, SAFETY, VERIFY_REPAIR, ESCALATE."
    ),
)
def classify_intent(body: UnderstandRequest) -> dict:
    """
    Full RQU → ICE pipeline in one call.

    Parses the raw query into a RUO, then classifies the intent.
    Returns the complete Intent Classification Object including
    a ruo_summary and routing_hint for the orchestrator.
    """
    try:
        ruo = _rqu.understand(body.query)
        ico = _ice.classify(ruo)
        return ico
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"ICE engine error: {type(exc).__name__}: {exc}",
        )


@router.post(
    "/components",
    summary="Component Identification Engine (CIE)",
    tags=["CIE"],
    description=(
        "Identify every component involved in a repair query. "
        "Returns each component with its canonical name, type "
        "(mechanical / electrical / electronic / gas / fluid / structural / control), "
        "functional role, and whether it is the suspected failing part. "
        "No diagnosis, no repair guidance — components only."
    ),
)
def identify_components(body: UnderstandRequest) -> dict:
    """
    Parse a raw repair query and return every component involved.

    Suspects (likely failing components) are listed first.

    Example input: `"My RV fridge won't light on propane"`

    Returns:
    - `components[]` — list of every component identified
    - `suspects` — count of likely-failing components
    - `total` — total components identified
    """
    try:
        result = _cie.identify(body.query)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"CIE engine error: {type(exc).__name__}: {exc}",
        )


_VERSION_BY_CATEGORY = {
    "Home Maintenance": 1,
    "Electronics": 2,
    "Industrial / Automotive": 3,
}

_DOMAIN_KEYWORDS: dict[int, tuple[str, ...]] = {
    1: (
        "roof", "leak", "shingle", "plumb", "faucet", "toilet", "pipe",
        "water", "hvac", "furnace", "fridge", "refrigerator", "propane",
        "stove", "oven", "outlet", "breaker", "gutter", "basement",
        "sump", "window", "door", "garage", "heater", "drain",
    ),
    2: (
        "phone", "iphone", "samsung", "laptop", "macbook", "screen",
        "battery", "charger", "computer", "pc", "monitor", "tv",
        "television", "tablet", "router", "network", "printer", "console",
        "ps5", "xbox", "camera",
    ),
    3: (
        "car", "truck", "vehicle", "engine", "brake", "transmission",
        "oil", "alternator", "radiator", "exhaust", "motor", "generator",
        "excavator", "tractor", "forklift", "hydraulic", "diesel",
        "motorcycle", "industrial", "compressor",
    ),
}

_ENTITY_TYPE_BY_INTENT = {
    "IDENTIFY_COMPONENT": "system",
    "CONFIGURATION": "system",
    "MAINTENANCE": "repair",
    "INSTALLATION": "repair",
    "PART_LOOKUP": "repair",
    "REPAIR_GUIDANCE": "repair",
}


def _domain_boost(query: str, version: int) -> float:
    query_lower = query.lower()
    hits = sum(1 for kw in _DOMAIN_KEYWORDS.get(version, ()) if kw in query_lower)
    return round(min(hits * 0.05, 0.25), 4)


def _preferred_version_from_ruo(ruo: dict[str, Any]) -> Optional[int]:
    return _VERSION_BY_CATEGORY.get(ruo.get("equipment_category", ""))


def _selection_reason(ruo_version: Optional[int], selected_version: int) -> str:
    if ruo_version == selected_version:
        return "RQU equipment category and highest adjusted knowledge score agree."
    if ruo_version:
        return "Highest adjusted knowledge score overrode the RQU category hint."
    return "Selected from the highest adjusted knowledge score."


@router.post(
    "/intent-search",
    summary="Intent-aware knowledge selection",
    tags=["ICE"],
    description=(
        "Runs RQU and ICE, chooses the most relevant knowledge-base version, "
        "and returns ranked knowledge matches for the user's intent. This is "
        "the backend equivalent of understand -> classify -> pick knowledge."
    ),
)
def intent_search(body: IntentSearchRequest) -> dict:
    """
    Classify a user query and pick the best matching knowledge base.

    The route searches all three versioned knowledge bases, then applies:
    - the RQU equipment-category version hint,
    - domain keyword boosts,
    - intent-specific routing.
    """
    try:
        ruo = _rqu.understand(body.query)
        ico = _ice.classify(ruo)
        primary_intent = ico["primary_intent"]
        ruo_version = _preferred_version_from_ruo(ruo)

        if primary_intent == "SAFETY":
            selected_version = ruo_version or 1
            return {
                "query": body.query,
                "repair_understanding": ruo,
                "intent_classification": ico,
                "selected_knowledge": {
                    "version": selected_version,
                    "version_label": _VERSION_LABELS[selected_version],
                    "reason": "Safety intent short-circuits knowledge search.",
                },
                "knowledge_action": "safety_alert",
                "matches": [],
            }

        if primary_intent == "ESCALATE":
            selected_version = ruo_version or 1
            return {
                "query": body.query,
                "repair_understanding": ruo,
                "intent_classification": ico,
                "selected_knowledge": {
                    "version": selected_version,
                    "version_label": _VERSION_LABELS[selected_version],
                    "reason": "Escalation intent should ask for help or more detail.",
                },
                "knowledge_action": "escalate",
                "matches": [],
            }

        matches: list[dict[str, Any]] = []
        knowledge_action = "analyze_symptoms"

        if primary_intent in {
            "DIAGNOSE_PROBLEM",
            "ERROR_CODE_LOOKUP",
            "VERIFY_REPAIR",
        }:
            for version in sorted(_VALID_VERSIONS):
                for match in _get_diagnostic(version).analyze_symptoms(
                    body.query, top_k=body.top_k
                ):
                    boost = _domain_boost(body.query, version)
                    if ruo_version == version:
                        boost += 0.15
                    adjusted_score = round((match.get("score") or 0) + boost, 4)
                    matches.append({
                        **match,
                        "version": version,
                        "version_label": _VERSION_LABELS[version],
                        "raw_score": match.get("score"),
                        "domain_boost": round(boost, 4),
                        "adjusted_score": adjusted_score,
                    })
        else:
            knowledge_action = "semantic_search"
            entity_type = _ENTITY_TYPE_BY_INTENT.get(primary_intent)
            for version in sorted(_VALID_VERSIONS):
                for result in _get_retrieval(version).search(
                    query_text=body.query,
                    top_k=body.top_k,
                    entity_type_filter=entity_type,
                ):
                    boost = _domain_boost(body.query, version)
                    if ruo_version == version:
                        boost += 0.15
                    adjusted_score = round((result.get("score") or 0) + boost, 4)
                    matches.append({
                        **result,
                        "version": version,
                        "version_label": _VERSION_LABELS[version],
                        "raw_score": result.get("score"),
                        "domain_boost": round(boost, 4),
                        "adjusted_score": adjusted_score,
                    })

        matches.sort(key=lambda item: item["adjusted_score"], reverse=True)
        matches = matches[:body.top_k]
        for rank, match in enumerate(matches, start=1):
            match["rank"] = rank

        selected_version = (
            matches[0]["version"] if matches
            else ruo_version if ruo_version
            else 1
        )

        return {
            "query": body.query,
            "repair_understanding": ruo,
            "intent_classification": ico,
            "selected_knowledge": {
                "version": selected_version,
                "version_label": _VERSION_LABELS[selected_version],
                "reason": _selection_reason(ruo_version, selected_version),
            },
            "knowledge_action": knowledge_action,
            "matches": matches,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _engine_error(exc, "intent_search")


@router.post(
    "/{version}/search",
    summary="Semantic FAISS search",
    description=(
        "Embed the query using SHA-256 synthetic embeddings and run "
        "cosine-similarity search over the version's FAISS index. "
        "Returns ranked entity IDs with scores."
    ),
)
def search(
    version: int = Path(..., ge=1, le=3, description="Version 1, 2, or 3"),
    body: SearchRequest = ...,
) -> dict:
    _validate_version(version)
    try:
        eng     = _get_retrieval(version)
        results = eng.search(
            query_text         = body.query,
            top_k              = body.top_k,
            entity_type_filter = body.entity_type,
        )
        return {
            "version":        version,
            "version_label":  _VERSION_LABELS[version],
            "query":          body.query,
            "entity_type":    body.entity_type,
            "total_results":  len(results),
            "results":        results,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise _engine_error(exc, "search")


@router.get(
    "/{version}/systems/{system_id}",
    summary="System details",
    description="Fetch full system info from SQLite by system_code or partial name.",
)
def get_system(
    version: int   = Path(..., ge=1, le=3),
    system_id: str = Path(..., min_length=1, max_length=64),
) -> dict:
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_system_details(system_id)
    except Exception as exc:
        raise _engine_error(exc, "get_system_details")
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"System '{system_id}' not found in version {version}")
    return result


@router.get(
    "/{version}/symptoms/{symptom_id}",
    summary="Symptom details",
    description="Fetch full symptom info from SQLite by symptom_code or partial name.",
)
def get_symptom(
    version: int    = Path(..., ge=1, le=3),
    symptom_id: str = Path(..., min_length=1, max_length=64),
) -> dict:
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_symptom_details(symptom_id)
    except Exception as exc:
        raise _engine_error(exc, "get_symptom_details")
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Symptom '{symptom_id}' not found in version {version}")
    return result


@router.get(
    "/{version}/repairs/{repair_id}",
    summary="Repair procedure details",
    description="Fetch a full repair procedure from SQLite by repair_code or partial name.",
)
def get_repair(
    version: int   = Path(..., ge=1, le=3),
    repair_id: str = Path(..., min_length=1, max_length=64),
) -> dict:
    _validate_version(version)
    try:
        result = _get_retrieval(version).get_repair_procedure(repair_id)
    except Exception as exc:
        raise _engine_error(exc, "get_repair_procedure")
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Repair '{repair_id}' not found in version {version}")
    return result


# ===========================================================================
# Diagnostic endpoints
# ===========================================================================

@router.post(
    "/{version}/analyze",
    summary="Analyze symptoms from free text",
    description=(
        "Tokenize the input and score it against every row in the symptoms "
        "table using weighted keyword overlap. Returns the top-k matches "
        "ranked by relevance score."
    ),
)
def analyze_symptoms(
    version: int = Path(..., ge=1, le=3),
    body: AnalyzeRequest = ...,
) -> dict:
    _validate_version(version)
    try:
        eng     = _get_diagnostic(version)
        matches = eng.analyze_symptoms(body.text, top_k=body.top_k)
        return {
            "version":       version,
            "version_label": _VERSION_LABELS[version],
            "input_text":    body.text,
            "total_matches": len(matches),
            "matches":       matches,
        }
    except Exception as exc:
        raise _engine_error(exc, "analyze_symptoms")


@router.get(
    "/{version}/tree/{symptom_code}",
    summary="Load a diagnostic tree",
    description=(
        "Find the diagnostic tree matching a symptom_code (e.g. PRB-ROF-002) "
        "from the version's diagnostic_trees.json. Returns the full tree "
        "structure: steps, decision points, and resolution paths."
    ),
)
def get_tree(
    version: int       = Path(..., ge=1, le=3),
    symptom_code: str  = Path(..., min_length=2, max_length=64),
) -> dict:
    _validate_version(version)
    try:
        tree = _get_diagnostic(version).get_diagnostic_tree(symptom_code)
    except Exception as exc:
        raise _engine_error(exc, "get_diagnostic_tree")
    if tree is None:
        raise HTTPException(
            status_code=404,
            detail=f"No diagnostic tree found for '{symptom_code}' in version {version}",
        )
    return tree


@router.post(
    "/{version}/diagnose",
    summary="Run guided tree traversal",
    description=(
        "Walk the diagnostic tree for a symptom_code step-by-step, consuming "
        "one yes/no user response per decision point. Returns the traversal "
        "trace, recommended_action, and matched repair_code (if reached)."
    ),
)
def run_diagnostic(
    version: int = Path(..., ge=1, le=3),
    body: DiagnoseRequest = ...,
) -> dict:
    _validate_version(version)
    try:
        result = _get_diagnostic(version).run_diagnostic(
            symptom_code   = body.symptom_code,
            user_responses = body.responses,
        )
        return {
            "version":       version,
            "version_label": _VERSION_LABELS[version],
            **result,
        }
    except Exception as exc:
        raise _engine_error(exc, "run_diagnostic")


# ===========================================================================
# Repair Reasoning endpoints
# ===========================================================================

@router.post(
    "/{version}/recommend",
    summary="Ranked repair recommendations",
    description=(
        "Match JSON repair procedures to a symptom using a 4-tier scoring "
        "system: direct repair_code match → resolution path code → category "
        "match → keyword overlap. Sorted by relevance DESC then difficulty ASC."
    ),
)
def recommend_repair(
    version: int = Path(..., ge=1, le=3),
    body: RecommendRequest = ...,
) -> dict:
    _validate_version(version)
    try:
        recs = _get_repair(version).recommend_repair(
            symptom_code      = body.symptom_code,
            diagnostic_result = body.diagnostic_result,
            top_k             = body.top_k,
        )
        return {
            "version":        version,
            "version_label":  _VERSION_LABELS[version],
            "symptom_code":   body.symptom_code,
            "total_results":  len(recs),
            "recommendations": recs,
        }
    except Exception as exc:
        raise _engine_error(exc, "recommend_repair")


@router.get(
    "/{version}/parts/{repair_id}",
    summary="Parts availability for a repair",
    description=(
        "For each material in the JSON repair procedure, fuzzy-match it "
        "against parts_inventory in SQLite and return stock level, unit "
        "cost, supplier, and availability status."
    ),
)
def parts_availability(
    version: int   = Path(..., ge=1, le=3),
    repair_id: str = Path(..., min_length=2, max_length=64,
                          description="JSON repair key, e.g. RP-ROF-001"),
) -> dict:
    _validate_version(version)
    try:
        result = _get_repair(version).check_parts_availability(repair_id)
        return {
            "version":      version,
            "version_label": _VERSION_LABELS[version],
            **result,
        }
    except Exception as exc:
        raise _engine_error(exc, "check_parts_availability")


@router.post(
    "/{version}/plan",
    summary="Full repair plan",
    description=(
        "End-to-end repair plan: calls recommend_repair, picks the best "
        "option, checks parts availability, calculates total time and cost, "
        "and returns ordered plan_steps (pre-checks → tools → procedure → "
        "post-checks → warnings)."
    ),
)
def generate_plan(
    version: int = Path(..., ge=1, le=3),
    body: PlanRequest = ...,
) -> dict:
    _validate_version(version)
    try:
        plan = _get_repair(version).generate_repair_plan(
            symptom_code      = body.symptom_code,
            diagnostic_result = body.diagnostic_result,
            top_k             = body.top_k,
        )
        return {
            "version":       version,
            "version_label": _VERSION_LABELS[version],
            **plan,
        }
    except Exception as exc:
        raise _engine_error(exc, "generate_repair_plan")
