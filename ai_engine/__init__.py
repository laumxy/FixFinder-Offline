"""
ai_engine
=========
FixFinder AI Engine package.

Modules
-------
retrieval_engine       – FAISS-backed semantic search over systems/symptoms/repairs.
diagnostic_engine      – Keyword scoring + decision-tree traversal for step-by-step diagnosis.
repair_reasoning_engine – Repair recommendation, parts availability, and full plan generation.

Quick start
-----------
    from ai_engine.retrieval_engine        import AIRetrievalEngine
    from ai_engine.diagnostic_engine       import AIDiagnosticEngine
    from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine

    # Semantic search
    with AIRetrievalEngine(version=1) as ret:
        results = ret.search("roof leaking near chimney", top_k=5)

    # Symptom analysis + guided diagnosis
    with AIDiagnosticEngine(version=1) as diag:
        matches = diag.analyze_symptoms("roof is leaking after heavy rain")
        result  = diag.run_diagnostic(
            matches[0]["symptom_code"],
            user_responses=["yes", "no", "yes"],
        )

    # Repair reasoning + parts check + full plan
    with AIRepairReasoningEngine(version=1) as rep:
        recs  = rep.recommend_repair("PRB-ROF-002", diagnostic_result=result)
        avail = rep.check_parts_availability(recs[0]["id"])
        plan  = rep.generate_repair_plan("PRB-ROF-002", diagnostic_result=result)
        print(plan["summary"])
"""

from .retrieval_engine        import AIRetrievalEngine        # noqa: F401
from .diagnostic_engine       import AIDiagnosticEngine       # noqa: F401
from .repair_reasoning_engine import AIRepairReasoningEngine  # noqa: F401
from .rqu_engine              import RQUEngine                # noqa: F401
from .ice_engine              import ICEEngine                # noqa: F401
from .tee_engine              import TechnicalEntityExtractor # noqa: F401
from .equipment_engine        import EquipmentResolver        # noqa: F401
from .cie_engine              import ComponentIdentifier      # noqa: F401
from .failure_modes_engine   import FailureModesEngine       # noqa: F401

__all__ = [
    "AIRetrievalEngine",
    "AIDiagnosticEngine",
    "AIRepairReasoningEngine",
    "RQUEngine",
    "ICEEngine",
    "TechnicalEntityExtractor",
    "EquipmentResolver",
    "ComponentIdentifier",
    "FailureModesEngine",
]
__version__ = "1.7.1"

