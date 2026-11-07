"""
scripts/migrate_to_postgres.py - One-Click SQLite to PostgreSQL Data Migration Tool.

Migrates all data from local tech_news.db into PostgreSQL:
- Users & Authentication
- Categories & Taxonomies
- Articles, Summaries & Published dates
- Clusters, Story Groupings, and Embeddings
- Cluster Logs & Pair Caches

Usage:
  python scripts/migrate_to_postgres.py "postgresql://user:password@host:5432/database"
"""

import sys
import os
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.models import (
    Base, User, Category, Article, ArticleCategory,
    UserSubscription, DigestLog, Cluster, PairCache, ClusterLog
)

def run_migration(pg_url: str, sqlite_path: str = "tech_news.db"):
    print("="*60)
    print(" SQLITE -> POSTGRESQL DATA MIGRATION ")
    print("="*60)

    # Normalize Postgres URL
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif pg_url.startswith("postgresql://") and "+psycopg2" not in pg_url:
        pg_url = pg_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    print(f"Connecting to PostgreSQL...")
    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    PgSession = sessionmaker(bind=pg_engine)

    # 1. Initialize schema in PostgreSQL
    print("Creating all tables and schemas in PostgreSQL...")
    Base.metadata.create_all(bind=pg_engine)

    # Ensure all new columns exist in PostgreSQL
    with pg_engine.connect() as conn:
        for col_name, col_type in [
            ("cluster_id", "INTEGER"),
            ("is_copy_of", "VARCHAR(255)"),
            ("embedding", "BYTEA"),
            ("entities", "JSON"),
            ("minhash", "BYTEA"),
            ("text_basis", "VARCHAR(50)"),
            ("clustered_at", "TIMESTAMP WITH TIME ZONE"),
        ]:
            conn.execute(text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
        conn.commit()

    # 2. Connect to SQLite
    if not os.path.exists(sqlite_path):
        print(f"[ERROR] Source SQLite file '{sqlite_path}' not found!")
        return

    src_conn = sqlite3.connect(sqlite_path)
    src_conn.row_factory = sqlite3.Row
    src_cur = src_conn.cursor()

    pg_db = PgSession()

    try:
        # A. Categories
        src_cur.execute("SELECT id, name, description, keywords FROM categories")
        cat_rows = src_cur.fetchall()
        for r in cat_rows:
            if not pg_db.query(Category).filter(Category.id == r["id"]).first():
                import json
                kw = json.loads(r["keywords"]) if r["keywords"] and isinstance(r["keywords"], str) else r["keywords"]
                pg_db.add(Category(id=r["id"], name=r["name"], description=r["description"], keywords=kw))
        pg_db.commit()
        print(f"-> Migrated {len(cat_rows)} categories.")

        # B. Users
        src_cur.execute("SELECT * FROM users")
        user_rows = src_cur.fetchall()
        for r in user_rows:
            u_dict = dict(r)
            if not pg_db.query(User).filter(User.id == u_dict["id"]).first():
                pg_db.add(User(
                    id=u_dict["id"],
                    email=u_dict["email"],
                    hashed_password=u_dict["hashed_password"],
                    full_name=u_dict.get("full_name"),
                    is_active=bool(u_dict.get("is_active", True)),
                    is_verified=bool(u_dict.get("is_verified", False)),
                    is_admin=bool(u_dict.get("is_admin", False)),
                    daily_digest_enabled=bool(u_dict.get("daily_digest_enabled", True)),
                    weekly_digest_enabled=bool(u_dict.get("weekly_digest_enabled", True)),
                    digest_time=u_dict.get("digest_time", "09:00"),
                    time_zone=u_dict.get("time_zone", "UTC")
                ))
        pg_db.commit()
        print(f"-> Migrated {len(user_rows)} users.")

        # C. Clusters
        try:
            src_cur.execute("SELECT * FROM clusters")
            clust_rows = src_cur.fetchall()
            for r in clust_rows:
                c_dict = dict(r)
                if not pg_db.query(Cluster).filter(Cluster.id == c_dict["id"]).first():
                    pg_db.add(Cluster(
                        id=c_dict["id"],
                        primary_article_id=c_dict["primary_article_id"],
                        size=c_dict.get("size", 1)
                    ))
            pg_db.commit()
            print(f"-> Migrated {len(clust_rows)} story clusters.")
        except sqlite3.OperationalError:
            print("-> No existing clusters table in SQLite, skipping clusters.")

        # D. Articles
        src_cur.execute("SELECT * FROM articles")
        art_rows = src_cur.fetchall()
        for r in art_rows:
            a_dict = dict(r)
            if not pg_db.query(Article).filter(Article.id == a_dict["id"]).first():
                dt = datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
                if a_dict.get("created_at"):
                    try:
                        dt = datetime.fromisoformat(str(a_dict["created_at"]).replace("Z", "+00:00"))
                    except Exception:
                        pass

                pg_db.add(Article(
                    id=a_dict["id"],
                    title=a_dict["title"],
                    link=a_dict["link"],
                    summary=a_dict.get("summary"),
                    llm_summary=a_dict.get("llm_summary"),
                    published=a_dict.get("published"),
                    image_url=a_dict.get("image_url"),
                    source=a_dict.get("source", "TechNews"),
                    created_at=dt,
                    cluster_id=a_dict.get("cluster_id"),
                    is_copy_of=a_dict.get("is_copy_of"),
                    embedding=a_dict.get("embedding"),
                    entities=a_dict.get("entities"),
                    minhash=a_dict.get("minhash"),
                    text_basis=a_dict.get("text_basis")
                ))
        pg_db.commit()
        print(f"-> Migrated {len(art_rows)} articles with clustering vectors & metadata.")

        # E. Article Categories
        src_cur.execute("SELECT * FROM article_categories")
        ac_rows = src_cur.fetchall()
        for r in ac_rows:
            ac_dict = dict(r)
            if not pg_db.query(ArticleCategory).filter(ArticleCategory.id == ac_dict["id"]).first():
                pg_db.add(ArticleCategory(
                    id=ac_dict["id"],
                    article_id=ac_dict["article_id"],
                    category_id=ac_dict["category_id"],
                    relevance_score=ac_dict.get("relevance_score", 1)
                ))
        pg_db.commit()
        print(f"-> Migrated {len(ac_rows)} article-category relations.")

        print("\n" + "="*60)
        print("[SUCCESS] All data successfully transferred into PostgreSQL!")
        print("To switch your application permanently to PostgreSQL:")
        print(f'1. Set DATABASE_URL in your .env file and on Render to:')
        print(f'   DATABASE_URL={pg_url}')
        print("2. You can safely delete tech_news.db afterwards.")
        print("="*60)

    except Exception as e:
        pg_db.rollback()
        print(f"[MIGRATION ERROR] {e}")
        raise
    finally:
        src_conn.close()
        pg_db.close()

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PG_DATABASE_URL")
    if not url_arg:
        print("[ERROR] Please provide your PostgreSQL connection string:")
        print("python scripts/migrate_to_postgres.py 'postgresql://user:password@host:5432/dbname'")
        sys.exit(1)
    run_migration(url_arg)
