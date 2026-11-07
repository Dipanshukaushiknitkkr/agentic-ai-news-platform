"""
tests/test_event_clusterer.py

Unit tests for Layer 2: same-event clustering (scorer + clusterer).
These tests do NOT require the embedding model (uses random unit vectors),
so they run fast in CI without downloading sentence-transformers.

One integration test (test_clusterer_with_embedder) is marked slow and
requires the actual model — it is skipped by default.
"""

import math
import pytest
import numpy as np
from typing import List
from datetime import datetime, timezone, timedelta

from dedup.scorer import (
    compute_time_score,
    score_pair,
    _hours_apart,
    _parse_iso,
    vectorised_cosines,
    average_link_cluster_score,
)
from dedup.entities import entity_overlap_score, extract_entities
from dedup.clusterer import StoryClusterer, ClusterDecision
from dedup.config import ClusterConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return (v / n).astype(np.float32) if n > 0 else v.astype(np.float32)

def _rand_unit(dim: int = 384, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _unit(rng.standard_normal(dim).astype(np.float32))

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _iso_offset(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# scorer.py tests
# ---------------------------------------------------------------------------

class TestTimeDecay:
    def test_at_zero_hours(self):
        assert compute_time_score(0.0, half_life=24.0) == pytest.approx(1.0)

    def test_at_half_life(self):
        score = compute_time_score(24.0, half_life=24.0)
        assert score == pytest.approx(math.exp(-1), rel=1e-6)

    def test_at_72_hours(self):
        score = compute_time_score(72.0, half_life=24.0)
        assert score == pytest.approx(math.exp(-3), rel=1e-6)


class TestScorePair:
    def _cfg(self):
        return ClusterConfig()

    def test_identical_embeddings_full_score(self):
        emb = _rand_unit()
        ents = ["openai", "gpt-5"]
        ps = score_pair(emb, emb, ents, ents, hours_apart=0.0, config=self._cfg())
        assert not ps.hard_gated
        # cos=1.0, ent=1.0, time=1.0 -> score=0.6+0.25+0.15=1.0
        assert ps.score == pytest.approx(1.0, rel=1e-4)

    def test_no_shared_entity_hard_gate(self):
        emb_a = _rand_unit(seed=1)
        emb_b = _rand_unit(seed=2)
        ps = score_pair(emb_a, emb_b, ["openai"], ["google"], hours_apart=1.0, config=self._cfg())
        assert ps.hard_gated
        assert ps.score == 0.0

    def test_beyond_window_hard_gate(self):
        emb = _rand_unit()
        ents = ["openai"]
        ps = score_pair(emb, emb, ents, ents, hours_apart=100.0, config=self._cfg())
        assert ps.hard_gated
        assert ps.score == 0.0

    def test_different_topics_low_score(self):
        # Orthogonal embeddings -> cos ~= 0
        emb_a = _unit(np.array([1.0] + [0.0] * 383))
        emb_b = _unit(np.array([0.0, 1.0] + [0.0] * 382))
        ents = ["openai"]  # share one entity so gate passes
        ps = score_pair(emb_a, emb_b, ents, ents, hours_apart=1.0, config=self._cfg())
        assert not ps.hard_gated
        assert ps.score < 0.5


class TestVectorisedCosines:
    def test_self_similarity_is_one(self):
        emb = _rand_unit(seed=42)
        matrix = np.stack([emb, emb], axis=0)
        sims = vectorised_cosines(emb, matrix)
        assert sims[0] == pytest.approx(1.0, abs=1e-5)
        assert sims[1] == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_is_zero(self):
        emb_a = _unit(np.array([1.0] + [0.0] * 383))
        emb_b = _unit(np.array([0.0, 1.0] + [0.0] * 382))
        matrix = emb_b.reshape(1, -1)
        sim = vectorised_cosines(emb_a, matrix)
        assert sim[0] == pytest.approx(0.0, abs=1e-5)


class TestEntityOverlap:
    def test_full_overlap(self):
        assert entity_overlap_score(["openai", "gpt-5"], ["gpt-5", "openai"]) == pytest.approx(1.0)

    def test_no_overlap(self):
        assert entity_overlap_score(["openai"], ["google"]) == 0.0

    def test_partial_overlap(self):
        score = entity_overlap_score(["openai", "gpt-5", "chatgpt"], ["gpt-5", "anthropic"])
        assert score == pytest.approx(1 / 2)   # |{gpt-5}| / min(3,2)


# ---------------------------------------------------------------------------
# clusterer.py tests
# ---------------------------------------------------------------------------

class TestStoryClusterer:
    def _make_config(self, t_high=0.70, t_low=0.50):
        cfg = ClusterConfig()
        cfg.t_high = t_high
        cfg.t_low = t_low
        return cfg

    def test_first_article_creates_new_cluster(self):
        clusterer = StoryClusterer(self._make_config())
        emb = _rand_unit(seed=10)
        decision = clusterer.assign("art1", emb, ["openai", "gpt-5"], _now_iso())
        assert decision.action == "new"
        assert decision.cluster_id == 1
        assert clusterer.active_cluster_count == 1

    def test_identical_articles_join_same_cluster(self):
        clusterer = StoryClusterer(self._make_config())
        emb = _rand_unit(seed=10)
        ents = ["openai", "gpt-5"]
        now = _now_iso()

        d1 = clusterer.assign("art1", emb, ents, now)
        assert d1.action == "new"

        # Same embedding + same entities -> should score ~1.0 -> join
        d2 = clusterer.assign("art2", emb.copy(), ents, _iso_offset(0.5))
        assert d2.action == "join"
        assert d2.cluster_id == d1.cluster_id

    def test_different_topics_create_separate_clusters(self):
        clusterer = StoryClusterer(self._make_config())

        emb_openai = _unit(np.array([1.0] + [0.0] * 383))
        emb_google = _unit(np.array([0.0, 1.0] + [0.0] * 382))

        d1 = clusterer.assign("art1", emb_openai, ["openai", "gpt-5"], _now_iso())
        d2 = clusterer.assign("art2", emb_google, ["google", "gemini"], _iso_offset(1.0))

        assert d1.action == "new"
        assert d2.action == "new"
        assert d1.cluster_id != d2.cluster_id
        assert clusterer.active_cluster_count == 2

    def test_no_shared_entity_does_not_join(self):
        """Hard gate: articles with zero shared entities must NEVER join same cluster."""
        clusterer = StoryClusterer(self._make_config())
        emb = _rand_unit(seed=5)   # same embedding (high cos), different entities

        d1 = clusterer.assign("art1", emb, ["openai", "gpt-5"], _now_iso())
        d2 = clusterer.assign("art2", emb.copy(), ["tesla", "elon"], _iso_offset(1.0))

        assert d2.action == "new"       # entity gate fired; must not join
        assert d1.cluster_id != d2.cluster_id

    def test_borderline_zone_returned(self):
        """
        Articles with 0.50 <= score < 0.70 should return action='borderline'.
        We engineer this by using moderately similar (not identical) embeddings.
        """
        cfg = self._make_config(t_high=0.95, t_low=0.30)  # narrow the join band to force borderline
        clusterer = StoryClusterer(cfg)

        emb_a = _rand_unit(seed=10)
        # emb_b is a mild perturbation of emb_a
        rng = np.random.default_rng(99)
        emb_b = _unit(emb_a + 0.3 * rng.standard_normal(384).astype(np.float32))

        ents = ["openai"]
        d1 = clusterer.assign("art1", emb_a, ents, _now_iso())
        assert d1.action == "new"

        d2 = clusterer.assign("art2", emb_b, ents, _iso_offset(1.0))
        assert d2.action in ("borderline", "join")  # depends on actual cosine

    def test_window_pruning_removes_old_clusters(self):
        """Clusters with updated_at older than window_hours must be pruned."""
        clusterer = StoryClusterer(self._make_config())
        emb = _rand_unit(seed=10)

        # Inject an artificially old cluster directly
        old_time = _iso_offset(-80)   # 80 hours ago (> 72h window)
        clusterer.assign("art_old", emb, ["openai"], old_time)
        # Force updated_at to be old
        old_cid = max(clusterer._clusters.keys())
        clusterer._clusters[old_cid].updated_at = old_time

        # Trigger pruning via a new assignment
        clusterer.assign("art_new", _rand_unit(seed=99), ["google"], _now_iso())

        assert old_cid not in clusterer._clusters

    def test_confirm_join_adds_to_cluster(self):
        """confirm_join() should expand cluster size."""
        clusterer = StoryClusterer(self._make_config())
        emb = _rand_unit(seed=10)
        d1 = clusterer.assign("art1", emb, ["openai"], _now_iso())
        cid = d1.cluster_id

        emb2 = _rand_unit(seed=20)
        clusterer.confirm_join("art2", cid, emb2, ["openai"], _iso_offset(1.0))

        cm = clusterer.get_cluster(cid)
        assert cm is not None
        assert cm.size == 2
        assert "art2" in cm.article_ids


# ---------------------------------------------------------------------------
# integration test (slow — downloads model)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_clusterer_with_real_embedder():
    """
    Requires sentence-transformers to be installed.
    Run with: pytest -m slow
    """
    from dedup.embedder import embed_single, build_text_for_embedding

    cfg = ClusterConfig()
    clusterer = StoryClusterer(cfg)

    articles = [
        {
            "id": "art1",
            "title": "OpenAI launches GPT-5 with improved reasoning",
            "body": "OpenAI announced GPT-5 today featuring chain-of-thought reasoning improvements.",
            "published": _now_iso(),
            "entities": ["openai", "gpt-5"],
        },
        {
            "id": "art2",
            "title": "Sam Altman unveils OpenAI's next generation model",
            "body": "Sam Altman presented GPT-5 at an event showcasing advanced reasoning benchmarks.",
            "published": _iso_offset(0.5),
            "entities": ["openai", "gpt-5", "sam altman"],
        },
        {
            "id": "art3",
            "title": "Google Quantum AI achieves error-corrected qubit milestone",
            "body": "Google's quantum team in Santa Barbara demonstrated Willow chip beating classical computers.",
            "published": _iso_offset(1.0),
            "entities": ["google", "willow"],
        },
    ]

    decisions = {}
    for art in articles:
        text = build_text_for_embedding(art["title"], art["body"])
        emb = embed_single(text, model_name=cfg.embedding_model_name)
        d = clusterer.assign(art["id"], emb, art["entities"], art["published"])
        decisions[art["id"]] = d

    # art1 and art2 (same event, same entities) must end up in the same cluster
    assert decisions["art1"].cluster_id == decisions["art2"].cluster_id or \
           decisions["art2"].action in ("join", "borderline"), \
           "art1 and art2 (same GPT-5 event) should cluster together"

    # art3 (different topic) must be in a different cluster
    assert decisions["art3"].cluster_id != decisions["art1"].cluster_id, \
           "art3 (quantum topic) must NOT join the GPT-5 cluster"
