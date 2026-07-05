"""
faiss_utils.py
Utility functions for loading and querying FixFinder FAISS indices.

Usage:
    from faiss_utils import load_index, search, get_nearest, batch_search

    ctx     = load_index(version=1)
    results = search(query_vector, top_k=5, ctx=ctx)
    near    = get_nearest("ROF-001", top_k=5, ctx=ctx)
    batch   = batch_search([vec1, vec2], top_k=3, ctx=ctx)
"""

import json
import os
from typing import Optional

import faiss
import numpy as np


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_VERSION_DIRS = {
    1: os.path.join(_BASE_DIR, "Version_1", "12_FAISS"),
    2: os.path.join(_BASE_DIR, "Version_2", "12_FAISS"),
    3: os.path.join(_BASE_DIR, "Version_3", "12_FAISS"),
}

# In-process cache: {version_int: context_dict}
_CACHE: dict[int, dict] = {}


# ===========================================================================
# Public API
# ===========================================================================

def load_index(version: int, force_reload: bool = False) -> dict:
    """
    Load the FAISS index and metadata for a version (1, 2, or 3).

    Returns a context dict:
    {
      "version"      : str             e.g. "1.0"
      "dimension"    : int             768
      "index_type"   : str             "IndexFlatIP"
      "total_entries": int
      "index"        : faiss.IndexFlatIP
      "id_mapping"   : dict            {"0": "ROF-001", ...}
      "rev_mapping"  : dict            {"ROF-001": 0, ...}   (reverse lookup)
      "mapping"      : dict            category range mapping
      "index_path"   : str
    }

    Results are cached in-process. Pass force_reload=True to bypass.
    """
    if version not in _VERSION_DIRS:
        raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")

    if not force_reload and version in _CACHE:
        return _CACHE[version]

    faiss_dir  = _VERSION_DIRS[version]
    index_path = os.path.join(faiss_dir, "index.faiss")
    meta_path  = os.path.join(faiss_dir, "metadata.json")

    for p in (index_path, meta_path):
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"FAISS file not found: {p}\n"
                "Run build_faiss_indices.py first."
            )

    index = faiss.read_index(index_path)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    id_mapping  = meta["id_mapping"]                         # {"0": "ROF-001", ...}
    rev_mapping = {v: int(k) for k, v in id_mapping.items()} # {"ROF-001": 0, ...}

    ctx = {
        "version":       meta["version"],
        "dimension":     meta["dimension"],
        "index_type":    meta["index_type"],
        "total_entries": meta["total_entries"],
        "index":         index,
        "id_mapping":    id_mapping,
        "rev_mapping":   rev_mapping,
        "mapping":       meta.get("mapping", {}),
        "index_path":    index_path,
    }

    _CACHE[version] = ctx
    return ctx


def search(
    query_vector: "list[float] | np.ndarray",
    top_k: int = 5,
    ctx: Optional[dict] = None,
    version: Optional[int] = None,
    entity_type_filter: Optional[str] = None,
) -> list[dict]:
    """
    Cosine-similarity search against the FAISS index.

    Parameters
    ----------
    query_vector       : 768-dim float vector
    top_k              : number of results (default 5)
    ctx                : pre-loaded context from load_index() — preferred
    version            : int 1/2/3 — used when ctx is not supplied
    entity_type_filter : "system" | "symptom" | "repair"  (optional)
                         Fetches extra candidates so filtering still returns top_k.

    Returns
    -------
    list of dicts sorted by descending score:
    [
      {"rank": 1, "entity_id": "ROF-001", "score": 0.9821, "faiss_idx": 0},
      ...
    ]
    """
    ctx = _resolve_ctx(ctx, version)
    dim = ctx["dimension"]

    q = _prepare_query(query_vector, dim)   # shape (1, dim), L2-normalised

    # fetch more candidates if we need to filter by entity type afterwards
    fetch_k = top_k * 5 if entity_type_filter else top_k
    fetch_k = min(fetch_k, ctx["total_entries"])

    scores_arr, indices_arr = ctx["index"].search(q, fetch_k)
    scores  = scores_arr[0].tolist()
    indices = indices_arr[0].tolist()

    results = []
    for faiss_idx, score in zip(indices, scores):
        if faiss_idx < 0:          # FAISS pads with -1 when fewer results exist
            continue
        entity_id = ctx["id_mapping"].get(str(faiss_idx))
        if entity_id is None:
            continue
        if entity_type_filter and not _match_type(entity_id, entity_type_filter):
            continue
        results.append({
            "rank":      len(results) + 1,
            "entity_id": entity_id,
            "score":     round(float(score), 6),
            "faiss_idx": faiss_idx,
        })
        if len(results) == top_k:
            break

    return results


def get_nearest(
    entity_id: str,
    top_k: int = 5,
    ctx: Optional[dict] = None,
    version: Optional[int] = None,
) -> list[dict]:
    """
    Find the top_k nearest neighbours to a known entity.

    Retrieves the stored vector for `entity_id` and runs a search,
    excluding the entity itself from the returned results.

    Parameters
    ----------
    entity_id : str   e.g. "ROF-001"
    top_k     : int   number of neighbours to return (not counting self)
    ctx       : dict  pre-loaded context (preferred)
    version   : int   1/2/3 — used when ctx not supplied

    Returns
    -------
    Same list-of-dicts format as search(), without the source entity.
    """
    ctx = _resolve_ctx(ctx, version)

    pos = ctx["rev_mapping"].get(entity_id)
    if pos is None:
        raise KeyError(f"entity_id {entity_id!r} not found in index.")

    # reconstruct stored vector (FAISS IndexFlatIP supports reconstruct)
    stored_vec = np.zeros(ctx["dimension"], dtype=np.float32)
    ctx["index"].reconstruct(pos, stored_vec)

    # fetch top_k+1 so we can drop self
    raw = search(stored_vec, top_k=top_k + 1, ctx=ctx)
    neighbours = [r for r in raw if r["entity_id"] != entity_id][:top_k]

    # re-rank
    for i, r in enumerate(neighbours):
        r["rank"] = i + 1

    return neighbours


