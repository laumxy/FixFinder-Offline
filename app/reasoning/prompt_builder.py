import json
from typing import Any

from app.diagnosis.engine import DiagnosisResult
from app.nlp.preprocess import ProcessedInput


class PromptBuilder:
    def build(
        self,
        user_problem: str,
        processed: ProcessedInput,
        diagnosis: DiagnosisResult,
        questions: list[str],
    ) -> str:
        context = diagnosis.to_report(follow_up_questions=questions)
        return (
            "You are FIXFINDER OFFLINE AI ENGINE v2, a repair troubleshooting assistant.\n"
            "Use only the structured knowledge provided below. Do not invent repair steps, tools, causes, or safety rules.\n"
            "If confidence is low or required knowledge is missing, explain that more inspection is needed and ask the provided questions.\n"
            "Return concise practical guidance. Always mention safety before repair work.\n\n"
            f"USER_PROBLEM: {user_problem}\n"
            f"NORMALIZED_INPUT: {processed.normalized_text}\n"
            f"KEYWORDS: {', '.join(processed.keywords)}\n"
            "STRUCTURED_KNOWLEDGE_JSON:\n"
            f"{json.dumps(context, indent=2)}\n\n"
            "Write the final_answer text only. Do not output extra JSON."
        )

    @staticmethod
    def fallback_answer(report: dict[str, Any]) -> str:
        safety = " ".join(report.get("safety", []))
        inspections = " ".join(report.get("inspection_steps", [])[:2])
        repairs = " ".join(report.get("repair_steps", [])[:3])
        questions = " ".join(report.get("follow_up_questions", []))
        if not repairs:
            return (
                "Need more information. The local knowledge base does not contain enough repair steps for this problem. "
                f"Start with safety checks: {safety or 'stop work if there is immediate danger.'} "
                f"Answer these follow-up questions before repair: {questions}"
            ).strip()
        confidence = "unknown"
        confidence_scores = report.get("confidence_scores", [])
        if confidence_scores:
            confidence = confidence_scores[0].get("confidence", "unknown")
        return (
            f"Most likely issue: {report.get('problem')} with confidence {confidence}. "
            f"Safety first: {safety} Inspection: {inspections} Repair: {repairs}"
        ).strip()
