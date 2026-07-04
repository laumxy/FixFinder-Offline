from dataclasses import dataclass
from typing import Any

from app.diagnosis.scoring import CauseScore, DiagnosticScorer
from app.nlp.preprocess import ProcessedInput


@dataclass
class DiagnosisResult:
    category: str
    problem: str
    top_match: dict[str, Any] | None
    ranked_causes: list[CauseScore]
    confidence: float

    def to_report(self, follow_up_questions: list[str]) -> dict[str, Any]:
        match = self.top_match or {}
        confidence_scores = []
        for index, item in enumerate(self.ranked_causes):
            visible_confidence = self.confidence if index == 0 else item.confidence
            confidence_scores.append(
                {
                    "cause": item.cause,
                    "confidence": f"{visible_confidence:.1f}%",
                    "evidence": item.evidence,
                }
            )
        return {
            "category": self.category,
            "problem": self.problem,
            "ranked_causes": [item.cause for item in self.ranked_causes],
            "confidence_scores": confidence_scores,
            "follow_up_questions": follow_up_questions,
            "inspection_steps": match.get("inspection_steps", []),
            "repair_steps": match.get("repair_steps", []),
            "tools": match.get("tools", []),
            "safety": match.get("safety", []),
            "prevention": match.get("prevention", []),
            "final_answer": "",
        }


class DiagnosticEngine:
    def __init__(self) -> None:
        self.scorer = DiagnosticScorer()

    def score(
        self,
        processed: ProcessedInput,
        category: str,
        candidates: list[dict[str, Any]],
    ) -> DiagnosisResult:
        if not candidates:
            return DiagnosisResult(
                category=category,
                problem=processed.original_text,
                top_match=None,
                ranked_causes=[
                    CauseScore(
                        cause="Insufficient local knowledge match",
                        confidence=25.0,
                        evidence=[],
                    )
                ],
                confidence=25.0,
            )

        best = candidates[0]
        ranked_causes = self.scorer.rank_causes(processed.keywords, best)
        confidence = ranked_causes[0].confidence if ranked_causes else 45.0
        category_bonus = 5.0 if category == best.get("category") else 0.0
        confidence = min(98.0, confidence + category_bonus)

        return DiagnosisResult(
            category=best.get("category", category),
            problem=best.get("problem", processed.original_text),
            top_match=best,
            ranked_causes=ranked_causes,
            confidence=round(confidence, 1),
        )
