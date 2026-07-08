from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import json
import sqlite3
import hashlib
from datetime import datetime
from generate_embeddings import EmbeddingGenerator
from app.knowledge.packs import KnowledgePackManager
from fixfinder_engine.config import settings

# Local helper for optional psycopg2
try:
    import psycopg2
except Exception:
    psycopg2 = None


class RepairObjectGenerator:
    """High-level orchestrator that generates repair objects from taxonomy
    for Version 1/2/3 and connects outputs to symptoms, diagnostics, embeddings,
    knowledge graph, postgres, and pack builder.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir or Path.cwd())
        self.pack_manager = KnowledgePackManager()
        self.output_dir = self.base_dir / "data" / "repair_objects"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_repairs_json(self, version_name: str) -> dict:
        # accept either numeric (1) or VERSION_1_HOME style
        candidates = [version_name, f"Version_{version_name}", f"VERSION_{version_name}", f"VERSION_{version_name}_HOME", f"Version_{version_name}"]
        # fallback to Version_1 folder naming
        for v in [version_name, str(version_name)]:
            p = self.base_dir / f"Version_{v}" / "05_JSON" / "repair_procedures.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        # try variant with explicit VERSION_1 naming in taxonomy
        p = self.base_dir / "Version_1" / "05_JSON" / "repair_procedures.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        raise FileNotFoundError("repair_procedures.json not found for version")

    def generate(self, version_name: str, category_name: str, per_equipment_limit: int = 200, export_postgres: bool = False, create_pack: bool = True) -> dict[str, Any]:
        repairs_json = self._load_repairs_json(version_name)

        # repairs_json is a dict mapping repair_id -> details
        objs = []
        for rid, entry in repairs_json.items():
            if category_name and entry.get("category", "").lower() != category_name.lower():
                continue
            # build standardized repair object
            rep_obj = {
                "repair_id": entry.get("id") or rid,
                "version": str(version_name),
                "category": entry.get("category"),
                "subcategory": entry.get("subcategory", ""),
                "equipment": entry.get("equipment", ""),
                "system": entry.get("system", ""),
                "component": entry.get("component", ""),
                "problem": entry.get("name", ""),
                "severity": entry.get("severity", "Medium"),
                "safety_risk": ("High" if (entry.get("safety_notes") and "WARNING" in entry.get("safety_notes")) else "Low"),
                "difficulty": entry.get("difficulty", "Moderate"),
                "estimated_time": entry.get("estimated_time", ""),
                "required_skills": ["basic"] if entry.get("difficulty","").lower() == "easy" else ["intermediate"],
                "required_tools": entry.get("tools_required") or entry.get("tools", []),
                "required_parts": entry.get("materials_required") or entry.get("materials", []),
                "symptoms": entry.get("symptoms", []),
                "user_descriptions": entry.get("description", ""),
                "observed_sounds": entry.get("observed_sounds", []),
                "observed_smells": entry.get("observed_smells", []),
                "visual_observations": entry.get("visual", []) if isinstance(entry.get("visual", []), list) else [entry.get("visual", [])],
                "environmental_conditions": entry.get("environmental_conditions", []),
                "possible_causes": entry.get("causes", []),
                "diagnostic_questions": entry.get("pre_repair_checks", []),
                "diagnostic_steps": entry.get("diagnostic_steps", []),
                "measurement_tests": entry.get("measurement_tests", []),
                "decision_tree": {},
                "repair_steps": [ {"step": s.get("step"), "title": s.get("title"), "detail": s.get("detail")} for s in entry.get("procedure_steps", []) ],
                "verification_steps": entry.get("post_repair_checks", []),
                "preventive_maintenance": entry.get("preventive_maintenance", []),
                "related_repairs": entry.get("related", []),
                "keywords": entry.get("keywords", []) or [entry.get("name", "")],
                "embedding_text": " ".join([entry.get("name", ""), entry.get("estimated_time", ""), " ".join([s.get("title","") for s in entry.get("procedure_steps", [])])]),
                "graph_links": [],
                "created_at": datetime.utcnow().isoformat(),
            }
            objs.append(rep_obj)

        # Persist JSONL
        jsonl_path = self.output_dir / f"{version_name}_{category_name}_repairs.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for o in objs:
                fh.write(json.dumps(o, ensure_ascii=False) + "\n")

        # Persist SQLite
        sqlite_path = self.output_dir / f"{version_name}_{category_name}_repairs.sqlite3"
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repairs (
                repair_id TEXT PRIMARY KEY,
                payload JSON
            )
            """
        )
        for o in objs:
            cur.execute("INSERT OR REPLACE INTO repairs (repair_id,payload) VALUES (?,?)", (o["repair_id"], json.dumps(o, ensure_ascii=False)))
        conn.commit()
        conn.close()

        # Generate diagnostics using DiagnosticReasoner if available
        try:
            from backend.knowledge_factory.diagnostic_reasoner import DiagnosticReasoner

            dr = DiagnosticReasoner(output_dir=self.output_dir / "diagnostics")
            diag_res = dr.generate_for_objects(objs)
        except Exception:
            diag_res = {"summary": {"total_trees": 0}}

        # Generate embeddings
        emb_gen = EmbeddingGenerator()
        repairs_for_emb = [{"id": o["repair_id"], "name": o["problem"], "difficulty": o["difficulty"], "estimated_time": o["estimated_time"], "steps": o["repair_steps"]} for o in objs]
        emb_payload = emb_gen.generate_embeddings_for_version(str(version_name), [], [], repairs_for_emb)
        emb_out_dir = self.base_dir / f"Version_{version_name}" / "06_Embeddings"
        emb_out_dir.mkdir(parents=True, exist_ok=True)
        emb_path = emb_out_dir / "embeddings.json"
        emb_path.write_text(json.dumps(emb_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Optional Postgres export
        pg_res = None
        if export_postgres and psycopg2 is not None:
            dsn = (settings.postgres_dsn if hasattr(settings, "postgres_dsn") else None) or __import__("os").environ.get("PG_DSN")
            if dsn:
                try:
                    conn = psycopg2.connect(dsn)
                    cur = conn.cursor()
                    cur.execute("CREATE TABLE IF NOT EXISTS repairs (repair_id TEXT PRIMARY KEY, payload JSONB)")
                    inserted = 0
                    for o in objs:
                        cur.execute("INSERT INTO repairs (repair_id,payload) VALUES (%s,%s) ON CONFLICT (repair_id) DO UPDATE SET payload = EXCLUDED.payload", (o["repair_id"], json.dumps(o, ensure_ascii=False)))
                        inserted += 1
                    conn.commit()
                    cur.close()
                    conn.close()
                    pg_res = {"status": "ok", "rows": inserted}
                except Exception as exc:
                    pg_res = {"status": "error", "error": str(exc)}
            else:
                pg_res = {"status": "skipped", "reason": "no DSN"}

        # Create knowledge pack
        pack_meta = None
        if create_pack:
            try:
                pack_meta = self.pack_manager.generate_pack(name=f"{version_name}_{category_name}", description=f"Generated pack for {category_name}", industries=[category_name], version=str(version_name))
            except Exception:
                pack_meta = None

        return {"count": len(objs), "jsonl": str(jsonl_path), "sqlite": str(sqlite_path), "diagnostics": diag_res, "embeddings": str(emb_path), "postgres": pg_res, "pack": pack_meta}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Version name (e.g. 1 or VERSION_1_HOME)")
    parser.add_argument("category", help="Category name to generate (e.g. Appliances)")
    parser.add_argument("--no-pack", dest="create_pack", action="store_false")
    parser.add_argument("--postgres", dest="export_postgres", action="store_true")
    args = parser.parse_args()
    gen = RepairObjectGenerator()
    out = gen.generate(str(args.version), args.category, export_postgres=args.export_postgres, create_pack=args.create_pack)
    print(json.dumps(out, indent=2, ensure_ascii=False))
