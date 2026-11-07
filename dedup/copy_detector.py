"""
dedup/copy_detector.py - Layer 1: Near-Verbatim / Syndicated Copy Detection with MinHash LSH.

Identifies near-identical or syndicated copies of articles (e.g. shared wire stories, press releases).
Articles flagged as copies:
- Have is_copy_of set to the earliest-published matching article's ID.
- Are placed in the same cluster as the original.
- Skip Layers 2 and 3 downstream.
- Count as ONE origin downstream (for independent verification in Contradiction Radar).
"""

import pickle
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datasketch import MinHash, MinHashLSH

from dedup.config import ClusterConfig, DEFAULT_CONFIG
from dedup.normalize import build_minhash_from_text, tokenize

@dataclass
class CopyMatchResult:
    is_copy: bool
    original_article_id: Optional[str] = None
    cluster_id: Optional[int] = None
    jaccard_similarity: float = 0.0
    text_basis: str = "snippet"  # "full" | "snippet"
    minhash: Optional[MinHash] = None
    minhash_bytes: Optional[bytes] = None

class CopyDetector:
    """
    In-memory Layer 1 copy detector powered by datasketch MinHash LSH.
    """
    def __init__(self, config: Optional[ClusterConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.num_perm = self.config.minhash_num_perm
        self.threshold = self.config.lsh_threshold
        self.lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        # Store metadata for registered articles: id -> {published, cluster_id, minhash}
        self.registry: Dict[str, Dict[str, Any]] = {}

    def serialize_minhash(self, minhash: MinHash) -> bytes:
        """Serialize a MinHash object to bytes for SQLite BLOB storage."""
        return pickle.dumps(minhash)

    def deserialize_minhash(self, data: bytes) -> MinHash:
        """Deserialize bytes from SQLite BLOB to a MinHash object."""
        return pickle.loads(data)

    def register(
        self,
        article_id: str,
        minhash: MinHash,
        published: str = "",
        cluster_id: Optional[int] = None
    ) -> None:
        """Register an article's MinHash in the LSH index and metadata registry."""
        if article_id in self.registry:
            return  # Already registered

        self.registry[article_id] = {
            "published": published or "",
            "cluster_id": cluster_id,
            "minhash": minhash,
        }
        self.lsh.insert(article_id, minhash)

    def check_copy(
        self,
        text: str,
        published: str = "",
        current_article_id: Optional[str] = None
    ) -> CopyMatchResult:
        """
        Check if text is a near-duplicate/copy of an existing article in the LSH index.
        
        Returns:
            CopyMatchResult with is_copy=True and original_article_id if match found >= threshold,
            otherwise is_copy=False.
        """
        minhash, text_basis = build_minhash_from_text(
            text=text,
            num_perm=self.num_perm,
            k_full=self.config.shingle_k_full,
            k_snippet=self.config.shingle_k_snippet,
            snippet_threshold=self.config.snippet_threshold_words
        )
        minhash_bytes = self.serialize_minhash(minhash)

        # Query candidates from LSH
        candidates: List[str] = self.lsh.query(minhash)

        # Filter out current article if re-evaluating
        if current_article_id:
            candidates = [c for c in candidates if c != current_article_id]

        if not candidates:
            return CopyMatchResult(
                is_copy=False,
                text_basis=text_basis,
                minhash=minhash,
                minhash_bytes=minhash_bytes
            )

        # Compute actual MinHash Jaccard similarity for candidates
        matches = []
        for cand_id in candidates:
            cand_meta = self.registry.get(cand_id)
            if not cand_meta:
                continue
            cand_minhash = cand_meta["minhash"]
            sim = minhash.jaccard(cand_minhash)
            if sim >= self.threshold:
                matches.append((cand_id, cand_meta["published"], cand_meta["cluster_id"], sim))

        if not matches:
            return CopyMatchResult(
                is_copy=False,
                text_basis=text_basis,
                minhash=minhash,
                minhash_bytes=minhash_bytes
            )

        # Pick earliest published match (if tied or missing date, order by id)
        # Note: published strings formatted ISO or RFC or empty; empty sorts last
        def sort_key(item):
            pub = item[1]
            return (pub == "", pub, item[0])

        matches.sort(key=sort_key)
        best_cand_id, _, best_cluster_id, best_sim = matches[0]

        return CopyMatchResult(
            is_copy=True,
            original_article_id=best_cand_id,
            cluster_id=best_cluster_id,
            jaccard_similarity=best_sim,
            text_basis=text_basis,
            minhash=minhash,
            minhash_bytes=minhash_bytes
        )
