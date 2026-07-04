import re
from dataclasses import dataclass, field


# Common misspellings → canonical form
# Keeps the preprocessor resilient to frequent typos without needing a full spell-checker.
COMMON_MISSPELLINGS: dict[str, str] = {
    "vicheal": "vehicle", "vechile": "vehicle", "vehical": "vehicle",
    "vehicale": "vehicle", "vechicle": "vehicle", "vhicle": "vehicle",
    "tyre": "tyre", "tire": "tire",
    "bustr": "burst", "bursted": "burst",
    "break": "brake", "breaks": "brakes",
    "engne": "engine", "enging": "engine", "engin": "engine",
    "refridgerator": "refrigerator", "frige": "fridge",
    "pluming": "plumbing", "plumer": "plumber",
    "electic": "electric", "electrcal": "electrical", "wiring": "wiring",
    "genrator": "generator", "generater": "generator",
    "battrie": "battery", "batery": "battery", "battrey": "battery",
    "motocyle": "motorcycle", "motorcyle": "motorcycle", "motobike": "motorbike",
    "smartfone": "smartphone", "fone": "phone",
    "laptap": "laptop", "labtop": "laptop",
    "cooling": "cooling", "aircon": "aircon",
    "leek": "leak", "leking": "leaking", "leakes": "leaks",
    "nott": "not", "wont": "won't", "dont": "don't",
    "chargeing": "charging", "chargin": "charging",
    "startin": "starting", "staring": "starting",
    "watter": "water", "wate": "water",
    "pump": "pump", "pum": "pump",
    "solar": "solar", "soler": "solar",
    "routr": "router", "routor": "router",
    "printar": "printer", "printter": "printer",
}


def _correct_token(token: str) -> str:
    """Return the corrected form of a token, or the token itself if no correction is known."""
    return COMMON_MISSPELLINGS.get(token, token)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "my", "of", "on", "or", "our",
    "that", "the", "this", "to", "was", "we", "with", "its", "not", "do",
    "does", "did", "no", "so", "if", "up", "out", "any", "all", "been",
    "can", "will", "just", "also", "very", "when", "how", "what", "why",
}


@dataclass(frozen=True)
class ProcessedInput:
    original_text: str
    normalized_text: str
    keywords: list[str]
    language_hint: str = "en"


class NLPPreprocessor:
    def process(self, text: str, language_hint: str = "en") -> ProcessedInput:
        normalized = self._normalize(text)
        # Apply spelling corrections to the normalized text for better FTS/LIKE matching
        corrected_tokens = [
            _correct_token(t) for t in normalized.split()
        ]
        corrected_normalized = " ".join(corrected_tokens)
        keywords = self._extract_keywords(corrected_normalized)
        return ProcessedInput(
            original_text=text.strip(),
            normalized_text=corrected_normalized,
            keywords=keywords,
            language_hint=language_hint,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower().strip()
        # preserve hyphens inside compound words, strip everything else
        lowered = re.sub(r"[^a-z0-9\s\-]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    @staticmethod
    def _extract_keywords(normalized_text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9\-]*", normalized_text)
        seen: set[str] = set()
        result: list[str] = []
        for token in tokens:
            if len(token) > 2 and token not in STOPWORDS and token not in seen:
                # Apply spelling correction
                corrected = _correct_token(token)
                if corrected not in seen:
                    seen.add(corrected)
                    result.append(corrected)
        return result
