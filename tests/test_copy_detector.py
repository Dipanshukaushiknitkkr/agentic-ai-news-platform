import pytest
from datasketch import MinHash
from dedup.config import ClusterConfig
from dedup.normalize import (
    normalize_text,
    tokenize,
    generate_shingles,
    determine_text_basis,
    build_minhash_from_text
)
from dedup.copy_detector import CopyDetector, CopyMatchResult

def test_text_normalization():
    raw = "<p>Check out https://techcrunch.com for updates! OpenAI's new model, GPT-5, is here.</p>"
    norm = normalize_text(raw)
    assert "https" not in norm
    assert "<p>" not in norm
    assert "openai" in norm
    assert "gpt 5" in norm or "gpt" in norm
    
    tokens = tokenize(raw)
    assert "check" in tokens
    assert "out" in tokens

def test_adaptive_shingling():
    short_text = "OpenAI launches GPT-5 reasoning model with improved benchmark scores."
    long_text = " ".join(["OpenAI launches new advanced artificial intelligence model with high reasoning capacity."] * 12)
    
    assert determine_text_basis(short_text, threshold_words=80) == "snippet"
    assert determine_text_basis(long_text, threshold_words=80) == "full"
    
    m_short, basis_short = build_minhash_from_text(short_text, snippet_threshold=80)
    assert basis_short == "snippet"
    
    m_long, basis_long = build_minhash_from_text(long_text, snippet_threshold=80)
    assert basis_long == "full"

def test_exact_and_syndicated_copy_detection():
    detector = CopyDetector()
    
    base_text = (
        "SAN FRANCISCO — OpenAI announced on Thursday that it is launching GPT-5, "
        "its next generation artificial intelligence model featuring improved reasoning, "
        "coding abilities, and math problem solving. The new system will be rolled out "
        "gradually to developers and ChatGPT Plus subscribers over the next several weeks. "
        "Company executives noted that compute costs have dropped significantly."
    )
    
    res1 = detector.check_copy(base_text, published="2026-11-01T10:00:00Z")
    assert res1.is_copy is False
    assert res1.minhash is not None
    
    # Register art1
    detector.register(
        article_id="art1",
        minhash=res1.minhash,
        published="2026-11-01T10:00:00Z",
        cluster_id=101
    )
    
    # Test identical copy (art2)
    res2 = detector.check_copy(base_text, published="2026-11-01T10:30:00Z")
    assert res2.is_copy is True
    assert res2.original_article_id == "art1"
    assert res2.cluster_id == 101
    assert res2.jaccard_similarity >= 0.99
    
    # Test syndicated wire copy with slight outlet lead-in
    syndicated_text = (
        "According to reports from San Francisco, OpenAI announced on Thursday that it is launching GPT-5, "
        "its next generation artificial intelligence model featuring improved reasoning, "
        "coding abilities, and math problem solving. The new system will be rolled out "
        "gradually to developers and ChatGPT Plus subscribers over the next several weeks. "
        "Company executives noted that compute costs have dropped significantly."
    )
    res3 = detector.check_copy(syndicated_text, published="2026-11-01T11:00:00Z")
    assert res3.is_copy is True
    assert res3.original_article_id == "art1"

def test_different_article_not_detected_as_copy():
    detector = CopyDetector()
    
    art1_text = (
        "OpenAI announced the release of GPT-5 today with massive context windows "
        "and enhanced multi-modal audio capabilities for enterprise customers."
    )
    res1 = detector.check_copy(art1_text)
    detector.register("art1", res1.minhash, "2026-11-01T10:00:00Z", cluster_id=1)
    
    art2_text = (
        "Google Quantum AI lab in Santa Barbara achieved quantum supremacy milestone "
        "demonstrating error-corrected qubits running Willow architecture."
    )
    res2 = detector.check_copy(art2_text)
    assert res2.is_copy is False
    assert res2.original_article_id is None

def test_earliest_published_attribution():
    detector = CopyDetector()
    
    text = (
        "Meta has open sourced Llama 4 featuring native mixture of experts "
        "architecture with 400 billion total parameters and 128 experts active."
    )
    res = detector.check_copy(text)
    
    # Register earlier article
    detector.register("art_earlier", res.minhash, "2026-11-01T08:00:00Z", cluster_id=200)
    # Register later copy
    detector.register("art_later", res.minhash, "2026-11-01T09:30:00Z", cluster_id=200)
    
    # New query should link to art_earlier
    query_res = detector.check_copy(text, published="2026-11-01T12:00:00Z")
    assert query_res.is_copy is True
    assert query_res.original_article_id == "art_earlier"

def test_minhash_serialization():
    detector = CopyDetector()
    text = "Testing MinHash binary serialization and deserialization integrity."
    res = detector.check_copy(text)
    
    blob = res.minhash_bytes
    assert isinstance(blob, bytes)
    
    deserialized = detector.deserialize_minhash(blob)
    assert deserialized.jaccard(res.minhash) == 1.0
