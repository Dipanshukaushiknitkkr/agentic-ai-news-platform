"""
dedup/scorer.py - Pair scoring and average-link cluster scoring for Layer 2.

Pair score formula:
    score = 0.6*cos + 0.25*ent + 0.15*time

Hard gates (return 0 immediately):
    - No shared entity (after alias + spaCy + fallback)
    - hours_apart > 72

Time decay:
    time = exp(-hours_apart / half_life)   where half_life = 24h (configurable)

Vectorised cosine:
    Embeddings are stored L2-unit-normalised so cosine_sim = dot product.
    For a new article vs a full cluster window, one matrix multiply gives all cosines.

Cluster scoring:
    AVERAGE-LINK: mean of pair scores against all existing cluster members.
    (Never single-link; it chains unrelated stories.)
"""

import math
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from dedup.config import ClusterConfig, DEFAULT_CONFIG
from dedup.entities import entity_overlap_score


@dataclass
class PairScore:
    score: float
    cos_sim: float
    ent_score: float
    time_score: float
    hours_apart: float
    hard_gated: bool = False


def compute_time_score(hours_apart: float, half_life: float = 24.0) -> float:
    """Exponential time decay. Full score at 0h, ~0.5 at half_life hours."""
    return math.exp(-hours_apart / half_life)


def score_pair(
    emb_a: np.ndarray,
    emb_b: np.ndarray,
    entities_a: List[str],
    entities_b: List[str],
    hours_apart: float,
    config: Optional[ClusterConfig] = None
) -> PairScore:
    """
    Compute the full pair score between two articles.
    Returns PairScore with score=0 if any hard gate fires.
    """
    cfg = config or DEFAULT_CONFIG

    # --- Hard gates ---
    if hours_apart > cfg.window_hours:  # 72h gate
        return PairScore(
            score=0.0, cos_sim=0.0, ent_score=0.0,
            time_score=0.0, hours_apart=hours_apart, hard_gated=True
        )

    ent = entity_overlap_score(entities_a, entities_b)
    if ent == 0.0:  # no shared entity gate
        return PairScore(
            score=0.0, cos_sim=0.0, ent_score=0.0,
            time_score=0.0, hours_apart=hours_apart, hard_gated=True
        )

    # --- Cosine similarity (dot product of unit vecs) ---
    cos = float(np.dot(emb_a, emb_b))
    cos = max(0.0, min(1.0, cos))   # clamp numerical noise

    # --- Time score ---
    time_s = compute_time_score(hours_apart, cfg.time_decay_half_life_hours)

    # --- Weighted sum ---
    score = cfg.w_cos * cos + cfg.w_ent * ent + cfg.w_time * time_s

    return PairScore(
        score=score, cos_sim=cos, ent_score=ent,
        time_score=time_s, hours_apart=hours_apart
    )


def vectorised_cosines(
    query_emb: np.ndarray,
    window_matrix: np.ndarray
) -> np.ndarray:
    """
    Compute cosine similarities between a single query embedding and all rows
    in window_matrix in one matrix multiply (O(N*D) instead of O(N) Python calls).

    Both query_emb and window_matrix rows must be L2-unit-normalised.
    Returns 1-D float32 array of shape (N,).
    """
    return window_matrix @ query_emb   # shape (N,)


def average_link_cluster_score(
    query_emb: np.ndarray,
    query_entities: List[str],
    query_time_iso: str,
    cluster_members: List[Dict[str, Any]],
    config: Optional[ClusterConfig] = None
) -> float:
    """
    AVERAGE-LINK cluster score: mean pair score between the query article and
    every existing cluster member.

    cluster_members is a list of dicts with keys:
        - "embedding": np.ndarray (1-D unit-normalised)
        - "entities": List[str]
        - "published_iso": str  (ISO-formatted datetime string)

    Returns 0.0 if the cluster has no members or all gates fire.
    """
    if not cluster_members:
        return 0.0

    cfg = config or DEFAULT_CONFIG
    query_dt = _parse_iso(query_time_iso)
    if query_dt is None:
        # Cannot compute time gate; use 0 hours (conservative)
        query_dt = 0.0

    scores = []
    for member in cluster_members:
        member_emb = member["embedding"]
        member_ents = member.get("entities", [])
        member_pub = member.get("published_iso", "")

        hours = _hours_apart(query_time_iso, member_pub)

        ps = score_pair(
            query_emb, member_emb,
            query_entities, member_ents,
            hours, cfg
        )
        if not ps.hard_gated:
            scores.append(ps.score)

    if not scores:
        return 0.0
    return float(np.mean(scores))


def _parse_iso(iso_str: str) -> Optional[float]:
    """Parse ISO datetime string to a Unix-like float (seconds). Returns None on failure."""
    if not iso_str:
        return None
    try:
        from datetime import datetime, timezone
        # Handle both 'Z' and '+00:00' suffixes
        iso_clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        return dt.timestamp()
    except Exception:
        return None


def _hours_apart(iso_a: str, iso_b: str) -> float:
    """Return absolute hours difference between two ISO datetime strings. 999 on error."""
    ts_a = _parse_iso(iso_a)
    ts_b = _parse_iso(iso_b)
    if ts_a is None or ts_b is None:
        return 999.0
    return abs(ts_a - ts_b) / 3600.0
