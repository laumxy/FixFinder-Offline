from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CauseScore:
    cause: str
    confidence: float
    evidence: list[str]


class DiagnosticScorer:
    def rank_causes(self, keywords: list[str], candidate: dict[str, Any]) -> list[CauseScore]:
        symptoms = candidate.get("symptoms", [])
        causes = candidate.get("causes", [])
        semantic_score = float(candidate.get("semantic_score", 0.0))
        keyword_set = set(keywords)

        ranked = []
        for cause in causes:
            cause_terms = set(cause.lower().replace("-", " ").split())
            symptom_evidence = [
                symptom for symptom in symptoms
                if keyword_set.intersection(symptom.lower().replace("-", " ").split())
            ]
            cause_match = len(keyword_set.intersection(cause_terms))
            symptom_match = len(symptom_evidence)
            confidence = min(98.0, 35.0 + (cause_match * 12.0) + (symptom_match * 10.0) + (semantic_score * 25.0))
            ranked.append(
                CauseScore(
                    cause=cause,
                    confidence=round(confidence, 1),
                    evidence=symptom_evidence[:3],
                )
            )

        return sorted(ranked, key=lambda item: item.confidence, reverse=True)
