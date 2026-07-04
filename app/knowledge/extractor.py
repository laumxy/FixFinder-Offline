from app.database.models import KnowledgeProblem, LearningSource
from app.knowledge.cleaner import KnowledgeCleaner
from app.nlp.classifier import ProblemClassifier
from app.nlp.preprocess import NLPPreprocessor


SYMPTOM_WORDS = ("symptom", "drip", "leak", "click", "noise", "warm", "yellow", "dim", "smell", "stain", "does not")
CAUSE_WORDS = ("cause", "because", "fault", "failed", "worn", "blocked", "damaged", "loose", "dirty")
REPAIR_WORDS = ("replace", "clean", "tighten", "reset", "inspect", "check", "repair", "remove", "install", "test")
TOOL_WORDS = ("tool", "wrench", "screwdriver", "meter", "multimeter", "ladder", "gloves", "scanner", "brush")
SAFETY_WORDS = ("safety", "danger", "turn off", "shut off", "unplug", "protective", "do not", "call a professional")


class KnowledgeExtractor:
    def __init__(self) -> None:
        self.cleaner = KnowledgeCleaner()
        self.preprocessor = NLPPreprocessor()
        self.classifier = ProblemClassifier()

    def extract(self, source: LearningSource, version: str) -> KnowledgeProblem | None:
        raw_text = source.text
        if not raw_text and source.url:
            return None

        text = self.cleaner.clean_text(raw_text)
        if len(text) < 120 or not self.cleaner.is_safe(text):
            return None

        processed = self.preprocessor.process(text[:500])
        category = source.category if source.category != "general" else self.classifier.classify(processed)
        sentences = self.cleaner.split_sentences(text)

        symptoms = self._pick(sentences, SYMPTOM_WORDS)
        causes = self._pick(sentences, CAUSE_WORDS)
        repair_steps = self._pick(sentences, REPAIR_WORDS)
        tools = self._extract_tools(sentences)
        safety = self._pick(sentences, SAFETY_WORDS)

        if not repair_steps or not causes:
            return None

        problem = self._problem_title(processed.keywords, category)
        reliability = self._reliability(source.source_type, bool(source.url), symptoms, causes, repair_steps, safety)
        if reliability < 0.45:
            return None

        return KnowledgeProblem(
            category=category,
            problem=problem,
            aliases=[problem.lower()],
            symptoms=symptoms or ["User-reported symptoms require confirmation."],
            causes=causes,
            inspection_steps=self.cleaner.unique_list(
                [step for step in repair_steps if step.lower().startswith(("inspect", "check", "test"))],
                limit=5,
            ) or ["Inspect the affected area and confirm the source before repair."],
            repair_steps=repair_steps,
            tools=tools or ["flashlight", "protective gloves"],
            safety=safety or ["Stop work if there is immediate danger and use appropriate protective equipment."],
            prevention=["Inspect the system periodically and fix early symptoms before they worsen."],
            difficulty="moderate",
            risk_level="medium",
            estimated_time="varies by confirmed cause",
            source_type=source.source_type,
            source_url=source.url,
            reliability_score=reliability,
            confidence_score=reliability,
            knowledge_version=version,
        )

    def _pick(self, sentences: list[str], words: tuple[str, ...]) -> list[str]:
        picked = [sentence for sentence in sentences if any(word in sentence.lower() for word in words)]
        return self.cleaner.unique_list(picked, limit=6)

    def _extract_tools(self, sentences: list[str]) -> list[str]:
        tools = []
        for sentence in sentences:
            lowered = sentence.lower()
            if any(word in lowered for word in TOOL_WORDS):
                for tool in ("wrench", "screwdriver", "multimeter", "ladder", "gloves", "scanner", "brush", "flashlight"):
                    if tool in lowered:
                        tools.append(tool)
        return self.cleaner.unique_list(tools, limit=8)

    def _problem_title(self, keywords: list[str], category: str) -> str:
        joined = " ".join(keywords)
        known_patterns = [
            "washing machine not draining",
            "refrigerator not cooling",
            "phone not charging",
            "car not starting",
            "engine not starting",
            "tap leaking",
            "roof leak",
        ]
        for pattern in known_patterns:
            if pattern in joined:
                return pattern.title()
        useful = [
            word for word in keywords
            if word not in {"repair", "problem", "issue", "system", "can", "such", "include", "show", "shows"}
        ]
        title_words = useful[:5] or [category, "repair", "issue"]
        return " ".join(title_words).title()

    def _reliability(
        self,
        source_type: str,
        has_url: bool,
        symptoms: list[str],
        causes: list[str],
        repair_steps: list[str],
        safety: list[str],
    ) -> float:
        score = 0.35
        if source_type in {"manual", "public_documentation", "manufacturer"}:
            score += 0.25
        elif source_type in {"technical_blog", "forum", "reddit"}:
            score += 0.12
        if has_url:
            score += 0.08
        if symptoms:
            score += 0.08
        if causes:
            score += 0.1
        if len(repair_steps) >= 2:
            score += 0.1
        if safety:
            score += 0.04
        return round(min(score, 0.95), 2)
