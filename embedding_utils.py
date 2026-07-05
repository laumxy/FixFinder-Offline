"""
embedding_utils.py
Utility functions for loading, searching, and manipulating FixFinder embeddings.

Usage:
    from embedding_utils import load_embeddings, search_embeddings, get_embedding, normalize_embedding

    embeddings = load_embeddings(version=1)
    results    = search_embeddings(query_vector, top_k=5, embeddings=embeddings)
    entry      = get_embedding("ROF-001", embeddings=embeddings)
    normed     = normalize_embedding(some_vector)
"""

import json
import math
import os
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Default paths (relative to this file's directory)
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_VERSION_PATHS = {
    1: os.path.join(_BASE_DIR, "Version_1", "06_Embeddings", "embeddings.json"),
    2: os.path.join(_BASE_DIR, "Version_2", "06_Embeddings", "embeddings.json"),
    3: os.path.join(_BASE_DIR, "Version_3", "06_Embeddings", "embeddings.json"),
}

# In-process cache: {version_int: payload_dict}
_CACHE: dict[int, dict] = {}


# ===========================================================================
# Public API
# ===========================================================================

def load_embeddings(version: int, force_reload: bool = False) -> dict:
    """
    Load the embeddings payload for a version (1, 2, or 3).

    Returns the full payload dict:
      {
        "version": "1.0",
        "dimension": 768,
        "total_embeddings": 30,
        "embeddings": [ { "entity_type", "entity_id", "text", "embedding" }, ... ]
      }

    Results are cached in-process. Pass force_reload=True to bypass the cache.
    """
    if version not in _VERSION_PATHS:
        raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")

    if not force_reload and version in _CACHE:
        return _CACHE[version]

    path = _VERSION_PATHS[version]
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Embeddings file not found: {path}\n"
            "Run generate_embeddings.py first."
        )

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    _CACHE[version] = payload
    return payload


def normalize_embedding(vector: list[float] | np.ndarray) -> list[float]:
    """
    L2-normalize a vector so it lies on the unit hypersphere.

    Parameters
    ----------
    vector : list[float] or np.ndarray

    Returns
    -------
    list[float] – normalized vector (same length as input)

    Raises
    ------
    ValueError if the input is a zero vector.
    """
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        raise ValueError("Cannot normalize a zero vector.")
    normalized = arr / norm
    return [round(float(v), 6) for v in normalized]


def get_embedding(
    entity_id: str,
    embeddings: Optional[dict] = None,
    version: Optional[int] = None,
) -> Optional[dict]:
    """
    Retrieve a single embedding entry by entity_id.

    You must supply either a pre-loaded `embeddings` payload or a `version` int.

    Parameters
    ----------
    entity_id  : str   e.g. "ROF-001", "PRB-PHN-001", "RP-CAR-001"
    embeddings : dict  (optional) pre-loaded payload from load_embeddings()
    version    : int   (optional) 1 / 2 / 3 – will call load_embeddings internally

    Returns
    -------
    dict with keys entity_type, entity_id, text, embedding — or None if not found.
    """
    if embeddings is None and version is None:
        raise ValueError("Provide either 'embeddings' or 'version'.")
    if embeddings is None:
        embeddings = load_embeddings(version)

    for entry in embeddings["embeddings"]:
        if entry["entity_id"] == entity_id:
            return entry
    return None


