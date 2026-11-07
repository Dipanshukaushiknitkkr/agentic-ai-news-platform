"""
dedup/legacy.py - Preserved Legacy Jaccard + Levenshtein Deduplication Logic.

KEPT ONLY AS AN EVALUATION BASELINE. DO NOT USE FOR PRODUCTION CLUSTERING.
Extracted unmodified from backend/scrapers/techcrunch.py and backend/services/categorization_service.py.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Set, Dict, Any

LEGACY_JACCARD_THRESHOLD = 0.48
LEGACY_LEVENSHTEIN_THRESHOLD = 0.62

LEGACY_STOPWORDS: Set[str] = {
    'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'for', 'to', 'of', 'in',
    'with', 'by', 'as', 'from', 'that', 'this', 'it', 'are', 'be', 'was', 'were', 'has',
    'had', 'have', 'but', 'not', 'if', 'then', 'so', 'do', 'does', 'did', 'can', 'will',
    'just', 'about', 'into', 'over', 'after', 'before', 'more', 'less', 'than', 'up',
    'out', 'off', 'no', 'yes', 'you', 'new', 'says', 'how', 'why', 'what', 'first',
    'here', 'now', 'its', 'itself', 'all', 'any', 'both', 'each', 'few', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'too', 'very', 'announced', 'announces', 'launches', 'unveils'
}

def legacy_clean_title_tokens(title: str) -> Set[str]:
    """Extract clean content keywords from headline (legacy method)."""
    words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', title.lower())
    return set(w for w in words if w not in LEGACY_STOPWORDS)

def token_jaccard(title_a: str, title_b: str) -> float:
    """Compute token Jaccard similarity between two headlines after stopword removal."""
    toks_a = legacy_clean_title_tokens(title_a)
    toks_b = legacy_clean_title_tokens(title_b)
    if not toks_a or not toks_b:
        return 0.0
    union = len(toks_a | toks_b)
    return len(toks_a & toks_b) / union if union > 0 else 0.0

def levenshtein_ratio(title_a: str, title_b: str) -> float:
    """Compute SequenceMatcher character similarity ratio between two lowercased headlines."""
    return SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()

def is_duplicate_article(
    title_a: str,
    title_b: str,
    jaccard_thresh: float = LEGACY_JACCARD_THRESHOLD,
    seq_thresh: float = LEGACY_LEVENSHTEIN_THRESHOLD
) -> bool:
    """Legacy check: flags duplicate if Jaccard >= 0.48 (with >=3 common tokens) OR SequenceMatcher >= 0.62."""
    toks_a = legacy_clean_title_tokens(title_a)
    toks_b = legacy_clean_title_tokens(title_b)
    intersection = len(toks_a & toks_b)
    union = len(toks_a | toks_b)
    jaccard = intersection / union if union > 0 else 0.0
    seq_ratio = SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()

    return (jaccard >= jaccard_thresh and intersection >= 3) or seq_ratio >= seq_thresh

def legacy_is_duplicate_headline(
    new_title: str,
    existing_titles: List[str],
    jaccard_thresh: float = LEGACY_JACCARD_THRESHOLD,
    seq_thresh: float = LEGACY_LEVENSHTEIN_THRESHOLD
) -> Tuple[bool, Optional[str]]:
    """Legacy helper: checks a title against a list of already seen titles."""
    for existing in existing_titles:
        if is_duplicate_article(new_title, existing, jaccard_thresh, seq_thresh):
            return True, existing
    return False, None

def filter_duplicates(
    articles: List[Dict[str, Any]],
    jaccard_thresh: float = LEGACY_JACCARD_THRESHOLD,
    seq_thresh: float = LEGACY_LEVENSHTEIN_THRESHOLD
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filters duplicate articles using legacy deduplication (near-duplicates discarded)."""
    unique_articles = []
    discarded_articles = []
    seen_titles = []

    for art in articles:
        title = art.get("title", "")
        is_dup, _ = legacy_is_duplicate_headline(title, seen_titles, jaccard_thresh, seq_thresh)
        if is_dup:
            discarded_articles.append(art)
        else:
            unique_articles.append(art)
            seen_titles.append(title)

    return unique_articles, discarded_articles
