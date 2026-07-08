from __future__ import annotations

import itertools
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .schema import RepairObject
from .taxonomy_manager import TaxonomyManager
from .symptom_builder import SymptomBuilder
from .diagnostic_builder import DiagnosticBuilder
from .cause_builder import CauseBuilder
from .repair_step_builder import RepairStepBuilder
from .safety_builder import SafetyBuilder
from .exporter import Exporter
from .symptom_intelligence import SymptomIntelligenceGenerator
from .diagnostic_reasoner import DiagnosticReasoner


class KnowledgeFactoryEngine:
    """FKFE: generate repair objects from taxonomy and export artifacts."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or Path.cwd())
        self.taxonomy = TaxonomyManager(base_dir=self.base_dir / "taxonomy")
        self.symptom_builder = SymptomBuilder()
        self.diagnostic_builder = DiagnosticBuilder()
        self.cause_builder = CauseBuilder()
        self.repair_step_builder = RepairStepBuilder()
        self.safety_builder = SafetyBuilder()
        self.exporter = Exporter(output_dir=self.base_dir)

    def generate_version(self, version_name: str, category_name: str, output_dir: str | Path | None = None, per_equipment_limit: int = 200) -> Dict[str, Any]:
        out_dir = Path(output_dir or self.base_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ensure taxonomy files exist
        self.taxonomy.ensure_seeded()
        version = self.taxonomy.load_version(version_name)
        if not version:
            raise FileNotFoundError(f"Taxonomy version not found: {version_name}")

        # find the requested category or equipment
        target = None
        for c in version.get("categories", []):
            if c.get("name", "").lower() == category_name.lower():
                target = c
                break
            for eq in c.get("equipment", []):
                if eq.get("name", "").lower() == category_name.lower():
                    target = c
                    break
            if target:
                break

        if not target:
            raise ValueError(f"Category/equipment not found: {category_name}")

        objects: List[RepairObject] = []
        for eq in target.get("equipment", []):
            eq_name = eq.get("name")
            components = eq.get("components") or []
            problems = eq.get("problems") or []
            for comp, prob in itertools.islice(itertools.product(components, problems), 0, per_equipment_limit):
                ro = RepairObject(
                    id=str(uuid.uuid4()),
                    title=f"{eq_name} {comp} - {prob}",
                    description=f"{comp} on {eq_name} experiencing {prob}.",
                    equipment=eq_name,
                    category=target.get("name"),
                    symptoms=self.symptom_builder.build(eq_name, comp, prob),
                    causes=self.cause_builder.build(eq_name, comp, prob),
                    repair_steps=self.repair_step_builder.build(eq_name, comp, prob),
                    tools=["Screwdriver", "Wrench"],
                    safety_notes=self.safety_builder.build(eq_name, comp, prob),
                    tags=[target.get("name", "").lower(), eq_name.lower(), comp.lower(), prob.lower()],
                    aliases=[comp.lower()],
                    metadata={"source": "fkfe", "version": version_name, "component": comp, "problem": prob, "diagnostic_steps": self.diagnostic_builder.build(eq_name, comp, prob)},
                )
                objects.append(ro.normalize())

        json_path = self.exporter.export_jsonl(objects, filename="taxonomy.json")
        sqlite_path = self.exporter.export_sqlite(objects, dbname="taxonomy.sqlite3")
        graph_path = self.exporter.export_graph(objects, filename="taxonomy_graph.json")

        # generate symptom intelligence artifacts for these objects
        sympt_out = out_dir / "symptoms"
        sig = SymptomIntelligenceGenerator(output_dir=sympt_out)
        sig_res = sig.generate_for_objects([o.as_dict() for o in objects])

        # generate diagnostic trees for these objects
        diag_out = out_dir / "diagnostics"
        dr = DiagnosticReasoner(output_dir=diag_out)
        diag_res = dr.generate_for_objects([o.as_dict() for o in objects])

        artifacts = {"json": str(json_path), "sqlite": str(sqlite_path), "graph": str(graph_path), "symptoms_db": str(sig.db_path), "symptom_index": str(sig.index_path), "diagnostic_db": str(dr.db_path), "diagnostic_graph": str(dr.graph_path)}
        return {"objects": [o.as_dict() for o in objects], "summary": {"total_objects": len(objects), "total_symptoms": sig_res["summary"]["total_symptoms"], "total_diagnostic_trees": diag_res["summary"]["total_trees"]}, "artifacts": artifacts}
