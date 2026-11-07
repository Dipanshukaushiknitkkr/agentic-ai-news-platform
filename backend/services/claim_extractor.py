"""
claim_extractor.py - Grounded Claim Extractor with Anti-Hallucination Evidence Spans.

Extracts structured factual claims from articles, strictly requiring:
1. Exact quote span (evidence sentence from the text).
2. Attribution type (official PR vs anonymous leak vs direct investigation vs citation).
3. Deterministic normalization via claim_normalizer.
4. Python-level grounding verification: drops claims whose quote_span does not exist in the source text.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

try:
    from backend.app.groq_client import call_groq
    from backend.services.claim_normalizer import (
        canonicalize_attribute,
        parse_numeric_with_unit,
        normalize_qualifier
    )
except ImportError:
    from app.groq_client import call_groq
    from services.claim_normalizer import (
        canonicalize_attribute,
        parse_numeric_with_unit,
        normalize_qualifier
    )

CLAIM_EXTRACTION_PROMPT = """You are an investigative NLP claim extractor for computational journalism.
Deconstruct the provided technology news article into atomic, verifiable factual claims.

For each atomic claim, you MUST extract:
1. "entity": The primary company, model, person, or product (e.g. "OpenAI", "GPT-5", "Anthropic", "Apple").
2. "attribute": The specific metric or property (e.g. "valuation", "round_size", "subscription_cost", "context_length", "release_date", "model_parameters", "headcount_reduction").
3. "raw_value": The verbatim value mentioned (e.g. "$40B", "$20/month", "1M tokens", "10,000 employees", "October 2026").
4. "qualifier": Any tier, region, scope, or bound (e.g. "Plus tier", "Enterprise only", "up to", "initially in US", "minimum"). If none, use null.
5. "attribution_type": MUST be one of:
   - "official_statement": on-record statement, official company blog, press release, CEO announcement.
   - "anonymous_leak": "sources familiar with the matter", "insiders say", "unnamed report".
   - "direct_investigation": the outlet's own benchmark, teardown, testing, or legal filing.
   - "secondary_citation": citing another news outlet (e.g. "as first reported by The Information").
6. "quote_span": The EXACT, VERBATIM sentence from the text containing this claim. DO NOT paraphrase or fabricate.

RETURN ONLY A VALID JSON ARRAY OF OBJECTS with these exact keys:
[
  {
    "entity": "OpenAI",
    "attribute": "subscription_cost",
    "raw_value": "$20/month",
    "qualifier": "Plus tier",
    "attribution_type": "official_statement",
    "quote_span": "The company announced ChatGPT Plus will remain $20/month for individual subscribers."
  }
]
If no atomic claims with concrete values exist, return []."""

def verify_quote_grounding(quote_span: str, source_text: str, threshold: float = 0.70) -> bool:
    """
    Verifies that the quote_span is genuinely grounded in the source text.
    Uses normalized substring match and token overlap to reject LLM hallucinations.
    """
    if not quote_span or not source_text:
        return False
        
    norm_quote = re.sub(r"[^\w\s]", "", quote_span.lower()).strip()
    norm_source = re.sub(r"[^\w\s]", "", source_text.lower()).strip()
    
    # Exact substring check
    if norm_quote in norm_source:
        return True
        
    # High-overlap token check for minor punctuation or whitespace truncations
    q_tokens = set(norm_quote.split())
    if not q_tokens:
        return False
    s_tokens = set(norm_source.split())
    
    intersection = len(q_tokens & s_tokens)
    overlap_ratio = intersection / len(q_tokens)
    return overlap_ratio >= threshold

class GroundedClaimExtractor:
    """Extracts grounded, normalized claims from article text."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
        
    def extract_claims_from_text(self, text: str, outlet: str = "Unknown", publish_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extracts and grounds claims from an article."""
        if not text or len(text.strip()) < 30:
            return []
            
        api_key = self.api_key or os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
        if not api_key:
            print("[CLAIM_EXTRACTOR] Groq API key not configured, returning empty claims.")
            return []
            
        # Limit text payload to avoid context bloat while keeping substantive facts
        truncated_text = text[:3500]
        
        payload = {
            "temperature": 0.1,  # Low temperature for strict factual extraction
            "max_tokens": 800,
            "messages": [
                {"role": "system", "content": CLAIM_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Outlet: {outlet}\nPublish Date: {publish_time or 'Recent'}\nArticle Text:\n{truncated_text}"}
            ]
        }
        
        try:
            raw_response, model_used = call_groq(api_key, payload, timeout=16)
            if not raw_response:
                return []
                
            # Clean markdown formatting if present
            clean_text = raw_response.strip()
            if clean_text.startswith("```"):
                parts = clean_text.split("```")
                if len(parts) >= 2:
                    clean_text = parts[1]
                    if clean_text.startswith("json"):
                        clean_text = clean_text[4:]
            clean_text = clean_text.strip()
            
            raw_claims = json.loads(clean_text)
            if not isinstance(raw_claims, list):
                return []
                
            validated_claims = []
            for item in raw_claims:
                if not isinstance(item, dict):
                    continue
                    
                entity = str(item.get("entity", "")).strip()
                attribute = str(item.get("attribute", "")).strip()
                raw_val = str(item.get("raw_value", "")).strip()
                quote_span = str(item.get("quote_span", "")).strip()
                attribution = str(item.get("attribution_type", "secondary_citation")).strip()
                qualifier = item.get("qualifier")
                if qualifier:
                    qualifier = str(qualifier).strip()
                    
                if not entity or not attribute or not raw_val:
                    continue
                    
                # Anti-Hallucination: Verify quote_span actually exists in the source text
                if not verify_quote_grounding(quote_span, truncated_text):
                    # Quote hallucinated by LLM -> discard claim
                    continue
                    
                # Deterministic Normalization
                canonical_attr = canonicalize_attribute(attribute)
                norm_val, unit = parse_numeric_with_unit(raw_val)
                canonical_qual = normalize_qualifier(qualifier)
                
                claim_obj = {
                    "entity": entity,
                    "raw_attribute": attribute,
                    "canonical_attribute": canonical_attr,
                    "raw_value": raw_val,
                    "normalized_value": norm_val if norm_val is not None else raw_val,
                    "unit": unit,
                    "qualifier": qualifier,
                    "canonical_qualifier": canonical_qual,
                    "attribution_type": attribution,
                    "quote_span": quote_span,
                    "outlet": outlet,
                    "publish_time": publish_time
                }
                validated_claims.append(claim_obj)
                
            return validated_claims
            
        except Exception as e:
            print(f"[CLAIM_EXTRACTOR ERROR]: {e}")
            return []

claim_extractor = GroundedClaimExtractor()
