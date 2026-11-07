"""
dedup/normalize.py - Text normalization and adaptive shingling for MinHash LSH copy detection.

Rules:
- Lowercase, strip URLs, strip HTML tags, remove punctuation, normalize whitespace.
- k=5 shingles for full text; k=3 for short RSS snippets (< 80 words).
- Notes text_basis ('full' vs 'snippet') as copy detection on snippets has lower confidence.
"""

import re
from typing import List, Set, Tuple, Optional
from datasketch import MinHash

URL_REGEX = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
HTML_REGEX = re.compile(r'<[^>]+>', re.IGNORECASE)
PUNCT_REGEX = re.compile(r'[^\w\s]', re.UNICODE)
WHITESPACE_REGEX = re.compile(r'\s+')

def normalize_text(text: str) -> str:
    """Normalize text: strip HTML, strip URLs, strip punctuation, lowercase, collapse whitespace."""
    if not text:
        return ""
    # Strip HTML tags
    cleaned = HTML_REGEX.sub(" ", text)
    # Strip URLs
    cleaned = URL_REGEX.sub(" ", cleaned)
    # Lowercase
    cleaned = cleaned.lower()
    # Strip punctuation
    cleaned = PUNCT_REGEX.sub(" ", cleaned)
    # Collapse whitespace
    cleaned = WHITESPACE_REGEX.sub(" ", cleaned).strip()
    return cleaned

def tokenize(text: str) -> List[str]:
    """Tokenize normalized text into word tokens."""
    norm = normalize_text(text)
    return norm.split() if norm else []

def determine_text_basis(text: str, threshold_words: int = 80) -> str:
    """Returns 'snippet' if text has fewer than threshold_words, else 'full'."""
    words = tokenize(text)
    return "snippet" if len(words) < threshold_words else "full"

def generate_shingles(tokens: List[str], k: int) -> Set[str]:
    """Generate k-word shingles from a sequence of tokens."""
    if not tokens:
        return set()
    if len(tokens) < k:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}

def build_minhash_from_text(
    text: str,
    num_perm: int = 128,
    k_full: int = 5,
    k_snippet: int = 3,
    snippet_threshold: int = 80
) -> Tuple[MinHash, str]:
    """
    Builds a datasketch MinHash object for the given text.
    Automatically selects k=3 for snippets (< 80 words) and k=5 for full text.
    Returns (minhash, text_basis).
    """
    tokens = tokenize(text)
    text_basis = "snippet" if len(tokens) < snippet_threshold else "full"
    k = k_snippet if text_basis == "snippet" else k_full

    m = MinHash(num_perm=num_perm)
    shingles = generate_shingles(tokens, k)
    for s in shingles:
        m.update(s.encode('utf-8'))

    return m, text_basis