def batch_search(
    query_vectors: "list[list[float]] | np.ndarray",
    top_k: int = 5,
    ctx: Optional[dict] = None,
    version: Optional[int] = None,
) -> list[list[dict]]:
    """
    Search multiple query vectors in a single FAISS call (efficient).

    Parameters
    ----------
    query_vectors : list of 768-dim vectors, or (N, 768) numpy array
    top_k         : results per query
    ctx / version : as in search()

    Returns
    -------
    list of lists — one inner list per query, each formatted like search().
    """
    ctx = _resolve_ctx(ctx, version)
    dim = ctx["dimension"]

    queries = np.array(query_vectors, dtype=np.float32)
    if queries.ndim == 1:
        queries = queries.reshape(1, -1)

    if queries.shape[1] != dim:
        raise ValueError(
            f"Expected query dimension {dim}, got {queries.shape[1]}."
        )

    faiss.normalize_L2(queries)

    fetch_k = min(top_k, ctx["total_entries"])
    scores_matrix, indices_matrix = ctx["index"].search(queries, fetch_k)

    all_results = []
    for row_scores, row_indices in zip(scores_matrix, indices_matrix):
        row = []
        for faiss_idx, score in zip(row_indices, row_scores):
            if faiss_idx < 0:
                continue
            entity_id = ctx["id_mapping"].get(str(faiss_idx))
            if entity_id is None:
                continue
            row.append({
                "rank":      len(row) + 1,
                "entity_id": entity_id,
                "score":     round(float(score), 6),
                "faiss_idx": int(faiss_idx),
            })
        all_results.append(row)

    return all_results


def index_stats(ctx: Optional[dict] = None, version: Optional[int] = None) -> dict:
    """
    Return summary information about a loaded FAISS index context.
    """
    ctx = _resolve_ctx(ctx, version)
    return {
        "version":       ctx["version"],
        "dimension":     ctx["dimension"],
        "index_type":    ctx["index_type"],
        "total_entries": ctx["total_entries"],
        "index_path":    ctx["index_path"],
        "categories":    {
            cat: {
                "range":   info["range"],
                "count":   len(info.get("ids", [])),
            }
            for cat, info in ctx["mapping"].items()
        },
    }


# ===========================================================================
# Private helpers
# ===========================================================================

def _resolve_ctx(ctx: Optional[dict], version: Optional[int]) -> dict:
    if ctx is not None:
        return ctx
    if version is not None:
        return load_index(version)
    raise ValueError("Provide either 'ctx' or 'version'.")


def _prepare_query(
    query_vector: "list[float] | np.ndarray",
    dim: int,
) -> np.ndarray:
    """Validate, reshape, and L2-normalise a single query vector."""
    q = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
    if q.shape[1] != dim:
        raise ValueError(f"Expected query dimension {dim}, got {q.shape[1]}.")
    faiss.normalize_L2(q)
    return q


# Simple entity-type classifier based on entity_id prefix conventions
_TYPE_PREFIXES = {
    "system":  {
        "ROF","FND","PLM","ELC","HVC","EXT","WIN","GRG","SMP",
        "PHN","TAB","LAP","DKT","TV","AUD","CAM","NET","GAM","WRB",
        "CAR","TRK","MCY","HVY","GEN","CMP","PMP","MOT","VAN","SUV","EV",
    },
    "symptom": {"PRB"},
    "repair":  {"RP"},
}


def _match_type(entity_id: str, entity_type: str) -> bool:
    """Return True if entity_id belongs to the requested entity_type."""
    prefix = entity_id.split("-")[0].upper()
    return prefix in _TYPE_PREFIXES.get(entity_type, set())


# ===========================================================================
# __main__ – smoke test
# ===========================================================================

if __name__ == "__main__":
    print("=== faiss_utils smoke test ===\n")

    for v in (1, 2, 3):
        try:
            ctx = load_index(v)
            stats = index_stats(ctx=ctx)
            print(f"Version {v}: {stats['total_entries']} entries, "
                  f"dim={stats['dimension']}, type={stats['index_type']}")

            # --- search: use first stored vector as query ---
            first_vec = np.zeros(ctx["dimension"], dtype=np.float32)
            ctx["index"].reconstruct(0, first_vec)
            top = search(first_vec, top_k=3, ctx=ctx)
            print(f"  search() top-3:")
            for r in top:
                print(f"    rank={r['rank']}  {r['entity_id']:<18s} score={r['score']:.4f}")

            # --- get_nearest ---
            first_id = ctx["id_mapping"]["0"]
            near = get_nearest(first_id, top_k=3, ctx=ctx)
            print(f"  get_nearest({first_id!r}) top-3:")
            for r in near:
                print(f"    rank={r['rank']}  {r['entity_id']:<18s} score={r['score']:.4f}")

            # --- batch_search: two random queries ---
            rng   = np.random.RandomState(42)
            vecs  = rng.randn(2, ctx["dimension"]).astype(np.float32)
            batch = batch_search(vecs, top_k=2, ctx=ctx)
            print(f"  batch_search(2 queries, top_k=2):")
            for qi, res in enumerate(batch):
                ids = [r["entity_id"] for r in res]
                print(f"    query {qi}: {ids}")

            print()

        except FileNotFoundError as exc:
            print(f"  [SKIP] {exc}\n")
