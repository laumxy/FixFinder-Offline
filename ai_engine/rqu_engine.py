"""
ai_engine/rqu_engine.py
========================
Repair Query Understanding (RQU) Engine — FixFinder.

Transforms a raw user repair query into a structured Repair Understanding
Object (RUO) using deterministic NLP rules.  No LLM, no guessing, no
repair reasoning — pure query parsing.

The _detect_symptoms and all keyword lists operate on the ORIGINAL
lowercase text (q_lower) so raw phrases like "won't start" and "dead"
always match.  _normalize() is only used for equipment/component
extraction and normalized_terms output.

Output schema (16 keys, always present):
  language, primary_intent, secondary_intent, equipment_category,
  equipment, component, symptoms, failure_types, environment,
  severity, safety_risk, evidence_type, ambiguity_score, confidence,
  normalized_terms, missing_information, original_query
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Synonym map — raw → canonical (used for normalised_terms only)
# ---------------------------------------------------------------------------
_SYNONYMS: dict[str, str] = {
    "won't":     "will not",    "wont":      "will not",
    "can't":     "cannot",      "cant":      "cannot",
    "doesn't":   "does not",    "doesnt":    "does not",
    "isn't":     "is not",      "isnt":      "is not",
    "dead":      "not working", "broken":    "not working",
    "blown":     "failed",      "burnt":     "burned",    "fried": "burned",
    "tripped":   "triggered",   "popped":    "triggered",
    "light":     "ignite",      "lights":    "ignites",
    "fire up":   "ignite",      "kick on":   "start",
    "fridge":    "refrigerator","icebox":    "refrigerator",
    "dometic":   "RV refrigerator", "norcold": "RV refrigerator",
    "rv fridge": "RV refrigerator",
    "a/c":       "air conditioner",
    "gen":       "generator",   "onan":      "generator",
    "pump":      "water pump",
    "slide":     "slide-out",   "slide out": "slide-out",
    "jacks":     "leveling jacks",
    "outlet":    "electrical outlet", "socket": "electrical outlet",
    "breaker":   "circuit breaker",
    "iphone":    "iPhone",      "samsung":   "Samsung device",
    "car":       "automobile",  "brakes":    "brakes",
}

# ---------------------------------------------------------------------------
# Equipment master list  {canonical_name: version (1/2/3)}
# ---------------------------------------------------------------------------
_EQUIPMENT_VERSION: dict[str, int] = {
    # ── v1 Home / RV ──
    "refrigerator": 1, "RV refrigerator": 1, "propane refrigerator": 1,
    "furnace": 1, "air conditioner": 1, "water heater": 1,
    "water pump": 1, "slide-out": 1, "awning": 1,
    "leveling system": 1, "leveling jacks": 1,
    "generator": 1, "inverter/charger": 1,
    "electrical outlet": 1, "circuit breaker": 1, "fuse": 1,
    "roof": 1, "toilet": 1, "drain": 1, "window": 1,
    "door": 1, "garage door": 1,
    # ── v2 Electronics ──
    "laptop": 2, "smartphone": 2, "iPhone": 2, "Samsung device": 2,
    "tablet": 2, "TV": 2, "television": 2,
    "router": 2, "printer": 2, "gaming console": 2, "PS5": 2, "Xbox": 2,
    # ── v3 Automotive / Industrial ──
    "automobile": 3, "truck": 3, "engine": 3, "brakes": 3,
    "transmission": 3, "excavator": 3, "tractor": 3,
    "hydraulic system": 3, "compressor": 3, "industrial motor": 3,
}

# ---------------------------------------------------------------------------
# Component keyword map — searched on ORIGINAL lowercase text
# ---------------------------------------------------------------------------
_COMPONENT_KEYWORDS: dict[str, list[str]] = {
    "burner":         ["burner", "flame", "orifice", "jet", "pilot"],
    "thermocouple":   ["thermocouple", "safety sensor"],
    "igniter":        ["igniter", "ignitor", "electrode"],
    "fan":            ["fan", "blower"],
    "pump":           ["pump", "impeller"],
    "battery":        ["battery", "12v"],
    "fuse":           ["fuse", "breaker", "gfci"],
    "thermostat":     ["thermostat", "t-stat"],
    "valve":          ["valve", "solenoid", "gas valve"],
    "seal":           ["seal", "gasket", "o-ring"],
    "screen/display": ["screen", "display", "lcd", "oled", "panel"],
    "charging port":  ["charging port", "usb port", "lightning"],
    "carburetor":     ["carburetor", "carb"],
    "starter":        ["starter", "starter motor"],
    "alternator":     ["alternator"],
    "radiator":       ["radiator", "coolant"],
    "spark":          ["spark plug", "ignition coil"],
}

# ---------------------------------------------------------------------------
# Symptom keyword map — searched on ORIGINAL lowercase text
# ---------------------------------------------------------------------------
_SYMPTOM_KEYWORDS: list[tuple[str, list[str]]] = [
    ("will not start",       ["won't start", "wont start", "not starting",
                               "fails to start", "doesn't start", "no start",
                               "won't crank", "starts then dies", "dies immediately",
                               "dies right away", "runs then shuts", "starts but dies"]),
    ("will not ignite",      ["won't light", "wont light", "won't ignite",
                               "no flame", "doesn't ignite", "fails to ignite",
                               "no ignition", "won't fire", "not lighting"]),
    ("no power",             ["no power", "dead", "not turning on", "won't turn on",
                               "wont turn on", "won't power on", "nothing happens",
                               "completely dead", "won't come on", "no lights",
                               "doesn't turn on", "not powering"]),
    ("not cooling",          ["not cooling", "not cold", "warm inside", "not getting cold",
                               "no cooling", "won't cool", "not chilling",
                               "not refrigerating", "not keeping cold"]),
    ("not charging",         ["not charging", "won't charge", "not holding charge",
                               "battery draining", "drains fast", "battery dead",
                               "battery dying"]),
    ("overheating",          ["overheating", "too hot", "running hot", "gets hot",
                               "thermal shutdown", "shuts off from heat", "shutting down hot"]),
    ("leaking",              ["leaking", "dripping", "water leak", "oil leak",
                               "drips", "puddle", "wet floor"]),
    ("loud noise",           ["loud noise", "clicking", "grinding", "rattling",
                               "knocking", "squealing", "humming", "vibrating",
                               "makes noise", "strange noise"]),
    ("stuck",                ["stuck", "won't move", "won't retract", "won't extend",
                               "jammed", "not moving", "seized", "won't retract",
                               "won't slide"]),
    ("running continuously", ["runs constantly", "won't stop running", "keeps running",
                               "won't shut off", "runs all the time"]),
    ("low pressure",         ["low pressure", "weak water", "low flow", "no water",
                               "no water flow", "weak flow", "water runs out",
                               "water runs but no", "runs but no water"]),
    ("tripping",             ["tripping", "trips breaker", "keeps blowing", "popped breaker",
                               "breaker trips"]),
    ("cracked/damaged",      ["cracked", "broken screen", "shattered", "damaged", "bent"]),
    ("error code",           ["error code", "fault code", "warning light", "check engine",
                               "cel on", "shows code", "p0", "f1", "e1", "e2"]),
    ("slow/sluggish",        ["slow", "sluggish", "takes long", "delayed"]),
]

# ---------------------------------------------------------------------------
# Failure type map — searched on ORIGINAL lowercase text
# ---------------------------------------------------------------------------
_FAILURE_TYPES: list[tuple[str, list[str]]] = [
    ("mechanical failure",   ["seized", "jammed", "stuck", "snapped", "cracked", "bent"]),
    ("electrical failure",   ["no power", "dead", "blown fuse", "tripped", "sparks",
                               "short", "burned out"]),
    ("fuel/fluid issue",     ["no fuel", "out of propane", "empty tank", "low oil",
                               "no coolant", "clogged", "blocked", "dirty", "no gas"]),
    ("ignition failure",     ["won't light", "won't ignite", "no spark", "no flame",
                               "thermocouple", "igniter"]),
    ("seal/leak failure",    ["leaking", "dripping", "seal", "gasket", "o-ring"]),
    ("sensor/control fault", ["error", "fault code", "sensor", "won't respond", "no signal",
                               "check engine"]),
    ("overload/overheat",    ["overheating", "too hot", "thermal shutdown", "overheat"]),
    ("wear/degradation",     ["worn", "old", "corroded", "rusted", "degraded"]),
    ("intermittent fault",   ["sometimes", "intermittent", "on and off",
                               "starts then dies", "randomly"]),
    ("user error",           ["wrong setting", "accidentally", "forgot", "misconfigured"]),
]

# ---------------------------------------------------------------------------
# Safety patterns — searched on ORIGINAL lowercase text
# Order matters: more specific first
# ---------------------------------------------------------------------------
_SAFETY_PATTERNS: list[tuple[str, list[str]]] = [
    ("carbon monoxide",  ["carbon monoxide", "co alarm", "co detector",
                           "headache in rv"]),
    ("gas leak",         ["smell gas", "gas smell", "propane smell", "smell propane",
                           "rotten egg", "gas leak", "propane leak",
                           "i smell gas", "smells like gas", "gas odor"]),
    ("electrical hazard",["sparks", "shocking", "shock", "burning smell from panel",
                           "smoke from outlet", "electrical fire", "hot wire",
                           "melting"]),
    ("fire risk",        ["on fire", "flames", "smoke coming", "charred",
                           "burning smell"]),
    ("structural",       ["driving with slide", "slide won't retract before",
                           "roof collapsing", "floor is soft", "frame damage",
                           "won't retract before driving"]),
]

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------
_PRIMARY_INTENTS: list[tuple[str, list[str]]] = [
    ("safety_check",   ["safe", "is it safe", "danger", "risk", "should i worry",
                         "gas smell", "smell gas", "smoke"]),
    ("repair",         ["how to fix", "fix", "repair", "replace", "install",
                         "change", "swap", "rebuild"]),
    ("maintenance",    ["service", "maintenance", "clean", "flush", "inspection",
                         "when to change", "oil change"]),
    ("identify",       ["what is", "what type", "identify", "which part", "where is"]),
    ("verify",         ["is it normal", "should it", "does it", "check if", "confirm"]),
    ("diagnose",       ["why", "what's wrong", "won't", "doesn't", "not working",
                         "broken", "issue", "problem", "failing", "failed",
                         "stopped", "no longer", "help"]),
]

_SECONDARY_INTENTS: list[tuple[str, list[str]]] = [
    ("cost_estimate",    ["how much", "cost", "price", "expensive", "worth it"]),
    ("diy_feasibility",  ["can i fix", "do it myself", "diy", "myself"]),
    ("parts_needed",     ["what parts", "which parts", "need parts", "buy", "order"]),
    ("time_estimate",    ["how long", "how many minutes", "how many hours"]),
    ("tools_needed",     ["what tools", "tools needed", "need a wrench"]),
    ("professional",     ["call a tech", "hire", "professional", "mechanic", "rv tech"]),
]

# ---------------------------------------------------------------------------
# Environment, severity, evidence patterns
# ---------------------------------------------------------------------------
_ENV_KEYWORDS: dict[str, list[str]] = {
    "RV/Camper":    ["rv", "motorhome", "camper", "travel trailer", "fifth wheel",
                     "coach", "dometic", "norcold", "onan", "rv fridge"],
    "Residential":  ["home", "house", "apartment", "condo", "basement", "kitchen"],
    "Vehicle":      ["car", "truck", "van", "automobile", "vehicle", "suv"],
    "Marine":       ["boat", "marine", "vessel", "outboard"],
    "Industrial":   ["factory", "shop", "warehouse", "industrial", "plant"],
    "Outdoor":      ["outside", "outdoor", "yard", "job site", "field"],
}

_URGENCY_KEYWORDS: dict[str, list[str]] = {
    "Critical":  ["fire", "smoke", "gas smell", "smell gas", "sparks", "flooding",
                  "carbon monoxide", "propane leak", "emergency", "asap", "immediately",
                  "dangerous", "explosion"],
    "High":      ["freezing", "no heat", "no water", "stuck", "cannot move",
                  "trip tomorrow", "leaving soon", "no power", "completely dead",
                  "nothing works", "boondocking"],
    "Medium":    ["not working", "issue", "problem", "keeps happening",
                  "intermittent", "sometimes", "broken"],
    "Low":       ["curious", "wondering", "maintenance", "planning", "eventually",
                  "just noticed"],
}

_EVIDENCE_TYPES: list[tuple[str, list[str]]] = [
    ("olfactory",  ["smell", "odor", "stink", "rotten", "burning smell"]),
    ("auditory",   ["hear", "heard", "noise", "clicking", "grinding", "beep", "sound"]),
    ("error_code", ["error code", "fault code", "warning", "shows code", "reads"]),
    ("visual",     ["see", "seeing", "looks", "visible", "noticed"]),
    ("tactile",    ["feel", "hot to touch", "vibrating", "shaking", "loose"]),
    ("measurement",["volt", "amp", "psi", "ohm", "measured", "reading"]),
    ("behavioral", ["won't", "doesn't", "stopped", "fails", "not", "dead", "stuck"]),
]

# Language detection — require 3+ markers to reduce false positives
_LANG_PATTERNS: dict[str, list[str]] = {
    "es": ["está", "funciona", "encendido", "frigorífico", "no enciende",
           "carro no", "nevera", "nevera no"],
    "fr": ["ne marche", "s'allume", "frigo", "voiture ne", "réfrigérateur"],
    "de": ["kühlt nicht", "kühlschrank", "zündet nicht", "startet nicht", "geht nicht"],
    "pt": ["não funciona", "geladeira", "não liga", "carro não", "não acende"],
}


# ===========================================================================
# RQUEngine
# ===========================================================================

class RQUEngine:
    """
    Repair Query Understanding Engine.

    All keyword matching runs on the ORIGINAL lowercase query so that
    natural user phrases like "won't start" and "dead" always resolve.
    Synonym normalisation is only used for the normalized_terms output field.
    """

    def understand(self, raw_query: str) -> dict[str, Any]:
        q       = raw_query.strip()
        q_lower = q.lower()

        language           = self._detect_language(q_lower)
        primary_intent     = self._detect_primary_intent(q_lower)
        secondary_intent   = self._detect_secondary_intent(q_lower)
        equipment_category = self._detect_equipment_category(q_lower)
        equipment          = self._detect_equipment(q_lower)
        component          = self._detect_component(q_lower)
        symptoms           = self._detect_symptoms(q_lower)
        failure_types      = self._detect_failure_types(q_lower)
        environment        = self._detect_environment(q_lower)
        severity           = self._detect_severity(q_lower)
        safety_risk        = self._detect_safety_risk(q_lower)
        evidence_type      = self._detect_evidence_type(q_lower)
        normalized_terms   = self._collect_normalized_terms(q_lower)
        missing_info       = self._detect_missing_info(
            equipment, component, symptoms, environment, q_lower)
        ambiguity_score    = self._compute_ambiguity(
            equipment, component, symptoms, missing_info)
        confidence         = self._compute_confidence(
            equipment, symptoms, failure_types, ambiguity_score)

        return {
            "language":            language,
            "primary_intent":      primary_intent,
            "secondary_intent":    secondary_intent,
            "equipment_category":  equipment_category,
            "equipment":           equipment,
            "component":           component,
            "symptoms":            symptoms,
            "failure_types":       failure_types,
            "environment":         environment,
            "severity":            severity,
            "safety_risk":         safety_risk,
            "evidence_type":       evidence_type,
            "ambiguity_score":     ambiguity_score,
            "confidence":          confidence,
            "normalized_terms":    normalized_terms,
            "missing_information": missing_info,
            "original_query":      raw_query,
        }

    # ------------------------------------------------------------------
    # Detection methods — all receive q_lower (original lowercase)
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_language(text: str) -> str:
        for lang, markers in _LANG_PATTERNS.items():
            if any(m in text for m in markers):
                return lang
        return "en"

    @staticmethod
    def _detect_primary_intent(text: str) -> str:
        for intent, keywords in _PRIMARY_INTENTS:
            if any(kw in text for kw in keywords):
                return intent
        return "diagnose"

    @staticmethod
    def _detect_secondary_intent(text: str) -> str:
        for intent, keywords in _SECONDARY_INTENTS:
            if any(kw in text for kw in keywords):
                return intent
        return "none"

    @staticmethod
    def _detect_equipment_category(text: str) -> str:
        v2_kw = ["laptop", "phone", "iphone", "samsung", "tablet", "tv ",
                  "television", "router", "printer", "console", "ps5", "xbox",
                  "screen", "display", "computer", "pc "]
        if any(k in text for k in v2_kw):
            return "Electronics"
        v3_kw = ["automobile", " car ", "car won", "car doesn", "car starts",
                  " truck", "engine light", "brake", "transmission",
                  "excavator", "tractor", "hydraulic", " diesel",
                  "motorcycle", "boat", "marine", "compressor"]
        if any(k in text for k in v3_kw):
            return "Industrial / Automotive"
        return "Home Maintenance"

    @staticmethod
    def _detect_equipment(text: str) -> str:
        best_len, best = 0, "unknown"
        for equip in _EQUIPMENT_VERSION:
            kw = equip.lower()
            if kw in text and len(kw) > best_len:
                best_len, best = len(kw), equip
        return best

    @staticmethod
    def _detect_component(text: str) -> str:
        for component, keywords in _COMPONENT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return component
        return "unknown"

    @staticmethod
    def _detect_symptoms(text: str) -> list[str]:
        found = [sym for sym, kws in _SYMPTOM_KEYWORDS if any(k in text for k in kws)]
        return found or ["unclear"]

    @staticmethod
    def _detect_failure_types(text: str) -> list[str]:
        found = [ft for ft, kws in _FAILURE_TYPES if any(k in text for k in kws)]
        return found or ["unknown"]

    @staticmethod
    def _detect_environment(text: str) -> str:
        for env, keywords in _ENV_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return env
        return "unspecified"

    @staticmethod
    def _detect_severity(text: str) -> str:
        for level in ("Critical", "High", "Medium", "Low"):
            if any(kw in text for kw in _URGENCY_KEYWORDS[level]):
                return level
        return "Medium"

    @staticmethod
    def _detect_safety_risk(text: str) -> str:
        for risk, keywords in _SAFETY_PATTERNS:
            if any(kw in text for kw in keywords):
                return risk
        return "none detected"

    @staticmethod
    def _detect_evidence_type(text: str) -> str:
        for etype, keywords in _EVIDENCE_TYPES:
            if any(kw in text for kw in keywords):
                return etype
        return "behavioral"

    @staticmethod
    def _collect_normalized_terms(text: str) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for raw, canonical in sorted(_SYNONYMS.items(), key=lambda x: -len(x[0])):
            if raw.lower() in text and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
        return result

    @staticmethod
    def _detect_missing_info(
        equipment: str, component: str,
        symptoms: list[str], environment: str, text: str,
    ) -> list[str]:
        missing = []
        if equipment == "unknown":
            missing.append("equipment not specified")
        if symptoms == ["unclear"]:
            missing.append("symptom not described")
        if environment == "unspecified":
            missing.append("operating environment not mentioned")
        if not re.search(r"\b(year|model|brand|make|\d{4})\b", text):
            missing.append("equipment make/model/year not provided")
        if not re.search(
            r"\b(since|started|ago|yesterday|week|month|always|recently|just)\b", text
        ):
            missing.append("onset timeline unknown")
        return missing

    @staticmethod
    def _compute_ambiguity(
        equipment: str, component: str,
        symptoms: list[str], missing_info: list[str],
    ) -> float:
        score = 0.0
        if equipment == "unknown":   score += 0.35
        if symptoms == ["unclear"]:  score += 0.30
        if component == "unknown":   score += 0.15
        score += min(len(missing_info) * 0.04, 0.20)
        return round(min(score, 1.0), 2)

    @staticmethod
    def _compute_confidence(
        equipment: str, symptoms: list[str],
        failure_types: list[str], ambiguity: float,
    ) -> float:
        score = round(1.0 - ambiguity, 2)
        if equipment != "unknown":            score = min(score + 0.10, 1.0)
        if symptoms != ["unclear"]:           score = min(score + 0.10, 1.0)
        if "unknown" not in failure_types:    score = min(score + 0.05, 1.0)
        return round(score, 2)