def search_embeddings(
    query_vector: list[float] | np.ndarray,
    top_k: int = 5,
    embeddings: Optional[dict] = None,
    version: Optional[int] = None,
    entity_type_filter: Optional[str] = None,
) -> list[dict]:
    """
    Cosine-similarity search over all stored embeddings.

    Parameters
    ----------
    query_vector       : list[float] or np.ndarray  – query embedding (768-dim)
    top_k              : int    – number of results to return (default 5)
    embeddings         : dict   – pre-loaded payload (optional)
    version            : int    – 1 / 2 / 3, used if embeddings not supplied
    entity_type_filter : str    – restrict results to "system", "symptom", or "repair"

    Returns
    -------
    list of dicts sorted by descending cosine similarity:
      [
        {
          "entity_type": "system",
          "entity_id":   "ROF-001",
          "text":        "...",
          "score":       0.9821,
          "embedding":   [...]
        },
        ...
      ]
    """
    if embeddings is None and version is None:
        raise ValueError("Provide either 'embeddings' or 'version'.")
    if embeddings is None:
        embeddings = load_embeddings(version)

    q = np.asarray(query_vector, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))
    if q_norm == 0.0:
        raise ValueError("Query vector must not be a zero vector.")
    q = q / q_norm

    results = []
    for entry in embeddings["embeddings"]:
        if entity_type_filter and entry["entity_type"] != entity_type_filter:
            continue
        v = np.asarray(entry["embedding"], dtype=np.float32)
        v_norm = float(np.linalg.norm(v))
        if v_norm == 0.0:
            continue
        score = float(np.dot(q, v / v_norm))
        results.append({
            "entity_type": entry["entity_type"],
            "entity_id":   entry["entity_id"],
            "text":        entry["text"],
            "score":       round(score, 6),
            "embedding":   entry["embedding"],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Returns a float in [-1.0, 1.0].
    """
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    denom = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return round(float(np.dot(a, b) / denom), 6)


def list_entity_ids(
    embeddings: Optional[dict] = None,
    version: Optional[int] = None,
    entity_type: Optional[str] = None,
) -> list[str]:
    """
    Return all entity IDs stored in the payload, optionally filtered by type.

    Parameters
    ----------
    embeddings  : dict  – pre-loaded payload
    version     : int   – 1 / 2 / 3
    entity_type : str   – "system" | "symptom" | "repair" (optional filter)

    Returns
    -------
    list of entity_id strings
    """
    if embeddings is None and version is None:
        raise ValueError("Provide either 'embeddings' or 'version'.")
    if embeddings is None:
        embeddings = load_embeddings(version)

    return [
        e["entity_id"]
        for e in embeddings["embeddings"]
        if entity_type is None or e["entity_type"] == entity_type
    ]


def embedding_stats(
    embeddings: Optional[dict] = None,
    version: Optional[int] = None,
) -> dict:
    """
    Return summary statistics for a loaded embeddings payload.

    Returns
    -------
    dict with keys: version, dimension, total, by_type, sample_norms
    """
    if embeddings is None and version is None:
        raise ValueError("Provide either 'embeddings' or 'version'.")
    if embeddings is None:
        embeddings = load_embeddings(version)

    by_type: dict[str, int] = {}
    norms = []
    for e in embeddings["embeddings"]:
        t = e["entity_type"]
        by_type[t] = by_type.get(t, 0) + 1
        vec = np.asarray(e["embedding"], dtype=np.float32)
        norms.append(float(np.linalg.norm(vec)))

    return {
        "version":    embeddings.get("version"),
        "dimension":  embeddings.get("dimension"),
        "total":      embeddings.get("total_embeddings", len(embeddings["embeddings"])),
        "by_type":    by_type,
        "norm_mean":  round(float(np.mean(norms)), 6) if norms else 0.0,
        "norm_std":   round(float(np.std(norms)),  6) if norms else 0.0,
    }


# ===========================================================================
# __main__ – quick smoke-test / demo
# ===========================================================================

if __name__ == "__main__":
    print("=== embedding_utils demo ===\n")

    for v in (1, 2, 3):
        try:
            payload = load_embeddings(v)
            stats   = embedding_stats(embeddings=payload)
            print(f"Version {v}: {stats}")

            # Fetch a specific entity
            ids = list_entity_ids(embeddings=payload, entity_type="system")
            if ids:
                entry = get_embedding(ids[0], embeddings=payload)
                print(f"  get_embedding({ids[0]!r}): text={entry['text'][:60]!r}...")

            # Self-similarity check: query with first embedding, expect it as top result
            first_vec = payload["embeddings"][0]["embedding"]
            top       = search_embeddings(first_vec, top_k=3, embeddings=payload)
            print(f"  top-3 search from first embedding:")
            for r in top:
                print(f"    {r['entity_id']:15s} score={r['score']:.4f}  type={r['entity_type']}")

            # Normalise check
            normed = normalize_embedding(first_vec)
            norm_val = math.sqrt(sum(x * x for x in normed))
            print(f"  normalize_embedding norm={norm_val:.6f} (should be ~1.0)\n")

        except FileNotFoundError as exc:
            print(f"  [SKIP] {exc}\n")
