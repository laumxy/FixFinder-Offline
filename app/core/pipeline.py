from app.ai.qwen_client import QwenClient
from app.analytics.tracker import tracker as analytics_tracker
from app.conversation import ConversationManager, ConversationSession, ConversationTurn
from app.database.db import latest_version
from app.diagnosis.engine import DiagnosticEngine
from app.localization.translator import localizer
from app.memory.session_memory import SessionMemory
from app.nlp.classifier import ProblemClassifier
from app.nlp.preprocess import NLPPreprocessor
from app.reasoning.prompt_builder import PromptBuilder
from app.reasoning.question_engine import QuestionEngine
from app.retrieval.faiss_index import FaissSearch
from app.retrieval.sqlite import KnowledgeRepository
from app.validation.validator import ResponseValidator
from fixfinder_engine.config import settings


class FixFinderPipeline:
    def __init__(self) -> None:
        self.preprocessor = NLPPreprocessor()
        self.classifier = ProblemClassifier()
        self.repository = KnowledgeRepository(settings.database_path)
        self.vector_search = FaissSearch(
            index_path=settings.faiss_index_path,
            metadata_path=settings.faiss_metadata_path,
            model_name=settings.embedding_model_name,
        )
        self.diagnostic_engine = DiagnosticEngine()
        self.question_engine = QuestionEngine()
        self.prompt_builder = PromptBuilder()
        self.qwen_client = QwenClient()
        self.validator = ResponseValidator()
        self.memory = SessionMemory()
        self.conversations = ConversationManager()

    def health(self) -> dict:
        faiss_status = self.vector_search.status()
        ollama_status = self.qwen_client.health()
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "database_exists": settings.database_path.exists(),
            "database_problem_count": self.repository.count_problems(),
            "knowledge_version": latest_version(settings.database_path),
            "faiss_index_exists": settings.faiss_index_path.exists(),
            "faiss": faiss_status,
            "ollama": ollama_status,
            "offline_first": True,
        }

    def run(self, user_problem: str, language: str = "en", session_id: str = "", user_id: int | None = None) -> dict:
        # Detect language from input if caller did not specify
        if language == "en":
            detected = localizer.detect_language(user_problem)
            if detected != "en":
                language = detected

        processed = self.preprocessor.process(user_problem)
        category = self.classifier.classify(processed)

        keyword_matches = self.repository.search_problems(
            query=processed.normalized_text,
            category=category,
            limit=settings.retrieval_limit,
        )
        vector_matches = self.vector_search.search(
            query=processed.normalized_text,
            category=category,
            limit=settings.retrieval_limit,
        )
        candidates = self.repository.merge_matches(keyword_matches, vector_matches)

        diagnosis = self.diagnostic_engine.score(
            processed=processed,
            category=category,
            candidates=candidates,
        )

        questions = self.question_engine.generate(
            category=category,
            processed=processed,
            top_match=diagnosis.top_match,
            confidence=diagnosis.confidence,
        )

        structured_report = diagnosis.to_report(follow_up_questions=questions)
        prompt = self.prompt_builder.build(
            user_problem=user_problem,
            processed=processed,
            diagnosis=diagnosis,
            questions=questions,
        )

        ai_answer = self.qwen_client.generate(prompt) if diagnosis.top_match else ""
        structured_report["final_answer"] = ai_answer or self.prompt_builder.fallback_answer(structured_report)
        structured_report["_engine"] = {
            "ai_reasoning": "ollama" if ai_answer else "offline_fallback",
            "ollama_error": self.qwen_client.last_error,
        }

        validated = self.validator.validate(structured_report)

        # Localise labels if non-English
        if language != "en":
            validated = localizer.translate_report(validated, language)

        top_confidence = float(
            validated["confidence_scores"][0]["confidence"].rstrip("%")
        ) if validated["confidence_scores"] else 0.0

        self.memory.add(
            problem=validated["problem"],
            category=validated["category"],
            confidence=validated["confidence_scores"][0]["confidence"] if validated["confidence_scores"] else "0.0%",
        )

        # Compute knowledge_version once and reuse — avoids a second DB call.
        knowledge_ver = latest_version(settings.database_path)

        analytics_tracker.record_diagnose(
            category=validated["category"],
            problem=validated["problem"],
            confidence=top_confidence,
            language=language,
            user_id=user_id,
            knowledge_version=knowledge_ver,
            session_id=session_id,
        )

        return validated

    # ── Conversational diagnosis ──────────────────────────────────────────────

    def converse(self, message: str, session_id: str = "", language: str = "en") -> dict:
        """
        Multi-turn conversational diagnosis.
        Optimised: question turns are lightweight (preprocess + classify only).
        Only the final diagnosis turn runs the full pipeline.
        """
        session = self.conversations.get_or_create(session_id)

        # Record user turn
        session.turns.append(ConversationTurn(role="user", content=message))

        # First message = problem description
        if not session.original_problem:
            session.original_problem = message

        # Accumulate answers
        session.answers.append(message if session.original_problem != message else "")
        enriched_text = session.original_problem
        extra_context = [a for a in session.answers if a and a != session.original_problem]
        if extra_context:
            enriched_text += " " + " ".join(extra_context)

        # ── Lightweight path: preprocess + classify (no FAISS, no scoring) ──
        processed = self.preprocessor.process(enriched_text)
        category = self.classifier.classify(processed)
        session.category = category

        # ── Question turn: fast path ──────────────────────────────────────
        max_rounds = 3
        batch_size = 2
        batch_start = session.question_index * batch_size
        batch_end = batch_start + batch_size

        # Get category questions (cheap — no FAISS or scoring needed)
        from app.reasoning.question_engine import CATEGORY_QUESTIONS
        cat_questions = CATEGORY_QUESTIONS.get(category, CATEGORY_QUESTIONS["general"]).copy()
        batch = cat_questions[batch_start:batch_end]

        ask_questions = (
            batch
            and session.question_index < max_rounds
        )

        if ask_questions:
            session.question_index += 1
            session.pending_questions = batch

            ack = f"I understand you're dealing with: **{session.original_problem}** (category: {category})."
            if extra_context:
                ack += "\nThanks for the extra details."
            ack += "\nI need a bit more info to narrow this down:"

            session.turns.append(ConversationTurn(
                role="assistant",
                content=ack,
                questions=batch,
            ))

            return {
                "session_id": session.session_id,
                "type": "questions",
                "message": ack,
                "questions": batch,
                "category": category,
                "confidence": 0.0,
                "turn": len(session.turns),
            }

        # ── Diagnosis turn: full pipeline (only once) ─────────────────────
        keyword_matches = self.repository.search_problems(
            query=processed.normalized_text,
            category=category,
            limit=settings.retrieval_limit,
        )
        vector_matches = self.vector_search.search(
            query=processed.normalized_text,
            category=category,
            limit=settings.retrieval_limit,
        )
        candidates = self.repository.merge_matches(keyword_matches, vector_matches)

        diagnosis = self.diagnostic_engine.score(
            processed=processed,
            category=category,
            candidates=candidates,
        )

        structured_report = diagnosis.to_report(follow_up_questions=[])
        prompt = self.prompt_builder.build(
            user_problem=session.original_problem,
            processed=processed,
            diagnosis=diagnosis,
            questions=[],
        )

        if extra_context:
            prompt += f"\n\nUSER_PROVIDED_CONTEXT:\n{chr(10).join(extra_context)}"

        # Use the cached is_available() instead of a fresh health() HTTP call.
        ai_answer = ""
        if self.qwen_client.is_available() and diagnosis.top_match:
            ai_answer = self.qwen_client.generate(prompt)

        structured_report["final_answer"] = ai_answer or self.prompt_builder.fallback_answer(structured_report)
        structured_report["_engine"] = {
            "ai_reasoning": "ollama" if ai_answer else "offline_fallback",
            "ollama_error": self.qwen_client.last_error,
        }

        validated = self.validator.validate(structured_report)

        if language != "en":
            validated = localizer.translate_report(validated, language)

        top_conf = float(
            validated["confidence_scores"][0]["confidence"].rstrip("%")
        ) if validated["confidence_scores"] else 0.0

        # Compute knowledge_version once — avoids a second DB round-trip.
        knowledge_ver = latest_version(settings.database_path)

        analytics_tracker.record_diagnose(
            category=validated["category"],
            problem=validated["problem"],
            confidence=top_conf,
            language=language,
            user_id=None,
            knowledge_version=knowledge_ver,
            session_id=session.session_id,
        )

        self.memory.add(
            problem=validated["problem"],
            category=validated["category"],
            confidence=validated["confidence_scores"][0]["confidence"] if validated["confidence_scores"] else "0.0%",
        )

        # Build the response message
        if ai_answer:
            response_text = ai_answer
        else:
            response_text = f"Based on my analysis, the most likely issue is: **{validated['problem']}**"
            if validated.get("repair_steps"):
                response_text += "\n\nHere's what to do:"
                for i, step in enumerate(validated["repair_steps"][:5], 1):
                    response_text += f"\n{i}. {step}"
            if validated.get("safety"):
                response_text += "\n\n**Safety:** " + "; ".join(validated["safety"][:3])

        session.turns.append(ConversationTurn(
            role="assistant",
            content=response_text,
            diagnostic=validated,
        ))
        self.conversations.end(session.session_id)

        return {
            "session_id": session.session_id,
            "type": "diagnosis",
            "message": response_text,
            "questions": [],
            "category": validated["category"],
            "confidence": diagnosis.confidence,
            "diagnostic": validated,
            "turn": len(session.turns),
        }
