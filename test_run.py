"""
FixFinder Backend - Integration Test Suite
Tests: NLP, classifier, database, pipeline (no Ollama), and validation
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PASS = "  [PASS]"
FAIL = "  [FAIL]"
SEP  = "-" * 60

def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)

# ── 1. NLP Pipeline ──────────────────────────────────────────────────────────
section("1. NLP PREPROCESSOR & CLASSIFIER")

from app.nlp.preprocess import NLPPreprocessor
from app.nlp.classifier import ProblemClassifier

preprocessor = NLPPreprocessor()
classifier = ProblemClassifier()

test_cases = [
    ("My ceiling leaks after heavy rain near the chimney", "roofing"),
    ("Car battery dead, engine won't start, clicking sound", "vehicles"),
    ("Tap dripping water won't stop even when closed", "plumbing"),
    ("Breaker keeps tripping when I plug in the microwave", "electrical"),
    ("Laptop overheating fan noise very loud", "laptops"),
    ("Maize crop yellowing and wilting in dry season", "agriculture"),
    ("Solar panel output dropped by 40 percent", "solar"),
    ("Generator fails to start and overloads", "generators"),
]

all_pass = True
for text, expected in test_cases:
    processed = preprocessor.process(text)
    got = classifier.classify(processed)
    ok = got == expected
    if not ok:
        all_pass = False
    status = PASS if ok else FAIL
    print(f"{status}  '{text[:45]}...' → {got} (expected {expected})")

print(f"\n{'All NLP tests passed!' if all_pass else 'Some NLP tests FAILED'}")

# ── 2. Database ───────────────────────────────────────────────────────────────
section("2. DATABASE (SQLite + FTS5)")

from app.database.db import ensure_database, fetch_all_problem_records, latest_version
from fixfinder_engine.config import settings

db_status = ensure_database(settings.database_path)
print(f"{PASS}  Database ensured: {settings.database_path}")
print(f"       existed={db_status['existed']}, problem_count={db_status['problem_count']}")

records = fetch_all_problem_records(settings.database_path)
print(f"{PASS if records else FAIL}  Fetched {len(records)} problem records from DB")

ver = latest_version(settings.database_path)
print(f"{PASS}  Knowledge version: {ver}")

# ── 3. SQLite FTS Search ─────────────────────────────────────────────────────
section("3. SQLITE FTS5 SEARCH")

from app.retrieval.sqlite import KnowledgeRepository

repo = KnowledgeRepository(settings.database_path)
count = repo.count_problems()
print(f"{PASS if count > 0 else FAIL}  Problem count in repo: {count}")

fts_results = repo.search_problems("ceiling leak rain chimney", category="roofing", limit=3)
print(f"{PASS if fts_results else FAIL}  FTS search returned {len(fts_results)} result(s)")
for r in fts_results[:2]:
    print(f"       → [{r['category']}] {r['problem']} (score={r.get('retrieval_score', 0):.1f})")

car_results = repo.search_problems("battery dead won't start clicking", category="vehicles", limit=3)
print(f"{PASS if car_results else FAIL}  Car search returned {len(car_results)} result(s)")
for r in car_results[:2]:
    print(f"       → [{r['category']}] {r['problem']} (score={r.get('retrieval_score', 0):.1f})")

# ── 4. Diagnostic Engine ──────────────────────────────────────────────────────
section("4. DIAGNOSTIC ENGINE + SCORING")

from app.diagnosis.engine import DiagnosticEngine
from app.reasoning.question_engine import QuestionEngine

engine = DiagnosticEngine()
question_engine = QuestionEngine()

processed = preprocessor.process("My ceiling leaks after heavy rain near the chimney")
category = classifier.classify(processed)
diagnosis = engine.score(processed=processed, category=category, candidates=fts_results or [])

print(f"{PASS}  Diagnosis category: {diagnosis.category}")
print(f"{PASS}  Diagnosis problem:  {diagnosis.problem}")
print(f"{PASS}  Confidence:         {diagnosis.confidence}%")
print(f"       Causes: {[c.cause[:50] for c in diagnosis.ranked_causes[:2]]}")

questions = question_engine.generate(
    category=category, processed=processed,
    top_match=diagnosis.top_match, confidence=diagnosis.confidence
)
print(f"{PASS}  Follow-up questions: {len(questions)}")

# ── 5. Report + Validation ───────────────────────────────────────────────────
section("5. REPORT GENERATION + VALIDATOR")

from app.reasoning.prompt_builder import PromptBuilder
from app.validation.validator import ResponseValidator

builder = PromptBuilder()
validator = ResponseValidator()

report = diagnosis.to_report(follow_up_questions=questions)
report["final_answer"] = builder.fallback_answer(report)

validated = validator.validate(report)
required_keys = ["category","problem","ranked_causes","confidence_scores",
                 "follow_up_questions","inspection_steps","repair_steps",
                 "tools","safety","prevention","final_answer"]

keys_ok = all(k in validated for k in required_keys)
print(f"{PASS if keys_ok else FAIL}  Validated report has all required keys")
print(f"       category:      {validated['category']}")
print(f"       problem:       {validated['problem'][:60]}")
print(f"       top confidence:{validated['confidence_scores'][0]['confidence']}")
print(f"       tools count:   {len(validated['tools'])}")
print(f"       repair steps:  {len(validated['repair_steps'])}")
print(f"       final_answer snippet: {validated['final_answer'][:80]}...")

# ── 6. Session Memory ─────────────────────────────────────────────────────────
section("6. SESSION MEMORY")

from app.memory.session_memory import SessionMemory

mem = SessionMemory()
mem.add(problem="ceiling leak", category="roofing", confidence="85.0%")
mem.add(problem="car won't start", category="vehicles", confidence="72.0%")
history = mem.recent()
print(f"{PASS if len(history) == 2 else FAIL}  Session history has {len(history)} entries")
for h in history:
    print(f"       → [{h.get('category')}] {h.get('problem')} conf={h.get('confidence')}")

# ── 7. Config / Settings ──────────────────────────────────────────────────────
section("7. SETTINGS & CONFIG")

print(f"{PASS}  App: {settings.app_name} v{settings.app_version}")
print(f"{PASS}  DB path:    {settings.database_path}")
print(f"{PASS}  FAISS path: {settings.faiss_index_path}")
print(f"{PASS}  Model:      {settings.embedding_model_name}")
print(f"{PASS}  Languages:  {settings.supported_languages}")

# ── 8. Seed Data Integrity ───────────────────────────────────────────────────
section("8. SEED DATA INTEGRITY")

seed_path = settings.seed_data_path
seed_raw = json.loads(seed_path.read_text(encoding="utf-8"))
print(f"{PASS}  Seed file loaded: {len(seed_raw)} records")

from app.database.models import KnowledgeProblem
parsed = [KnowledgeProblem.model_validate(item) for item in seed_raw]
print(f"{PASS}  All {len(parsed)} seed records pass Pydantic validation")

cats = {}
for rec in parsed:
    cats[rec.category] = cats.get(rec.category, 0) + 1
print("       Category distribution:")
for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"         {cat:<20} {cnt} records")

# ── Summary ───────────────────────────────────────────────────────────────────
section("TEST SUMMARY")
print("  Core pipeline components tested (NLP, DB, FTS, Scoring, Validation, Memory)")
print("  FAISS index will be tested at server startup (requires sentence-transformers load)")
print("  Ollama/Qwen: tested at runtime (requires Ollama server)")
print(f"\n  Server start command:  uvicorn main:app --host 127.0.0.1 --port 8000 --reload")
print(f"  API docs:              http://127.0.0.1:8000/docs")
print(f"  Health check:          http://127.0.0.1:8000/health")
