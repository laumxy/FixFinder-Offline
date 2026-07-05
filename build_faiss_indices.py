"""
build_faiss_indices.py
Builds FAISS IndexFlatIP (cosine similarity) indices for all 3 FixFinder versions.

Reads:
  Version_X/06_Embeddings/embeddings.json

Writes:
  Version_X/12_FAISS/index.faiss
  Version_X/12_FAISS/metadata.json
"""

import faiss
import json
import os
import numpy as np


# ===========================================================================
# FAISSIndexBuilder
# ===========================================================================

class FAISSIndexBuilder:
    """Builds and saves FAISS IndexFlatIP indices from embedding payloads."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    # ------------------------------------------------------------------
    # build_index
    # ------------------------------------------------------------------
    def build_index(self, embeddings_data: dict, version: str):
        """
        Build a FAISS IndexFlatIP from an embeddings payload.

        Parameters
        ----------
        embeddings_data : dict  Full payload loaded from embeddings.json.
        version         : str   Version label used for logging (e.g. "1.0").

        Returns
        -------
        tuple (index, id_mapping, category_mapping)
          index            – faiss.IndexFlatIP, vectors already added
          id_mapping       – {str(int_pos): entity_id}
          category_mapping – {category_name: {"range": [start, end]}}
        """
        entries = embeddings_data["embeddings"]
        n       = len(entries)

        # --- build float32 matrix ---
        matrix = np.zeros((n, self.dimension), dtype=np.float32)
        for i, entry in enumerate(entries):
            vec = np.asarray(entry["embedding"], dtype=np.float32)
            matrix[i] = vec

        # --- L2-normalise so inner product == cosine similarity ---
        faiss.normalize_L2(matrix)

        # --- create index and add vectors ---
        index = faiss.IndexFlatIP(self.dimension)
        index.add(matrix)

        # --- id_mapping: integer position → entity_id ---
        id_mapping = {str(i): entries[i]["entity_id"] for i in range(n)}

        # --- category mapping: group consecutive entries by entity_type ---
        category_mapping = self._build_category_mapping(entries)

        print(f"  Built IndexFlatIP  v{version}: {index.ntotal} vectors, dim={self.dimension}")
        return index, id_mapping, category_mapping

    # ------------------------------------------------------------------
    # save_index
    # ------------------------------------------------------------------
    def save_index(
        self,
        version: str,
        out_dir: str,
        index: faiss.IndexFlatIP,
        id_mapping: dict,
        category_mapping: dict,
        embeddings_data: dict,
    ) -> None:
        """
        Persist the FAISS index file and metadata.json to `out_dir`.

        Parameters
        ----------
        version          : str   e.g. "1.0"
        out_dir          : str   target directory (created if absent)
        index            : faiss.IndexFlatIP
        id_mapping       : dict  {str(pos): entity_id}
        category_mapping : dict  {category: {"range": [start, end]}}
        embeddings_data  : dict  original payload (for metadata fields)
        """
        os.makedirs(out_dir, exist_ok=True)

        # --- save .faiss binary ---
        index_path = os.path.join(out_dir, "index.faiss")
        faiss.write_index(index, index_path)
        print(f"  [OK] {index_path}")

        # --- build metadata ---
        metadata = {
            "version":       version,
            "dimension":     self.dimension,
            "index_type":    "IndexFlatIP",
            "total_entries": index.ntotal,
            "index_path":    index_path,
            "id_mapping":    id_mapping,
            "mapping":       category_mapping,
        }

        meta_path = os.path.join(out_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"  [OK] {meta_path}")

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_category_mapping(entries: list) -> dict:
        """
        Build range-based category mapping.

        Each entry is assigned a category label derived from its entity_id
        prefix.  The mapping records the exact list of FAISS integer positions
        for each category plus a [min, max+1] range for quick range checks.

        Returns
        -------
        dict  {label: {"range": [first_pos, last_pos+1], "ids": [entity_id, ...]}}
        """
        _PREFIX_MAP = {
            # Home Maintenance
            "ROF": "Roofing",         "FND": "Foundation",     "PLM": "Plumbing",
            "ELC": "Electrical",      "HVC": "HVAC",           "EXT": "Exterior",
            "WIN": "Windows",         "GRG": "Garage",         "SMP": "Basement",
            "APL": "Appliances",
            # Electronics
            "PHN": "Phones",          "TAB": "Tablets",        "LAP": "Laptops",
            "DKT": "Desktops",        "TV":  "TVs",            "AUD": "Audio",
            "CAM": "Cameras",         "NET": "Networking",     "GAM": "Gaming",
            "WRB": "Wearables",
            # Industrial / Automotive
            "CAR": "Cars",            "TRK": "Trucks",         "MCY": "Motorcycles",
            "HVY": "Heavy Equipment", "HEQ": "Heavy Equipment","GEN": "Generators",
            "CMP": "Compressors",     "PMP": "Pumps",          "MOT": "Motors",
            "VAN": "Commercial Vans", "SUV": "SUVs",           "EV":  "Electric Vehicles",
            "SOL": "Solar Systems",
        }

        # Map entity_type to readable fallback labels
        _TYPE_LABELS = {
            "system":  "Systems",
            "symptom": "Symptoms",
            "repair":  "Repairs",
        }

        def _category_label(entity_id: str, entity_type: str) -> str:
            # Strip leading functional prefixes (PRB-, RP-, PT-)
            parts = entity_id.split("-")
            for part in parts:
                if part in _PREFIX_MAP:
                    return _PREFIX_MAP[part]
            # Fallback: use entity_type label
            return _TYPE_LABELS.get(entity_type, entity_type.capitalize())

        # Collect positions per category (preserves insertion order via dict)
        cat_positions: dict[str, list[int]] = {}
        cat_ids: dict[str, list[str]] = {}

        for i, entry in enumerate(entries):
            label = _category_label(entry["entity_id"], entry["entity_type"])
            cat_positions.setdefault(label, []).append(i)
            cat_ids.setdefault(label, []).append(entry["entity_id"])

        # Build final mapping with accurate [min_pos, max_pos+1] range
        mapping: dict = {}
        for label, positions in cat_positions.items():
            mapping[label] = {
                "range": [min(positions), max(positions) + 1],
                "ids":   cat_ids[label],
            }

        return mapping


# ===========================================================================
# Per-version config
# ===========================================================================

VERSIONS = [
    {
        "label":        "Version 1 – Home Maintenance",
        "version_str":  "1.0",
        "embeddings_path": "Version_1/06_Embeddings/embeddings.json",
        "out_dir":      "Version_1/12_FAISS",
    },
    {
        "label":        "Version 2 – Electronics",
        "version_str":  "2.0",
        "embeddings_path": "Version_2/06_Embeddings/embeddings.json",
        "out_dir":      "Version_2/12_FAISS",
    },
    {
        "label":        "Version 3 – Industrial / Automotive",
        "version_str":  "3.0",
        "embeddings_path": "Version_3/06_Embeddings/embeddings.json",
        "out_dir":      "Version_3/12_FAISS",
    },
]


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    builder = FAISSIndexBuilder(dimension=768)

    for cfg in VERSIONS:
        print(f"\n{'='*60}")
        print(f"  {cfg['label']}")
        print(f"{'='*60}")

        # load embeddings
        emb_path = cfg["embeddings_path"]
        if not os.path.exists(emb_path):
            print(f"  [SKIP] embeddings file not found: {emb_path}")
            continue

        with open(emb_path, "r", encoding="utf-8") as f:
            embeddings_data = json.load(f)

        # build
        index, id_mapping, cat_mapping = builder.build_index(
            embeddings_data, cfg["version_str"]
        )

        # save
        builder.save_index(
            version         = cfg["version_str"],
            out_dir         = cfg["out_dir"],
            index           = index,
            id_mapping      = id_mapping,
            category_mapping= cat_mapping,
            embeddings_data = embeddings_data,
        )

        # summary
        print(f"  Categories / ranges:")
        for cat, info in cat_mapping.items():
            print(f"    {cat:<22s} range={info['range']}  ({len(info['ids'])} entries)")

    print("\nAll FAISS indices built successfully.")


if __name__ == "__main__":
    main()
