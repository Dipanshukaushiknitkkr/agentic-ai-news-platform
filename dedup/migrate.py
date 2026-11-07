"""
dedup/migrate.py - Universal (PostgreSQL & SQLite) Database Migration Script for Story Clustering.

Supports:
- PostgreSQL (Production / Local) with BYTEA, JSON, SERIAL, TIMESTAMPTZ
- SQLite (Local fallback & Unit testing)

Adds:
- articles columns: cluster_id, is_copy_of, embedding, entities, minhash, text_basis, clustered_at
- clusters table: (id, primary_article_id, created_at, updated_at, size)
- pair_cache table: (a_id, b_id, verdict, created_at, PRIMARY KEY(a_id, b_id))
- cluster_log table: (id, article_id, decision, best_cluster_id, best_score, layer, created_at)

Safe, idempotent, preserves all existing data.
"""

import sqlite3
import os
import sys
from typing import Optional

def upgrade(db_path: Optional[str] = None) -> None:
    """Apply migrations idempotently to PostgreSQL or SQLite."""
    # Check if a custom SQLite db_path was explicitly passed (e.g. in unit tests)
    if db_path:
        _upgrade_sqlite(db_path)
        return

    # Otherwise use SQLAlchemy engine (which respects DATABASE_URL for Postgres or SQLite)
    try:
        from backend.app.database import engine, Base
        from sqlalchemy import inspect, text

        # 1. Create any missing tables (clusters, pair_cache, cluster_log, etc.)
        Base.metadata.create_all(bind=engine)

        # 2. Inspect articles table for missing columns
        inspector = inspect(engine)
        if "articles" in inspector.get_table_names():
            existing_cols = {col["name"] for col in inspector.get_columns("articles")}
            is_postgres = (engine.dialect.name == "postgresql")

            blob_type = "BYTEA" if is_postgres else "BLOB"
            ts_type = "TIMESTAMP WITH TIME ZONE" if is_postgres else "TEXT"
            json_type = "JSON" if is_postgres else "TEXT"

            cols_to_add = [
                ("cluster_id", "INTEGER"),
                ("is_copy_of", "VARCHAR(255)" if is_postgres else "TEXT"),
                ("embedding", blob_type),
                ("entities", json_type),
                ("minhash", blob_type),
                ("text_basis", "VARCHAR(50)" if is_postgres else "TEXT"),
                ("clustered_at", ts_type),
            ]

            with engine.connect() as conn:
                for col_name, col_type in cols_to_add:
                    if col_name not in existing_cols:
                        if is_postgres:
                            conn.execute(text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        else:
                            conn.execute(text(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}"))
                        print(f"[MIGRATION] Added column '{col_name}' ({col_type}) to articles.")
                conn.commit()

        print(f"[MIGRATION] Upgrade completed successfully for {engine.dialect.name}.")
    except Exception as e:
        # Fallback to local SQLite if SQLAlchemy import fails
        print(f"[MIGRATION NOTE] Engine migration fallback: {e}")
        _upgrade_sqlite()

def _upgrade_sqlite(db_path: Optional[str] = None) -> None:
    """SQLite-specific migration path for unit tests."""
    target = db_path or os.getenv("DATABASE_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tech_news.db"
    )
    if target.startswith("sqlite:///"):
        target = target.replace("sqlite:///", "")

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(articles)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        new_columns = [
            ("cluster_id", "INTEGER"),
            ("is_copy_of", "TEXT"),
            ("embedding", "BLOB"),
            ("entities", "TEXT"),
            ("minhash", "BLOB"),
            ("text_basis", "TEXT"),
            ("clustered_at", "TEXT"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
                print(f"[MIGRATION] Added column '{col_name}' ({col_type}) to articles.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_article_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                size INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clusters_updated_at ON clusters(updated_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_is_copy_of ON articles(is_copy_of)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pair_cache (
                a_id TEXT NOT NULL,
                b_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (a_id, b_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cluster_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                best_cluster_id INTEGER,
                best_score REAL,
                layer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_log_art ON cluster_log(article_id)")

        conn.commit()
    finally:
        conn.close()

def downgrade(db_path: Optional[str] = None) -> None:
    """Revert migration tables."""
    target = db_path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tech_news.db"
    )
    if target.startswith("sqlite:///"):
        target = target.replace("sqlite:///", "")

    conn = sqlite3.connect(target)
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS cluster_log")
        cursor.execute("DROP TABLE IF EXISTS pair_cache")
        cursor.execute("DROP TABLE IF EXISTS clusters")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    db_arg = sys.argv[2] if len(sys.argv) > 2 else None
    if action == "downgrade":
        downgrade(db_arg)
    else:
        upgrade(db_arg)
