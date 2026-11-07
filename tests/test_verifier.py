"""
tests/test_verifier.py - Unit tests for Layer 3 PairVerifier.

All tests run without hitting real Groq API (mocked or offline scenarios).
"""
import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from dedup.verifier import PairVerifier, VERDICT_SAME, VERDICT_DIFFERENT
from dedup.migrate import upgrade


@pytest.fixture
def db_with_pair_cache():
    """Temp DB with pair_cache table migrated."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE articles (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, link TEXT NOT NULL,
        summary TEXT, llm_summary TEXT, published TEXT,
        image_url TEXT, source TEXT DEFAULT 'TechNews', created_at TEXT
    )""")
    conn.commit()
    conn.close()
    upgrade(path)
    yield path
    os.remove(path)


def test_no_api_key_returns_different(db_with_pair_cache):
    """Missing GROQ_API_KEY must return DIFFERENT safely (no crash)."""
    verifier = PairVerifier(db_path=db_with_pair_cache)
    with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
        result = verifier.verify(
            "a1", "OpenAI launches GPT-5", "OpenAI released GPT-5 today.",
            "a2", "Sam Altman unveils new model", "Sam Altman showed the new model."
        )
    assert result == VERDICT_DIFFERENT


def test_cache_hit_skips_groq(db_with_pair_cache):
    """A cached verdict must be returned without calling Groq."""
    verifier = PairVerifier(db_path=db_with_pair_cache)
    # Pre-seed the cache
    verifier._cache_set("a1", "a2", VERDICT_SAME)

    with patch.object(verifier, "_call_groq") as mock_groq:
        result = verifier.verify("a1", "Title A", "Body A", "a2", "Title B", "Body B")

    mock_groq.assert_not_called()
    assert result == VERDICT_SAME


def test_cache_is_symmetric(db_with_pair_cache):
    """Verdict stored as (a1,a2) must be retrieved even when queried as (a2,a1)."""
    verifier = PairVerifier(db_path=db_with_pair_cache)
    verifier._cache_set("a1", "a2", VERDICT_DIFFERENT)

    # Query in reverse order
    cached = verifier._cache_get("a2", "a1")
    assert cached == VERDICT_DIFFERENT


def test_groq_error_returns_different(db_with_pair_cache):
    """Any exception from Groq must silently return DIFFERENT."""
    verifier = PairVerifier(db_path=db_with_pair_cache)

    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}):
        with patch("dedup.verifier.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = Exception("Rate limited")
            result = verifier.verify(
                "a1", "OpenAI GPT-5", "Details here.",
                "a2", "Sam Altman model", "More details."
            )

    assert result == VERDICT_DIFFERENT


def test_groq_same_verdict_cached(db_with_pair_cache):
    """When Groq returns SAME, it must be persisted in pair_cache."""
    verifier = PairVerifier(db_path=db_with_pair_cache)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "SAME"

    with patch.dict(os.environ, {"GROQ_API_KEY": "fake-key"}):
        with patch("dedup.verifier.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            result = verifier.verify("a1", "Title A", "Snippet A", "a2", "Title B", "Snippet B")

    assert result == VERDICT_SAME
    # Check it's cached (symmetric key: a1 < a2)
    assert verifier._cache_get("a1", "a2") == VERDICT_SAME
