import os
import sqlite3
import tempfile
import pytest
from dedup.migrate import upgrade, downgrade

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Initialize initial articles table as it was before migration
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            llm_summary TEXT,
            published TEXT,
            image_url TEXT,
            source TEXT DEFAULT 'TechNews',
            created_at TEXT
        )
    """)
    cur.execute("""
        INSERT INTO articles (id, title, link, summary)
        VALUES ('art1', 'OpenAI announces GPT-5', 'http://example.com/1', 'OpenAI launches new model')
    """)
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

def test_migration_upgrade_and_downgrade(temp_db):
    # Run upgrade
    upgrade(temp_db)
    
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    
    # Verify new columns on articles
    cur.execute("PRAGMA table_info(articles)")
    cols = {row[1] for row in cur.fetchall()}
    for expected_col in ["cluster_id", "is_copy_of", "embedding", "entities", "minhash", "text_basis", "clustered_at"]:
        assert expected_col in cols, f"Missing column {expected_col}"
        
    # Verify new tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "clusters" in tables
    assert "pair_cache" in tables
    assert "cluster_log" in tables
    
    # Verify existing data is preserved intact
    cur.execute("SELECT id, title FROM articles WHERE id='art1'")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "art1"
    assert row[1] == "OpenAI announces GPT-5"
    
    conn.close()
    
    # Test idempotence: running upgrade again shouldn't fail
    upgrade(temp_db)
    
    # Test downgrade
    downgrade(temp_db)
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_after_down = {row[0] for row in cur.fetchall()}
    assert "clusters" not in tables_after_down
    assert "pair_cache" not in tables_after_down
    assert "cluster_log" not in tables_after_down
    conn.close()
