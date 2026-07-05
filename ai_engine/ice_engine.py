"""
ai_engine/ice_engine.py
========================
Intent Classification Engine (ICE) — FixFinder.

Input:  A Repair Understanding Object (RUO) produced by RQUEngine.
Output: A structured Intent Classification Object (ICO) with:
          - primary_intent   (one of 11 allowed intents)
          - secondary_intent (one of 11 allowed intents, or "NONE")
          - user_goal        (plain-English description of what the user wants)
          - intent_confidence (0.0 – 1.0)
          - routing_hint     (which engine to call next)

Allowed intents:
  DIAGNOSE_PROBLEM  REPAIR_GUIDANCE   IDENTIFY_COMPONENT
  ERROR_CODE_LOOKUP MAINTENANCE       INSTALLATION
  CONFIGURATION     PART_LOOKUP       SAFETY
  VERIFY_REPAIR     ESCALATE

No LLM, no guessing — pure rule-based classification over RUO fields.

Usage
-----
    from ai_engine.rqu_engine import RQUEngine
    from ai_engine.ice_engine import ICEEngine

    ruo = RQUEngine().understand("My fridge won't light on propane")
    ico = ICEEngine().classify(ruo)
    print(ico["primary_intent"])   # "DIAGNOSE_PROBLEM"
    print(ico["routing_hint"])     # "run symptom analysis + repair plan"
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Allowed intents (canonical names)
# ---------------------------------------------------------------------------

INTENT_DIAGNOSE        = "DIAGNOSE_PROBLEM"
INTENT_REPAIR          = "REPAIR_GUIDANCE"
INTENT_IDENTIFY        = "IDENTIFY_COMPONENT"
INTENT_ERROR_CODE      = "ERROR_CODE_LOOKUP"
INTENT_MAINTENANCE     = "MAINTENANCE"
INTENT_INSTALLATION    = "INSTALLATION"
INTENT_CONFIGURATION   = "CONFIGURATION"
INTENT_PART_LOOKUP     = "PART_LOOKUP"
INTENT_SAFETY          = "SAFETY"
INTENT_VERIFY          = "VERIFY_REPAIR"
INTENT_ESCALATE        = "ESCALATE"
INTENT_NONE            = "NONE"

ALL_INTENTS = {
    INTENT_DIAGNOSE, INTENT_REPAIR, INTENT_IDENTIFY, INTENT_ERROR_CODE,
    INTENT_MAINTENANCE, INTENT_INSTALLATION, INTENT_CONFIGURATION,
    INTENT_PART_LOOKUP, INTENT_SAFETY, INTENT_VERIFY, INTENT_ESCALATE,
}

# ---------------------------------------------------------------------------
# Routing hints — tell the orchestrator which downstream engine to invoke
# ---------------------------------------------------------------------------

_ROUTING: dict[str, str] = {
    INTENT_DIAGNOSE:     "run /v2/{version}/analyze → /v2/{version}/plan",
    INTENT_REPAIR:       "run /v2/{version}/plan with symptom_code",
    INTENT_IDENTIFY:     "run /v2/{version}/search with entity_type=system",
    INTENT_ERROR_CODE:   "run /v2/{version}/analyze with error code as query",
    INTENT_MAINTENANCE:  "run /v2/{version}/search with entity_type=repair",
    INTENT_INSTALLATION: "run /v2/{version}/search with entity_type=repair",
    INTENT_CONFIGURATION:"run /v2/{version}/search with entity_type=system",
    INTENT_PART_LOOKUP:  "run /v2/{version}/parts/{repair_id}",
    INTENT_SAFETY:       "return safety_alert immediately — do not search DB",
    INTENT_VERIFY:       "run /v2/{version}/diagnose with user_responses",
    INTENT_ESCALATE:     "return escalation message — recommend professional",
}

# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------
#
# Each rule is a tuple:
#   (primary_intent, conditions_dict, secondary_intent, user_goal_template)
#
# conditions_dict keys (all optional, AND-combined):
#   ruo_primary_in   : list[str]  — ruo["primary_intent"] must be one of these
#   safety_risk_not  : str        — safety_risk must NOT equal this
#   safety_risk_is   : str        — safety_risk must equal this (or non-empty if "*")
#   symptoms_have    : list[str]  — any of these must be in ruo["symptoms"]
#   symptoms_none    : bool       — symptoms == ["unclear"]
#   failure_has      : list[str]  — any of these in ruo["failure_types"]
#   failure_none     : bool       — failure_types == ["unknown"]
#   primary_kw       : list[str]  — keyword must appear in ruo["original_query"].lower()
#   equipment_known  : bool       — equipment != "unknown"
#   component_known  : bool       — component != "unknown"
#   ambiguity_gt     : float      — ambiguity_score > value → escalate
#   confidence_lt    : float      — confidence < value

_RULES: list[tuple[str, dict, str, str]] = [

    # 1. SAFETY — always wins when a safety risk is present
    (
        INTENT_SAFETY,
        {"safety_risk_is": "*"},
        INTENT_DIAGNOSE,
        "Immediate safety hazard detected ({safety_risk}). "
        "Provide emergency shutdown steps, then guide repair.",
    ),

    # 2. ERROR_CODE_LOOKUP — has an error code symptom
    (
        INTENT_ERROR_CODE,
        {"symptoms_have": ["error code"], "safety_risk_not": "*"},
        INTENT_DIAGNOSE,
        "User is reporting an error code or warning light. "
        "Look up the code and explain the cause.",
    ),

    # 3. PART_LOOKUP — user explicitly wants a part
    (
        INTENT_PART_LOOKUP,
        {
            "ruo_primary_in": ["diagnose", "repair"],
            "primary_kw": ["what parts", "which parts", "need parts",
                           "buy", "order", "replace part", "new part",
                           "part number"],
            "safety_risk_not": "*",
        },
        INTENT_REPAIR,
        "User wants to know which parts to buy for the repair.",
    ),

    # 4. INSTALLATION — installing new equipment
    (
        INTENT_INSTALLATION,
        {
            "ruo_primary_in": ["repair", "identify"],
            "primary_kw": ["install", "installing", "new install",
                           "hook up", "set up", "mount", "fitting"],
            "safety_risk_not": "*",
        },
        INTENT_CONFIGURATION,
        "User wants to install new equipment or a replacement part.",
    ),

    # 5. CONFIGURATION — settings, programming, app
    (
        INTENT_CONFIGURATION,
        {
            "primary_kw": ["setting", "configure", "program", "app",
                           "pair", "wifi setup", "factory reset",
                           "connect to", "connect the", "reset the"],
            "safety_risk_not": "*",
        },
        INTENT_IDENTIFY,
        "User needs to configure or program a device or system.",
    ),

    # 6. VERIFY_REPAIR — checking if a repair worked (must come before IDENTIFY)
    (
        INTENT_VERIFY,
        {
            "primary_kw": ["repaired correctly", "is it fixed", "working now",
                           "did i fix", "is the repair", "repaired right",
                           "check the fix", "verify repair", "test the repair",
                           "fixed correctly", "working after", "fixed now",
                           "correctly now", "repaired correctly"],
            "safety_risk_not": "*",
        },
        INTENT_MAINTENANCE,
        "User wants to verify a repair was done correctly or is now working.",
    ),

    # 6b. IDENTIFY_COMPONENT — user doesn't know what a part is
    (
        INTENT_IDENTIFY,
        {
            "ruo_primary_in": ["identify"],
            "safety_risk_not": "*",
        },
        INTENT_DIAGNOSE,
        "User wants to identify a component or understand what it is.",
    ),

    # 7. IDENTIFY_COMPONENT (from ruo primary)
    (
        INTENT_IDENTIFY,
        {
            "ruo_primary_in": ["identify"],
            "safety_risk_not": "*",
        },
        INTENT_DIAGNOSE,
        "User wants to identify a component or understand what it is.",
    ),

    # 7b. VERIFY_REPAIR — via ruo primary intent
    (
        INTENT_VERIFY,
        {
            "ruo_primary_in": ["verify"],
            "safety_risk_not": "*",
        },
        INTENT_MAINTENANCE,
        "User wants to verify a repair was done correctly or is working.",
    ),

    # 8. MAINTENANCE — routine service, cleaning, inspection
    (
        INTENT_MAINTENANCE,
        {
            "ruo_primary_in": ["maintenance"],
            "safety_risk_not": "*",
        },
        INTENT_REPAIR,
        "User wants routine maintenance guidance for the equipment.",
    ),

    # 9. REPAIR_GUIDANCE — explicit repair keyword, with or without symptoms
    (
        INTENT_REPAIR,
        {
            "ruo_primary_in": ["repair"],
            "safety_risk_not": "*",
        },
        INTENT_PART_LOOKUP,
        "User knows the problem and wants step-by-step repair instructions.",
    ),

    # 10. ESCALATE — too ambiguous or complexity beyond DIY
    (
        INTENT_ESCALATE,
        {
            "ambiguity_gt": 0.85,
            "safety_risk_not": "*",
        },
        INTENT_DIAGNOSE,
        "Query is too ambiguous to diagnose. "
        "Ask clarifying questions or recommend a technician.",
    ),

    # 11. ESCALATE — explicitly asked for a professional
    (
        INTENT_ESCALATE,
        {
            "primary_kw": ["call a tech", "hire", "professional",
                           "mechanic", "rv technician", "should i call"],
            "safety_risk_not": "*",
        },
        INTENT_SAFETY,
        "User is asking whether to escalate to a professional technician.",
    ),

    # 12. DIAGNOSE_PROBLEM — default when symptoms present (most common)
    (
        INTENT_DIAGNOSE,
        {
            "symptoms_none": False,
            "safety_risk_not": "*",
        },
        INTENT_REPAIR,
        "User has a malfunctioning system. "
        "Identify the root cause and return a repair plan.",
    ),

    # 13. DIAGNOSE_PROBLEM — fallback when nothing else matches
    (
        INTENT_DIAGNOSE,
        {},
        INTENT_NONE,
        "General repair query. Run symptom analysis across the knowledge base.",
    ),
]


# ===========================================================================
# ICEEngine
# ===========================================================================

class ICEEngine:
    """
    Intent Classification Engine.

    Consumes a Repair Understanding Object (RUO) from RQUEngine and
    produces a precise Intent Classification Object (ICO).
    """

    def classify(self, ruo: dict[str, Any]) -> dict[str, Any]:
        """
        Classify the intent from a Repair Understanding Object.

        Parameters
        ----------
        ruo : dict   Output from RQUEngine.understand()

        Returns
        -------
        dict — Intent Classification Object:
        {
          "primary_intent":    "DIAGNOSE_PROBLEM",
          "secondary_intent":  "REPAIR_GUIDANCE",
          "user_goal":         "User has a malfunctioning...",
          "intent_confidence": 0.87,
          "routing_hint":      "run /v2/{version}/analyze → plan",
          "ruo_summary": {
            "equipment":          "generator",
            "symptoms":           ["will not start"],
            "failure_types":      ["ignition failure"],
            "safety_risk":        "none detected",
            "severity":           "High",
            "ambiguity_score":    0.27,
            "equipment_category": "Home Maintenance",
          }
        }
        """
        query_lower = ruo.get("original_query", "").lower()

        for primary, conditions, secondary, goal_template in _RULES:
            if self._matches(ruo, query_lower, conditions):
                goal  = goal_template.format(
                    safety_risk = ruo.get("safety_risk", ""),
                    equipment   = ruo.get("equipment", "unknown"),
                    symptoms    = ", ".join(ruo.get("symptoms", [])),
                )
                confidence = self._score_confidence(ruo, primary)
                return {
                    "primary_intent":    primary,
                    "secondary_intent":  secondary,
                    "user_goal":         goal,
                    "intent_confidence": confidence,
                    "routing_hint":      _ROUTING.get(primary, "run general search"),
                    "ruo_summary": {
                        "equipment":          ruo.get("equipment", "unknown"),
                        "equipment_category": ruo.get("equipment_category", ""),
                        "symptoms":           ruo.get("symptoms", []),
                        "failure_types":      ruo.get("failure_types", []),
                        "safety_risk":        ruo.get("safety_risk", "none detected"),
                        "severity":           ruo.get("severity", "Medium"),
                        "ambiguity_score":    ruo.get("ambiguity_score", 0.5),
                        "environment":        ruo.get("environment", "unspecified"),
                        "language":           ruo.get("language", "en"),
                    },
                }

        # Should never reach here — last rule always matches
        return self._fallback(ruo)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(ruo: dict, query_lower: str, cond: dict) -> bool:
        """Return True if all conditions in `cond` are satisfied by `ruo`."""
        safety = ruo.get("safety_risk", "none detected")
        symptoms  = ruo.get("symptoms", ["unclear"])
        failures  = ruo.get("failure_types", ["unknown"])
        ambiguity = ruo.get("ambiguity_score", 0.5)
        confidence = ruo.get("confidence", 0.5)
        ruo_primary = ruo.get("primary_intent", "diagnose")

        # safety_risk_is: "*" means any non-empty safety risk
        if "safety_risk_is" in cond:
            val = cond["safety_risk_is"]
            if val == "*":
                if safety == "none detected" or not safety:
                    return False
            else:
                if safety != val:
                    return False

        # safety_risk_not: "*" means safety must be "none detected"
        if "safety_risk_not" in cond:
            val = cond["safety_risk_not"]
            if val == "*":
                if safety != "none detected" and safety:
                    return False
            else:
                if safety == val:
                    return False

        if "ruo_primary_in" in cond:
            if ruo_primary not in cond["ruo_primary_in"]:
                return False

        if "symptoms_have" in cond:
            if not any(s in symptoms for s in cond["symptoms_have"]):
                return False

        if "symptoms_none" in cond:
            want_none = cond["symptoms_none"]
            is_none   = symptoms == ["unclear"]
            if want_none and not is_none:
                return False
            if not want_none and is_none:
                return False

        if "failure_has" in cond:
            if not any(f in failures for f in cond["failure_has"]):
                return False

        if "failure_none" in cond:
            if cond["failure_none"] and failures != ["unknown"]:
                return False

        if "primary_kw" in cond:
            if not any(kw in query_lower for kw in cond["primary_kw"]):
                return False

        if "equipment_known" in cond:
            if cond["equipment_known"] and ruo.get("equipment") == "unknown":
                return False

        if "component_known" in cond:
            if cond["component_known"] and ruo.get("component") == "unknown":
                return False

        if "ambiguity_gt" in cond:
            if ambiguity <= cond["ambiguity_gt"]:
                return False

        if "confidence_lt" in cond:
            if confidence >= cond["confidence_lt"]:
                return False

        return True

    @staticmethod
    def _score_confidence(ruo: dict, intent: str) -> float:
        """
        Score how confident we are in this intent assignment.
        Combines RUO confidence with intent-specific signals.
        """
        base = ruo.get("confidence", 0.5)

        # Safety intents are always high confidence when safety_risk is present
        if intent == INTENT_SAFETY:
            return round(min(base + 0.30, 1.0), 2)

        # Escalation is confident when ambiguity is very high
        if intent == INTENT_ESCALATE:
            return round(min(ruo.get("ambiguity_score", 0.5) * 0.9, 1.0), 2)

        # Error code lookup is precise when symptoms clearly state error code
        if intent == INTENT_ERROR_CODE:
            return round(min(base + 0.15, 1.0), 2)

        # Repair guidance confident when symptoms AND equipment are known
        if intent == INTENT_REPAIR:
            bonus = 0.10 if ruo.get("equipment") != "unknown" else 0.0
            bonus += 0.10 if ruo.get("symptoms") != ["unclear"] else 0.0
            return round(min(base + bonus, 1.0), 2)

        # Diagnose defaults to base confidence
        return round(min(base + 0.05, 1.0), 2)

    @staticmethod
    def _fallback(ruo: dict) -> dict:
        return {
            "primary_intent":    INTENT_DIAGNOSE,
            "secondary_intent":  INTENT_NONE,
            "user_goal":         "General repair query — run full diagnostic pipeline.",
            "intent_confidence": 0.40,
            "routing_hint":      _ROUTING[INTENT_DIAGNOSE],
            "ruo_summary": {
                "equipment":          ruo.get("equipment", "unknown"),
                "equipment_category": ruo.get("equipment_category", ""),
                "symptoms":           ruo.get("symptoms", []),
                "failure_types":      ruo.get("failure_types", []),
                "safety_risk":        ruo.get("safety_risk", "none detected"),
                "severity":           ruo.get("severity", "Medium"),
                "ambiguity_score":    ruo.get("ambiguity_score", 0.5),
                "environment":        ruo.get("environment", "unspecified"),
                "language":           ruo.get("language", "en"),
            },
        }
