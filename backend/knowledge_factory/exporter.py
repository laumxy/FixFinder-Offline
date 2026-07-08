from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .schema import RepairObject
from .graph_builder import GraphBuilder
import os
try:
    import psycopg2
except Exception:
    psycopg2 = None


class Exporter:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir or Path("data/knowledge_build"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_jsonl(self, items: List[RepairObject], filename: str = "taxonomy.json") -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump({"items": [item.as_dict() for item in items]}, handle, indent=2)
        return path

    def export_sqlite(self, items: List[RepairObject], dbname: str = "taxonomy.sqlite3") -> Path:
        path = self.output_dir / dbname
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS taxonomy_objects (
                id TEXT PRIMARY KEY,
                title TEXT,
                category TEXT,
                equipment TEXT,
                component TEXT,
                problem TEXT,
                symptoms TEXT,
                diagnostic_steps TEXT,
                repair_steps TEXT,
                tools TEXT,
                parts TEXT,
                safety TEXT,
                keywords TEXT
            )
            """
        )
        for item in items:
            cur.execute(
                "INSERT OR REPLACE INTO taxonomy_objects (id,title,category,equipment,component,problem,symptoms,diagnostic_steps,repair_steps,tools,parts,safety,keywords) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    item.title,
                    item.category,
                    item.equipment,
                    item.metadata.get("component") or "",
                    item.metadata.get("problem") or "",
                    json.dumps(item.symptoms, ensure_ascii=False),
                    json.dumps(item.metadata.get("diagnostic_steps") or [], ensure_ascii=False),
                    json.dumps(item.repair_steps, ensure_ascii=False),
                    json.dumps(item.tools, ensure_ascii=False),
                    json.dumps(item.metadata.get("parts") or [], ensure_ascii=False),
                    json.dumps(item.safety_notes, ensure_ascii=False),
                    json.dumps(item.tags, ensure_ascii=False),
                ),
            )
        conn.commit()
        conn.close()
        return path

    def export_graph(self, items: List[RepairObject], filename: str = "taxonomy_graph.json") -> Path:
        gb = GraphBuilder()
        graph = gb.build_graph(items)
        path = self.output_dir / filename
        path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return path

    def export_postgres(self, items: List[RepairObject], table_name: str = "taxonomy_objects") -> dict:
        """Export items to a PostgreSQL table if `DATABASE_URL` (or PG_DSN) is set and psycopg2 is available.

        Returns a dict with status and row_count or error.
        """
        dsn = os.environ.get("PG_DSN") or os.environ.get("DATABASE_URL")
        if not dsn:
            return {"status": "skipped", "reason": "no DSN provided"}
        if psycopg2 is None:
            return {"status": "skipped", "reason": "psycopg2 not installed"}

        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} (id TEXT PRIMARY KEY, payload JSONB);")
        inserted = 0
        for item in items:
            cur.execute(
                f"INSERT INTO {table_name} (id,payload) VALUES (%s,%s) ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload",
                (item.id, json.dumps(item.as_dict(), ensure_ascii=False)),
            )
            inserted += 1
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "ok", "rows": inserted}
