"""
dedup/verifier.py - Layer 3: Borderline LLM Verification via Groq.

Only ambiguous article pairs (T_low <= score < T_high from Layer 2) reach here.
Sends a yes/no prompt to Groq at temperature=0 and caches the verdict in SQLite
pair_cache so the same pair is never re-queried.

Non-blocking contract:
  - On any error (timeout, rate-limit, bad JSON, missing key) return "DIFFERENT"
    so the article creates a new cluster rather than incorrectly merging.
  - Cache hits bypass the API entirely.

Prompt structure (temperature=0):
  Task: determine if two news snippets report the SAME real-world event.
  Return exactly one word: SAME or DIFFERENT.
"""

import os
import sqlite3
import logging
from typing import Optional
from datetime import datetime, timezone

try:
    from groq import Groq
except ImportError:
    Groq = None  # type: ignore

from dedup.config import ClusterConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

VERDICT_SAME = "SAME"
VERDICT_DIFFERENT = "DIFFERENT"

VERIFIER_PROMPT_TEMPLATE = """You are a news deduplication assistant. Determine whether the two article snippets below report the SAME real-world event (same incident, same announcement, same news story), or DIFFERENT events.

Article A title: {title_a}
Article A snippet: {snippet_a}

Article B title: {title_b}
Article B snippet: {snippet_b}

Rules:
- Respond with exactly one word: SAME or DIFFERENT
- SAME means: the articles describe the same underlying event (even if wording, angle, or details differ)
- DIFFERENT means: the articles are about different events, even if they share a topic or company
- Do NOT explain; output only SAME or DIFFERENT"""


def _truncate(text: str, max_chars: int = 400) -> str:
    text = (text or "").strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


def _cache_key(id_a: str, id_b: str):
    """Return a canonical (smaller_id, larger_id) pair for symmetric caching."""
    return (min(id_a, id_b), max(id_a, id_b))


class PairVerifier:
    """
    Groq-backed LLM verifier for borderline article pairs with SQLite caching.
    Instantiate once and reuse across requests.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[ClusterConfig] = None
    ):
        self.config = config or DEFAULT_CONFIG
        self.custom_db_path = db_path
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tech_news.db"
        )
        if self.db_path.startswith("sqlite:///"):
            self.db_path = self.db_path.replace("sqlite:///", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(
        self,
        id_a: str,
        title_a: str,
        snippet_a: str,
        id_b: str,
        title_b: str,
        snippet_b: str,
    ) -> str:
        """
        Return "SAME" or "DIFFERENT".
        1. Check pair_cache first.
        2. Query Groq if not cached.
        3. On any error, return DIFFERENT (safe fallback).
        """
        a_key, b_key = _cache_key(id_a, id_b)

        # --- Cache lookup ---
        cached = self._cache_get(a_key, b_key)
        if cached is not None:
            logger.debug("pair_cache hit: %s/%s -> %s", a_key, b_key, cached)
            return cached

        # --- Groq call ---
        verdict = self._call_groq(title_a, snippet_a, title_b, snippet_b)

        # --- Persist ---
        self._cache_set(a_key, b_key, verdict)
        return verdict

    # ------------------------------------------------------------------
    # Groq call
    # ------------------------------------------------------------------

    def _call_groq(
        self,
        title_a: str, snippet_a: str,
        title_b: str, snippet_b: str
    ) -> str:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            logger.warning("GROQ_API_KEY not set; Layer 3 defaulting to DIFFERENT")
            return VERDICT_DIFFERENT

        if Groq is None:
            logger.warning("groq package not installed; Layer 3 defaulting to DIFFERENT")
            return VERDICT_DIFFERENT

        prompt = VERIFIER_PROMPT_TEMPLATE.format(
            title_a=_truncate(title_a, 150),
            snippet_a=_truncate(snippet_a, 400),
            title_b=_truncate(title_b, 150),
            snippet_b=_truncate(snippet_b, 400),
        )

        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=self.config.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.groq_temperature,
                max_tokens=5,
                timeout=self.config.groq_timeout_seconds,
            )
            raw = response.choices[0].message.content.strip().upper()
            verdict = VERDICT_SAME if raw.startswith("SAME") else VERDICT_DIFFERENT
            logger.debug("Groq verdict raw=%r -> %s", raw, verdict)
            return verdict

        except Exception as exc:
            logger.error("Layer 3 Groq error: %s — defaulting to DIFFERENT", exc)
            return VERDICT_DIFFERENT

    # ------------------------------------------------------------------
    # pair_cache persistence helpers (PostgreSQL & SQLite)
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _cache_get(self, a_id: str, b_id: str) -> Optional[str]:
        # Always look up in canonical (min, max) order for symmetry
        key_a, key_b = min(a_id, b_id), max(a_id, b_id)

        # 1. Isolated test database fixture
        if self.custom_db_path and os.path.exists(self.custom_db_path):
            try:
                conn = self._get_conn()
                cur = conn.execute(
                    "SELECT verdict FROM pair_cache WHERE a_id=? AND b_id=?",
                    (key_a, key_b)
                )
                row = cur.fetchone()
                conn.close()
                return row["verdict"] if row else None
            except Exception as exc:
                logger.debug("pair_cache sqlite read error: %s", exc)
                return None

        # 2. Production PostgreSQL / SQLAlchemy engine
        try:
            from backend.app.database import SessionLocal
            from backend.app.models import PairCache
            db = SessionLocal()
            try:
                rec = db.query(PairCache).filter(PairCache.a_id == key_a, PairCache.b_id == key_b).first()
                if rec:
                    return rec.verdict
            finally:
                db.close()
        except Exception:
            pass
        return None

    def _cache_set(self, a_id: str, b_id: str, verdict: str) -> None:
        # Always store in canonical (min, max) order
        key_a, key_b = min(a_id, b_id), max(a_id, b_id)

        # 1. Isolated test database fixture
        if self.custom_db_path and os.path.exists(self.custom_db_path):
            try:
                conn = self._get_conn()
                conn.execute(
                    """INSERT OR REPLACE INTO pair_cache (a_id, b_id, verdict, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (key_a, key_b, verdict, datetime.now(timezone.utc).isoformat())
                )
                conn.commit()
                conn.close()
                return
            except Exception as exc:
                logger.debug("pair_cache sqlite write error: %s", exc)
                return

        # 2. Production PostgreSQL / SQLAlchemy engine
        try:
            from backend.app.database import SessionLocal
            from backend.app.models import PairCache
            db = SessionLocal()
            try:
                rec = db.query(PairCache).filter(PairCache.a_id == key_a, PairCache.b_id == key_b).first()
                if rec:
                    rec.verdict = verdict
                    rec.created_at = datetime.now(timezone.utc)
                else:
                    db.add(PairCache(a_id=key_a, b_id=key_b, verdict=verdict, created_at=datetime.now(timezone.utc)))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
