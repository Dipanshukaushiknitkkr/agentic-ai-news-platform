import pytest
from dedup.legacy import (
    token_jaccard,
    levenshtein_ratio,
    is_duplicate_article,
    filter_duplicates,
    LEGACY_JACCARD_THRESHOLD,
    LEGACY_LEVENSHTEIN_THRESHOLD
)

def test_legacy_metrics():
    s1 = "OpenAI releases GPT-5 with massive intelligence improvements"
    s2 = "OpenAI releases GPT-5 with massive intelligence improvements"
    assert token_jaccard(s1, s2) == 1.0
    assert levenshtein_ratio(s1, s2) == 1.0

    # Near verbatim copy
    s3 = "OpenAI releases GPT-5 with massive intelligence improvements today"
    assert token_jaccard(s1, s3) >= LEGACY_JACCARD_THRESHOLD
    assert levenshtein_ratio(s1, s3) >= LEGACY_LEVENSHTEIN_THRESHOLD
    assert is_duplicate_article(s1, s3) is True

def test_legacy_limitation_different_angles_fail_to_match():
    """
    Demonstrates the exact failure mode of the legacy algorithm:
    Two articles about the exact same event written from different editorial angles
    have low token overlap and low Levenshtein ratio, so legacy dedup fails to group them.
    """
    s1 = "OpenAI launches GPT-5 frontier model featuring expanded reasoning capabilities"
    s2 = "Compute bottlenecks force Sam Altman to limit access to newly released flagship AI"
    
    jaccard = token_jaccard(s1, s2)
    lev = levenshtein_ratio(s1, s2)
    
    assert jaccard < LEGACY_JACCARD_THRESHOLD
    assert lev < LEGACY_LEVENSHTEIN_THRESHOLD
    assert is_duplicate_article(s1, s2) is False

def test_filter_duplicates():
    articles = [
        {"title": "Meta releases Llama 3 open weights model", "source": "TechCrunch"},
        {"title": "Meta releases Llama 3 open weights model today", "source": "The Verge"}, # near duplicate
        {"title": "Google announces quantum computing breakthrough", "source": "Wired"},
    ]
    unique, discarded = filter_duplicates(articles)
    assert len(unique) == 2
    assert len(discarded) == 1
    assert discarded[0]["source"] == "The Verge"
