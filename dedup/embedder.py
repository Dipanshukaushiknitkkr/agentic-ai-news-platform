"""
dedup/embedder.py - Singleton sentence-transformer embedding model for Layer 2.

Loads `all-MiniLM-L6-v2` ONCE at startup, produces L2-unit-normalised 384-dim vectors.
Text basis: title + first ~150 words of body (or RSS snippet).
"""

import numpy as np
from typing import Optional, List
from functools import lru_cache

_MODEL = None
_MODEL_NAME = None

def _get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Lazy-load the embedding model exactly once per process."""
    global _MODEL, _MODEL_NAME
    if _MODEL is None or _MODEL_NAME != model_name:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
    return _MODEL


def build_text_for_embedding(title: str, body: str, max_body_words: int = 150) -> str:
    """
    Concatenate title + first max_body_words words of body for embedding.
    If body is empty / only whitespace, falls back to title only.
    """
    title = (title or "").strip()
    body = (body or "").strip()
    if body:
        body_words = body.split()[:max_body_words]
        body_snippet = " ".join(body_words)
        return f"{title}. {body_snippet}"
    return title


def embed_texts(
    texts: List[str],
    model_name: str = "all-MiniLM-L6-v2",
    normalize: bool = True,
) -> np.ndarray:
    """
    Embed a list of texts. Returns a float32 NumPy array of shape (N, D).
    When normalize=True each row is L2-unit-normalised so cosine_sim = dot product.
    """
    model = _get_model(model_name)
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    if normalize:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)   # avoid division by zero
        vecs = vecs / norms
    return vecs.astype(np.float32)


def embed_single(
    text: str,
    model_name: str = "all-MiniLM-L6-v2",
    normalize: bool = True,
) -> np.ndarray:
    """Embed a single text, returns a 1-D float32 array of shape (D,)."""
    return embed_texts([text], model_name=model_name, normalize=normalize)[0]
