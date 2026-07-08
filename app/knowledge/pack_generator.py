from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from app.database.db import fetch_all_problem_records
from fixfinder_engine.config import settings


class PackGenerator:
    """Generate offline knowledge packs containing records, diagnostics, embeddings, and metadata.

    Pack format: gzip-compressed JSON with keys:
      - schema_version
      - pack_id
      - name
      - description
      - version
      - created_at
      - record_count
      - records
      - diagnostic_trees
      - embeddings
      - images
      - conversation_templates

    Provides checksum and writes PWA manifest alongside packs.
    """

    def __init__(self, out_dir: Path | None = None) -> None:
        self.out_dir = Path(out_dir or settings.packs_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def _collect_records(self, industries: list[str] | None = None, incremental_since: str | None = None) -> list[dict[str, Any]]:
        records = fetch_all_problem_records(settings.database_path)
        if industries:
            records = [r for r in records if r.get("category") in industries]
        if incremental_since:
            records = [r for r in records if r.get("knowledge_version") != incremental_since]
        return records

    def _collect_diagnostic_trees(self) -> dict[str, Any]:
        # Try reading Version_* diagnostic JSONs if present
        trees = {}
        for v in (1, 2, 3):
            p = Path(settings.faiss_index_path).parent.parent / f"Version_{v}" / "05_JSON" / "diagnostic_trees.json"
            if p.exists():
                try:
                    trees[f"v{v}"] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    trees[f"v{v}"] = {}
        return trees

    def _collect_embeddings(self) -> dict[str, Any]:
        data = {}
        meta_path = settings.faiss_metadata_path
        if meta_path.exists():
            try:
                data["faiss_metadata"] = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                data["faiss_metadata"] = []
        # Also try Version_* embeddings.json
        for v in (1, 2, 3):
            p = Path(settings.faiss_index_path).parent.parent / f"Version_{v}" / "06_Embeddings" / "embeddings.json"
            if p.exists():
                try:
                    data[f"v{v}_embeddings"] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    data[f"v{v}_embeddings"] = []
        return data

    def _collect_images(self) -> dict[str, Any]:
        # Try Frontend metadata
        images_meta = {}
        p = Path(settings.faiss_index_path).parent.parent / "Frontend" / "metadata.json"
        if p.exists():
            try:
                images_meta = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                images_meta = {}
        return images_meta

    def _collect_conversation_templates(self) -> list[dict[str, Any]]:
        # Try to find conversation templates; fallback empty
        templates = []
        tpath = Path(settings.faiss_index_path).parent.parent / "app" / "conversation" / "templates.json"
        if tpath.exists():
            try:
                templates = json.loads(tpath.read_text(encoding="utf-8"))
            except Exception:
                templates = []
        return templates

    def generate_pack(
        self,
        name: str,
        description: str = "",
        industries: list[str] | None = None,
        version: str = "1.0",
        incremental_since: str | None = None,
    ) -> dict[str, Any]:
        records = self._collect_records(industries=industries, incremental_since=incremental_since)
        diag = self._collect_diagnostic_trees()
        emb = self._collect_embeddings()
        images = self._collect_images()
        templates = self._collect_conversation_templates()

        pack_id = name.lower().replace(" ", "-")[:32]
        now = datetime.utcnow().isoformat() if False else None
        payload = {
            "schema_version": settings.pack_schema_version,
            "pack_id": pack_id,
            "name": name,
            "description": description,
            "version": version,
            "created_at": __import__('datetime').datetime.utcnow().isoformat(),
            "record_count": len(records),
            "records": records,
            "diagnostic_trees": diag,
            "embeddings": emb,
            "images": images,
            "conversation_templates": templates,
            "incremental_since": incremental_since,
        }

        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        compressed = gzip.compress(raw)

        fname = f"{pack_id}_{name.lower().replace(' ','_')}.pack.gz"
        out_path = self.out_dir / fname
        out_path.write_bytes(compressed)

        checksum = hashlib.sha256(compressed).hexdigest()
        meta = {
            "pack_id": pack_id,
            "file": str(out_path),
            "checksum": checksum,
            "size_bytes": out_path.stat().st_size,
            "version": version,
            "record_count": len(records),
        }

        # Update PWA manifest
        self._update_manifest(meta)

        return meta

    def _update_manifest(self, meta: dict[str, Any]) -> None:
        manp = self.out_dir / "packs_manifest.json"
        try:
            manifest = json.loads(manp.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"packs": []}
        # replace if same pack_id
        packs = [p for p in manifest.get("packs", []) if p.get("pack_id") != meta.get("pack_id")]
        packs.append(meta)
        manifest["packs"] = packs
        manp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


__all__ = ["PackGenerator"]
