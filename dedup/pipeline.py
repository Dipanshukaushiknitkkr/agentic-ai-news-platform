"""
dedup/pipeline.py - Unified 3-Layer Story Clustering Pipeline Coordinator.

Orchestrates:
  - Layer 1: CopyDetector (MinHash LSH for syndicated / exact copies)
  - Layer 2: StoryClusterer (Sentence-transformer embeddings + spaCy NER + time decay)
  - Layer 3: PairVerifier (Groq LLM for borderline cases with pair_cache)
  - Database persistence: updates articles, clusters, and cluster_log in SQLite.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import numpy as np

from dedup.config import ClusterConfig, DEFAULT_CONFIG
from dedup.copy_detector import CopyDetector
from dedup.clusterer import StoryClusterer, ClusterDecision
from dedup.verifier import PairVerifier, VERDICT_SAME
from dedup.embedder import embed_single, build_text_for_embedding
from dedup.entities import extract_entities
from dedup.legacy import is_duplicate_article

logger = logging.getLogger(__name__)

class StoryClusteringPipeline:
    def __init__(self, config: Optional[ClusterConfig] = None, db_path: Optional[str] = None):
        self.config = config or DEFAULT_CONFIG
        self.copy_detector = CopyDetector(config=self.config)
        self.story_clusterer = StoryClusterer(config=self.config)
        self.pair_verifier = PairVerifier(db_path=db_path, config=self.config)
        self._warmed = False

    def warm_up(self, db_session) -> None:
        """Warm the rolling window and LSH index with recent articles from DB."""
        if self._warmed:
            return
        try:
            from backend.app.models import Article, Cluster
            # Fetch recent articles within window
            articles = (
                db_session.query(Article)
                .filter(Article.cluster_id.isnot(None))
                .order_by(Article.created_at.asc())
                .all()
            )

            db_rows = []
            for art in articles:
                # Register in Layer 1 CopyDetector if minhash exists
                if art.minhash:
                    try:
                        mh = self.copy_detector.deserialize_minhash(art.minhash)
                        pub_iso = art.created_at.isoformat() if art.created_at else ""
                        self.copy_detector.register(art.id, mh, published=pub_iso, cluster_id=art.cluster_id)
                    except Exception as e:
                        logger.debug("Failed to warm LSH for %s: %e", art.id, e)

                # Prepare for Layer 2 window
                if art.embedding:
                    db_rows.append({
                        "article_id": art.id,
                        "cluster_id": art.cluster_id,
                        "embedding": art.embedding,
                        "entities": art.entities,
                        "published": art.created_at.isoformat() if art.created_at else "",
                        "primary_article_id": art.id,
                    })

            self.story_clusterer.load_from_db(db_rows)
            self._warmed = True
            logger.info("StoryClusteringPipeline warmed with %d articles.", len(articles))
        except Exception as exc:
            logger.warning("StoryClusteringPipeline warm_up warning: %s", exc)

    def process_article(self, article: Any, db_session) -> Dict[str, Any]:
        """
        Process a single article through the 3-layer pipeline and persist results.
        `article` can be an Article model instance.
        """
        from backend.app.models import Cluster, ClusterLog

        art_id = article.id
        title = article.title or ""
        body = article.llm_summary or article.summary or ""
        text_for_minhash = f"{title}\n{body}"
        pub_iso = article.created_at.isoformat() if getattr(article, 'created_at', None) else datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------
        # LAYER 1: Copy Detection (MinHash LSH)
        # -------------------------------------------------------------
        copy_res = self.copy_detector.check_copy(
            text=text_for_minhash,
            published=pub_iso,
            current_article_id=art_id
        )

        if copy_res.is_copy:
            # Matched a syndicated copy or verbatim duplicate!
            orig_id = copy_res.original_article_id
            cluster_id = copy_res.cluster_id

            article.is_copy_of = orig_id
            article.cluster_id = cluster_id
            article.text_basis = copy_res.text_basis
            article.minhash = copy_res.minhash_bytes
            article.clustered_at = datetime.now(timezone.utc)

            # Update cluster size
            if cluster_id:
                cluster_rec = db_session.query(Cluster).filter(Cluster.id == cluster_id).first()
                if cluster_rec:
                    cluster_rec.size += 1
                    cluster_rec.updated_at = datetime.now(timezone.utc)

            # Log decision
            db_session.add(ClusterLog(
                article_id=art_id,
                decision="copy_of_" + str(orig_id),
                best_cluster_id=cluster_id,
                best_score=float(copy_res.jaccard_similarity),
                layer="L1",
                created_at=datetime.now(timezone.utc)
            ))
            db_session.commit()

            return {
                "action": "copy",
                "cluster_id": cluster_id,
                "is_copy_of": orig_id,
                "layer": "L1",
                "score": copy_res.jaccard_similarity
            }

        # -------------------------------------------------------------
        # LAYER 2: Same-Event Clustering
        # -------------------------------------------------------------
        embed_text = build_text_for_embedding(title, body)
        embedding = embed_single(embed_text, model_name=self.config.embedding_model_name)
        entities = extract_entities(title, body, config=self.config)

        decision = self.story_clusterer.assign(
            article_id=art_id,
            embedding=embedding,
            entities=entities,
            published_iso=pub_iso
        )

        target_cluster_id = decision.cluster_id
        decision_layer = "L2"
        decision_action = decision.action

        # -------------------------------------------------------------
        # LAYER 3: Borderline LLM Verification (if ambiguous)
        # -------------------------------------------------------------
        if decision.action == "borderline":
            cm = self.story_clusterer.get_cluster(decision.cluster_id)
            if cm and cm.article_ids:
                from backend.app.models import Article
                primary_id = cm.primary_article_id
                primary_art = db_session.query(Article).filter(Article.id == primary_id).first()

                if primary_art:
                    p_title = primary_art.title or ""
                    p_snip = primary_art.llm_summary or primary_art.summary or ""
                    verdict = self.pair_verifier.verify(
                        id_a=art_id,
                        title_a=title,
                        snippet_a=body,
                        id_b=primary_id,
                        title_b=p_title,
                        snippet_b=p_snip
                    )
                    decision_layer = "L3"
                    if verdict == VERDICT_SAME:
                        self.story_clusterer.confirm_join(art_id, target_cluster_id, embedding, entities, pub_iso)
                        decision_action = "join_confirmed_by_l3"
                    else:
                        new_cid = self.story_clusterer.create_new_cluster(art_id, embedding, entities, pub_iso)
                        target_cluster_id = new_cid
                        decision_action = "new_split_by_l3"

        # -------------------------------------------------------------
        # Persist to Database
        # -------------------------------------------------------------
        article.cluster_id = target_cluster_id
        article.is_copy_of = None
        article.embedding = embedding.tobytes()
        article.entities = json.dumps(entities)
        article.minhash = copy_res.minhash_bytes
        article.text_basis = copy_res.text_basis
        article.clustered_at = datetime.now(timezone.utc)

        # Update or create Cluster record
        cluster_rec = db_session.query(Cluster).filter(Cluster.id == target_cluster_id).first()
        if not cluster_rec:
            cluster_rec = Cluster(
                id=target_cluster_id,
                primary_article_id=art_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                size=1
            )
            db_session.add(cluster_rec)
        else:
            cluster_rec.size += 1
            cluster_rec.updated_at = datetime.now(timezone.utc)

        # Log decision
        db_session.add(ClusterLog(
            article_id=art_id,
            decision=decision_action,
            best_cluster_id=target_cluster_id,
            best_score=float(decision.best_score),
            layer=decision_layer,
            created_at=datetime.now(timezone.utc)
        ))
        db_session.commit()

        # Register in LSH so subsequent articles can check against this one
        if copy_res.minhash:
            self.copy_detector.register(art_id, copy_res.minhash, published=pub_iso, cluster_id=target_cluster_id)

        return {
            "action": decision_action,
            "cluster_id": target_cluster_id,
            "layer": decision_layer,
            "score": decision.best_score
        }

# Global singleton pipeline instance
_PIPELINE: Optional[StoryClusteringPipeline] = None

def get_pipeline(config: Optional[ClusterConfig] = None) -> StoryClusteringPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = StoryClusteringPipeline(config=config)
    return _PIPELINE
