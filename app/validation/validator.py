from typing import Any


REQUIRED_KEYS = [
    "category",
    "problem",
    "ranked_causes",
    "confidence_scores",
    "follow_up_questions",
    "inspection_steps",
    "repair_steps",
    "tools",
    "safety",
    "prevention",
    "final_answer",
]


class ResponseValidator:
    def validate(self, report: dict[str, Any]) -> dict[str, Any]:
        for key in REQUIRED_KEYS:
            report.setdefault(key, [] if key not in {"category", "problem", "final_answer"} else "")

        if not report["category"]:
            report["category"] = "general"

        if not report["problem"]:
            report["problem"] = "Need more information"

        if not report["ranked_causes"]:
            report["ranked_causes"] = ["Need more information"]

        if not report["confidence_scores"]:
            report["confidence_scores"] = [
                {
                    "cause": "Need more information",
                    "confidence": "0.0%",
                    "evidence": [],
                }
            ]

        report.pop("questions", None)

        if not report["safety"]:
            report["safety"] = [
                "Stop work if there is immediate danger, fire risk, gas smell, structural instability, or live electrical exposure.",
                "Use appropriate protective equipment and call a qualified professional for high-risk work.",
            ]

        if not report["tools"]:
            report["tools"] = ["flashlight", "protective gloves", "notebook or phone camera for inspection photos"]

        if not report["repair_steps"]:
            report["repair_steps"] = [
                "Do not begin repair until the source is confirmed.",
                "Collect the follow-up answers and inspect the likely failure points safely.",
                "Use a qualified technician if the problem involves structural, fuel, or electrical hazards.",
            ]

        allowed_steps = set(report["repair_steps"])
        answer = str(report.get("final_answer", "")).strip()
        if not answer:
            answer = "Need more information. Use the structured inspection and repair steps provided. Start with the safety warnings before touching the system."

        if "Safety" not in answer and "safety" not in answer:
            answer = "Safety first: review the safety warnings before inspection or repair. " + answer

        report["final_answer"] = answer
        report["repair_steps"] = [step for step in report["repair_steps"] if step in allowed_steps]
        return {key: report[key] for key in REQUIRED_KEYS}
