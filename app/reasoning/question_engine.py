from typing import Any

from app.nlp.preprocess import ProcessedInput
from fixfinder_engine.config import settings


CATEGORY_QUESTIONS: dict[str, list[str]] = {
    "roofing": [
        "Does the leak happen only during rain or also after rain has stopped?",
        "Can you see missing shingles, cracked tiles, or damaged flashing near the leak?",
        "Is there a visible water stain in the attic directly above the ceiling mark?",
    ],
    "vehicles": [
        "Do the dashboard lights come on when you turn the key?",
        "Do you hear clicking, cranking, or complete silence when starting?",
        "When was the battery last tested or replaced?",
    ],
    "plumbing": [
        "Is the leak coming from the tap handle, spout, or pipe connection below?",
        "Does the dripping continue when the handle is fully closed?",
        "Can you shut off the water supply valve under the sink?",
    ],
    "electrical": [
        "Has the breaker tripped or does it trip again after reset?",
        "Is there any burning smell, buzzing, heat, or visible damage?",
        "Does the issue affect one outlet or the whole circuit?",
    ],
    "appliances": [
        "Does the appliance power on and show any error code?",
        "When did the problem start and did anything change before it happened?",
        "Is there unusual noise, heat, smell, or leakage?",
    ],
    "farming": [
        "Which crop or animal is affected and at what growth stage?",
        "What symptoms do you see on leaves, stems, soil, or yield?",
        "Has rainfall, irrigation, fertilizer, or pesticide use recently changed?",
    ],
    "electronics": [
        "Does the device power on, charge, or show any indicator light?",
        "Was it dropped, exposed to water, or repaired recently?",
        "Does the problem happen with another charger, cable, or screen?",
    ],
    "general": [
        "What exact symptom do you see, hear, or smell?",
        "When did the problem start?",
        "What changed just before the problem appeared?",
    ],
}


class QuestionEngine:
    def generate(
        self,
        category: str,
        processed: ProcessedInput,
        top_match: dict[str, Any] | None,
        confidence: float,
    ) -> list[str]:
        if confidence >= settings.confidence_threshold:
            return []

        questions = CATEGORY_QUESTIONS.get(category, CATEGORY_QUESTIONS["general"]).copy()
        if top_match:
            missing_symptoms = [
                symptom for symptom in top_match.get("symptoms", [])
                if not set(processed.keywords).intersection(symptom.lower().split())
            ]
            if missing_symptoms:
                questions.insert(0, f"Do you also notice this symptom: {missing_symptoms[0]}?")
        return questions[:4]
