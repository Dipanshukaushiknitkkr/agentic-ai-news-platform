"""
dedup/entities.py - Named Entity Extraction for Layer 2 clustering.

Uses spaCy en_core_web_sm (parser + lemmatizer disabled for speed).
Applies a configurable alias/regex list for new AI product names the small
model misses.  Falls back to capitalised title tokens when spaCy returns nothing.
"""

import re
from typing import List, Set, Optional
from dedup.config import ClusterConfig, DEFAULT_CONFIG

_NLP = None

def _get_nlp(model_name: str = "en_core_web_sm"):
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load(model_name, disable=["parser", "lemmatizer"])
    return _NLP


def _extract_alias_entities(text: str, aliases: List[str]) -> Set[str]:
    """
    Fast regex scan for configurable alias terms (e.g. "GPT-5", "Llama 3").
    Returns lower-cased matches for normalised comparison.
    """
    found: Set[str] = set()
    for alias in aliases:
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        if pattern.search(text):
            found.add(alias.lower())
    return found


def _extract_spacy_entities(
    text: str,
    target_labels: List[str],
    model_name: str = "en_core_web_sm"
) -> Set[str]:
    """Run spaCy NER and return a set of lower-cased entity texts for target labels."""
    nlp = _get_nlp(model_name)
    doc = nlp(text[:5000])          # cap at 5000 chars; RSS text is usually shorter
    return {
        ent.text.strip().lower()
        for ent in doc.ents
        if ent.label_ in target_labels
    }


def _capitalised_title_fallback(title: str) -> Set[str]:
    """
    If NER returns nothing, extract runs of capitalised tokens from the title
    as a rough proxy for named entities.
    Example: "OpenAI Releases New Model" -> {"openai", "releases", "new", "model"}
    We only keep words that start with uppercase (excluding first word bias).
    """
    words = title.split()
    return {
        w.lower()
        for w in words[1:]
        if w and w[0].isupper() and len(w) > 2
    }


def extract_entities(
    title: str,
    body: str,
    config: Optional[ClusterConfig] = None
) -> List[str]:
    """
    Extract named entities from title + body (capped at 500 chars from body for speed).
    
    Priority:
      1. Alias/regex matches (catches novel AI product names)
      2. spaCy NER (ORG, PRODUCT, PERSON)
      3. Capitalised title token fallback (when above return empty)
    
    Returns sorted, deduplicated list of lower-cased entity strings.
    """
    cfg = config or DEFAULT_CONFIG
    text_for_spacy = f"{title}. {body[:500]}" if body else title

    # Layer 1: alias scan
    alias_hits = _extract_alias_entities(text_for_spacy, cfg.entity_aliases)

    # Layer 2: spaCy NER
    spacy_hits = _extract_spacy_entities(
        text_for_spacy,
        cfg.target_entity_labels,
        cfg.spacy_model_name
    )

    combined = alias_hits | spacy_hits

    # Layer 3: fallback if nothing found
    if not combined:
        combined = _capitalised_title_fallback(title)

    return sorted(combined)


def entity_overlap_score(entities_a: List[str], entities_b: List[str]) -> float:
    """
    Fraction of shared entities: |A ∩ B| / min(|A|, |B|).
    Returns 0.0 if either set is empty.
    """
    if not entities_a or not entities_b:
        return 0.0
    set_a = set(entities_a)
    set_b = set(entities_b)
    intersection = len(set_a & set_b)
    min_size = min(len(set_a), len(set_b))
    return intersection / min_size if min_size > 0 else 0.0
