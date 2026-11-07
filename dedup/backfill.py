"""
dedup/backfill.py - Chronological Backfill Script for Story Clustering.

Iterates over existing articles in tech_news.db in chronological order (created_at ASC)
and assigns each to a StoryCluster and marks copies without discarding any article.
"""

import sys
import os
import argparse
import time
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal, init_database
from backend.app.models import Article, Cluster, ClusterLog
from dedup.pipeline import get_pipeline
from dedup.config import DEFAULT_CONFIG

def run_backfill(force: bool = False, limit: int = 0) -> None:
    init_database()
    db = SessionLocal()
    pipeline = get_pipeline(DEFAULT_CONFIG)

    try:
        query = db.query(Article)
        if not force:
            query = query.filter(Article.cluster_id.is_(None))
        else:
            print("[BACKFILL] --force specified. Resetting existing clusters and logs...")
            db.query(ClusterLog).delete()
            db.query(Cluster).delete()
            db.query(Article).update({
                Article.cluster_id: None,
                Article.is_copy_of: None,
                Article.embedding: None,
                Article.entities: None,
                Article.minhash: None,
                Article.text_basis: None,
                Article.clustered_at: None
            })
            db.commit()

        articles = query.order_by(Article.created_at.asc()).all()
        if limit > 0:
            articles = articles[:limit]

        total = len(articles)
        print(f"[BACKFILL] Starting chronological clustering of {total} articles...")
        start_time = time.time()

        counts = {"copy": 0, "join": 0, "borderline": 0, "new": 0}
        for i, art in enumerate(articles, 1):
            res = pipeline.process_article(art, db)
            action = res.get("action", "unknown")
            if "copy" in action:
                counts["copy"] += 1
            elif "join" in action:
                counts["join"] += 1
            else:
                counts["new"] += 1

            if i % 10 == 0 or i == total:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                print(f"[BACKFILL] Progress: {i}/{total} ({i/total*100:.1f}%) - {rate:.2f} arts/sec")

        elapsed_total = time.time() - start_time
        distinct_clusters = db.query(Cluster).count()
        print("\n" + "="*50)
        print("[BACKFILL COMPLETE]")
        print(f"Total processed:     {total}")
        print(f"New clusters formed: {counts['new']}")
        print(f"Joined clusters:     {counts['join']}")
        print(f"Copies flagged (L1): {counts['copy']}")
        print(f"Total active clusters in DB: {distinct_clusters}")
        print(f"Total time elapsed:  {elapsed_total:.2f}s (Avg {elapsed_total/max(total,1):.3f}s/article)")
        print("="*50)

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill story clusters for existing articles.")
    parser.add_argument("--force", action="store_true", help="Recluster all articles from scratch")
    parser.add_argument("--limit", type=int, default=0, help="Max articles to process")
    args = parser.parse_args()
    run_backfill(force=args.force, limit=args.limit)
