"""
dedup/clusterer.py - Layer 2 Story Clusterer with rolling 72h in-memory window.

Incrementally assigns incoming articles to clusters without full re-clustering per fetch.
Decision tree per article:
    - Layer 1 hit? -> already handled by CopyDetector (skip here).
    - Best cluster score >= T_high? -> join cluster.
    - T_low <= best < T_high? -> send to Layer 3 (verifier).
    - Otherwise? -> create new cluster.

The window maintains:
    - np.ndarray embedding matrix (N x D) for vectorised cosine multiply.
    - Parallel lists of entities, published timestamps, cluster_ids, article_ids.

Clusters older than 72h are pruned from the window on each call.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

from dedup.config import ClusterConfig, DEFAULT_CONFIG
from dedup.scorer import average_link_cluster_score, _hours_apart, vectorised_cosines
from dedup.entities import entity_overlap_score


@dataclass
class ClusterMeta:
    """In-memory metadata for a single cluster in the rolling window."""
    cluster_id: int
    primary_article_id: str
    created_at: str          # ISO string
    updated_at: str          # ISO string
    size: int = 1
    # Member data for scoring
    embeddings: List[np.ndarray] = field(default_factory=list)
    entities_list: List[List[str]] = field(default_factory=list)
    published_list: List[str] = field(default_factory=list)
    article_ids: List[str] = field(default_factory=list)


@dataclass
class ClusterDecision:
    """Result of Layer 2 clustering for an article."""
    action: str              # "join" | "borderline" | "new"
    cluster_id: Optional[int]
    best_score: float
    layer: str = "L2"


class StoryClusterer:
    """
    Incremental story clusterer. Maintains an in-memory rolling window of active clusters.
    Designed to be instantiated ONCE at app startup and kept alive.
    """

    def __init__(self, config: Optional[ClusterConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._clusters: Dict[int, ClusterMeta] = {}   # cluster_id -> ClusterMeta
        self._next_cluster_id: int = 1                 # incremented in-process only

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_from_db(self, db_rows: List[Dict[str, Any]]) -> None:
        """
        Seed the in-memory window from persisted article rows on startup.
        Each row must have: article_id, cluster_id, embedding (bytes), entities (list),
        published (str), primary_article_id.
        Only loads articles within the rolling window.
        """
        import pickle
        cutoff = self._window_cutoff_iso()

        for row in db_rows:
            pub = row.get("published") or ""
            if pub and pub < cutoff:
                continue

            cid = row.get("cluster_id")
            if cid is None:
                continue

            emb_blob = row.get("embedding")
            if emb_blob is None:
                continue

            try:
                emb = np.frombuffer(emb_blob, dtype=np.float32).copy()
            except Exception:
                continue

            entities = row.get("entities") or []
            if isinstance(entities, str):
                import json
                try:
                    entities = json.loads(entities)
                except Exception:
                    entities = []

            if cid not in self._clusters:
                self._clusters[cid] = ClusterMeta(
                    cluster_id=cid,
                    primary_article_id=row.get("primary_article_id", row["article_id"]),
                    created_at=pub,
                    updated_at=pub,
                    size=0
                )
                self._next_cluster_id = max(self._next_cluster_id, cid + 1)

            cm = self._clusters[cid]
            cm.embeddings.append(emb)
            cm.entities_list.append(entities)
            cm.published_list.append(pub)
            cm.article_ids.append(row["article_id"])
            cm.size += 1

    def assign(
        self,
        article_id: str,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> ClusterDecision:
        """
        Assign an article (already past Layer 1) to a cluster.
        Returns a ClusterDecision describing what should happen.
        """
        self._prune_window()

        best_cluster_id, best_score = self._find_best_cluster(
            embedding, entities, published_iso
        )

        if best_score >= self.config.t_high:
            # Confident match — join existing cluster
            self._add_to_cluster(best_cluster_id, article_id, embedding, entities, published_iso)
            return ClusterDecision(action="join", cluster_id=best_cluster_id, best_score=best_score)

        elif best_score >= self.config.t_low:
            # Ambiguous — escalate to Layer 3; do NOT add to cluster yet
            return ClusterDecision(action="borderline", cluster_id=best_cluster_id, best_score=best_score)

        else:
            # No match — create a new cluster
            new_id = self._create_cluster(article_id, embedding, entities, published_iso)
            return ClusterDecision(action="new", cluster_id=new_id, best_score=best_score)

    def confirm_join(
        self,
        article_id: str,
        cluster_id: int,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> None:
        """Called after Layer 3 confirms SAME. Adds article to existing cluster."""
        if cluster_id in self._clusters:
            self._add_to_cluster(cluster_id, article_id, embedding, entities, published_iso)
        else:
            # Cluster has aged out of window; create a new one seeded with this article
            self._create_cluster(article_id, embedding, entities, published_iso)

    def create_new_cluster(
        self,
        article_id: str,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> int:
        """Create a new cluster explicitly (after Layer 3 says DIFFERENT)."""
        return self._create_cluster(article_id, embedding, entities, published_iso)

    def get_cluster(self, cluster_id: int) -> Optional[ClusterMeta]:
        return self._clusters.get(cluster_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_best_cluster(
        self,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> Tuple[Optional[int], float]:
        """
        Score the query article against all active clusters.
        Returns (best_cluster_id, best_average_link_score).
        Uses vectorised cosine multiply per cluster.
        """
        best_id: Optional[int] = None
        best_score: float = 0.0

        for cid, cm in self._clusters.items():
            if not cm.embeddings:
                continue

            # Vectorised cosine multiply against all member embeddings
            window_matrix = np.stack(cm.embeddings, axis=0)  # (N, D)
            cos_sims = vectorised_cosines(embedding, window_matrix)  # (N,)

            # Compute per-member pair scores (entity + time gate checked individually)
            scores_in_cluster = []
            for i, (ent_i, pub_i, cos_i) in enumerate(
                zip(cm.entities_list, cm.published_list, cos_sims)
            ):
                hours = _hours_apart(published_iso, pub_i)
                if hours > self.config.window_hours:
                    continue
                ent_overlap = entity_overlap_score(entities, ent_i)
                if ent_overlap == 0.0:
                    continue
                time_s = np.exp(-hours / self.config.time_decay_half_life_hours)
                pair_s = (
                    self.config.w_cos * float(cos_i)
                    + self.config.w_ent * ent_overlap
                    + self.config.w_time * float(time_s)
                )
                scores_in_cluster.append(pair_s)

            if not scores_in_cluster:
                continue

            avg_score = float(np.mean(scores_in_cluster))
            if avg_score > best_score:
                best_score = avg_score
                best_id = cid

        return best_id, best_score

    def _add_to_cluster(
        self,
        cluster_id: int,
        article_id: str,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> None:
        cm = self._clusters[cluster_id]
        cm.embeddings.append(embedding)
        cm.entities_list.append(entities)
        cm.published_list.append(published_iso)
        cm.article_ids.append(article_id)
        cm.size += 1
        cm.updated_at = published_iso

    def _create_cluster(
        self,
        article_id: str,
        embedding: np.ndarray,
        entities: List[str],
        published_iso: str,
    ) -> int:
        cid = self._next_cluster_id
        self._next_cluster_id += 1
        self._clusters[cid] = ClusterMeta(
            cluster_id=cid,
            primary_article_id=article_id,
            created_at=published_iso,
            updated_at=published_iso,
            size=1,
            embeddings=[embedding],
            entities_list=[entities],
            published_list=[published_iso],
            article_ids=[article_id],
        )
        return cid

    def _prune_window(self) -> None:
        """Remove clusters whose last updated_at is beyond window_hours."""
        cutoff = self._window_cutoff_iso()
        to_remove = [
            cid for cid, cm in self._clusters.items()
            if cm.updated_at and cm.updated_at < cutoff
        ]
        for cid in to_remove:
            del self._clusters[cid]

    def _window_cutoff_iso(self) -> str:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=self.config.window_hours)
        return cutoff_dt.isoformat()

    @property
    def active_cluster_count(self) -> int:
        return len(self._clusters)
