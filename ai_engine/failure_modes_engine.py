from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


_FAILURE_MODES: tuple["_FailureMode", ...] = ()


@dataclass(frozen=True)
class _FailureMode:
    code: str
    label: str
    # Evidence tokens/phrases -> positive evidence for this failure mode
    positive: tuple[str, ...]
    # Tokens/phrases that indicate the failure mode is less likely
    negative: tuple[str, ...] = ()


# Deterministic keyword-driven classifier for the requested codes.
# This is intentionally version-agnostic (“new iteration phase”).
_FAILURE_MODES = (
    _FailureMode(
        code="NO_POWER",
        label="No power",
        positive=(
            "no power",
            "dead",
            "not turning on",
            "won't turn on",
            "won't start",
            "no electricity",
            "won't charge",
            "stopped working",
            "no signal",
        ),
        negative=("charging", "power back", "power restored"),
    ),
    _FailureMode(
        code="NO_COOLING",
        label="No cooling",
        positive=(
            "not cooling",
            "doesn't cool",
            "won't cool",
            "not cold",
            "air conditioner not cooling",
            "ac not cooling",
            "refrigerator not cooling",
            "freezer not working",
        ),
    ),
    _FailureMode(
        code="LEAK",
        label="Leak",
        positive=(
            "leak",
            "leaking",
            "dripping",
            "water leak",
            "oil leak",
            "fluid leak",
            "wet",
            "puddles",
        ),
        negative=("no leak", "dry", "not leaking"),
    ),
    _FailureMode(
        code="BLOCKAGE",
        label="Blockage",
        positive=(
            "clog",
            "clogged",
            "blockage",
            "blocked",
            "not draining",
            "won't drain",
            "slow drain",
            "restricted",
        ),
        negative=("unblocked", "cleared"),
    ),
    _FailureMode(
        code="SHORT_CIRCUIT",
        label="Short circuit",
        positive=(
            "short",
            "short circuit",
            "sparks",
            "tripping breaker",
            "blown fuse",
            "fuse blew",
            "electrical arcing",
            "burning smell",
        ),
        negative=("no short",),
    ),
    _FailureMode(
        code="OVERHEATING",
        label="Overheating",
        positive=(
            "overheat",
            "overheating",
            "hot",
            "too hot",
            "thermal",
            "shuts down",
            "shutdown",
            "fan loud",
        ),
        negative=("cooling normal",),
    ),
    _FailureMode(
        code="LOW_PRESSURE",
        label="Low pressure",
        positive=(
            "low pressure",
            "not enough pressure",
            "pressure drop",
            "weak pressure",
            "won't build pressure",
            "doesn't pressurize",
            "low psi",
        ),
    ),
    _FailureMode(
        code="NOISE",
        label="Noise",
        positive=(
            "noisy",
            "noise",
            "buzzing",
            "humming",
            "clicking",
            "rattling",
            "grinding",
            "squealing",
            "whining",
        ),
    ),
    _FailureMode(
        code="VIBRATION",
        label="Vibration",
        positive=(
            "vibration",
            "vibrating",
            "shaking",
            "tremor",
            "wobbling",
            "rumbling",
        ),
    ),
    _FailureMode(
        code="SMOKE",
        label="Smoke",
        positive=(
            "smoke",
            "smoking",
            "burnt",
            "burning",
            "heat damage",
            "looks like it is smoking",
            "trace smoke",
        ),
        negative=("no smoke", "not smoking"),
    ),
    _FailureMode(
        code="INTERMITTENT_FAILURE",
        label="Intermittent failure",
        positive=(
            "intermittent",
            "cuts out",
            "cuts off",
            "stops and starts",
            "comes and goes",
            "randomly",
            "sometimes",
            "on and off",
            "fails sometimes",
            "sporadic",
        ),
    ),
)


class FailureModesEngine:
    """Deterministic failure-mode identifier.

    Input: raw user issue text.
    Output: ranked list of failure modes with evidence.
    """

    def __init__(self) -> None:
        # Precompile patterns for speed.
        self._modes = _FAILURE_MODES

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @staticmethod
    def _negation_span(text: str, idx: int, span: int = 12) -> bool:
        """Check for a nearby negation like 'no', 'not'."""
        start = max(0, idx - span)
        chunk = text[start:idx]
        return bool(re.search(r"\b(no|not|never)\b\s*$", chunk))

    def identify_failure_modes(self, user_input: str, top_k: int = 5) -> list[dict[str, Any]]:
        text = self._norm(user_input)
        if not text:
            return []

        scored: list[dict[str, Any]] = []

        for mode in self._modes:
            evidence: list[str] = []
            score = 0.0

            for phrase in mode.positive:
                # phrase match as substring
                pos = text.find(phrase)
                if pos == -1:
                    continue

                # If negated phrase appears close to 'not/no', treat as weaker evidence.
                negated = self._negation_span(text, pos)

                # base weights tuned for reasonable ranking (deterministic)
                weight = 0.35
                if phrase in {"leak", "leaking", "short circuit", "short" , "smoke"}:
                    weight = 0.55
                elif phrase in {"no power", "dead", "not turning on", "won't turn on"}:
                    weight = 0.6
                elif phrase in {"overheating", "overheat"}:
                    weight = 0.5

                if negated:
                    weight *= 0.25
                    evidence.append(f"(negated) {phrase}")
                else:
                    evidence.append(phrase)

                score += weight

            # Negative evidence
            for phrase in mode.negative:
                if phrase in text and not self._negation_span(text, text.find(phrase)):
                    score -= 0.25
                    evidence.append(f"(negative) {phrase}")

            # Clamp and convert to confidence-like score
            score = max(0.0, min(1.0, round(score, 4)))

            if score > 0:
                scored.append({
                    "code": mode.code,
                    "label": mode.label,
                    "score": score,
                    "evidence": evidence[:6],
                })

        scored.sort(key=lambda x: (x["score"], len(x.get("evidence", []))), reverse=True)
        return scored[: max(1, top_k)]


# Convenience singleton (stateless)
engine_singleton: Optional[FailureModesEngine] = None


def get_failure_modes_engine() -> FailureModesEngine:
    global engine_singleton
    if engine_singleton is None:
        engine_singleton = FailureModesEngine()
    return engine_singleton

