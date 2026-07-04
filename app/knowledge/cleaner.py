import re


UNSAFE_PATTERNS = [
    r"\bbypass\b.*\bbreaker\b",
    r"\bremove\b.*\bsafety\b",
    r"\bignore\b.*\bleak\b",
    r"\bshort\b.*\bwires\b",
]


class KnowledgeCleaner:
    def clean_text(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"https?://\S+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def is_safe(self, text: str) -> bool:
        lowered = text.lower()
        return not any(re.search(pattern, lowered) for pattern in UNSAFE_PATTERNS)

    def split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [sentence.strip(" -:\t\r\n") for sentence in sentences if len(sentence.strip()) > 12]

    def unique_list(self, values: list[str], limit: int = 8) -> list[str]:
        seen = set()
        result = []
        for value in values:
            normalized = re.sub(r"\s+", " ", value.strip())
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
            if len(result) >= limit:
                break
        return result
