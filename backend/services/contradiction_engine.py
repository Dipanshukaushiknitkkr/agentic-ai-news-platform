"""
contradiction_engine.py - Cross-Source Claim Alignment & Origin-Aware Contradiction Engine.

Features:
1. Origin-Aware Attribution: Distinguishes corporate PR echoes from independent investigative reporting.
2. Contradiction Radar: Detects numeric, date, and factual discrepancies with side-by-side auditable quote spans.
3. Scoped Distinction: Differentiates tier/scope/region differences from true conflicts.
4. Mathematically Bounded Agreement Index: Clamped 0-100% agreement metric with origin discounting.
"""

from typing import List, Dict, Any, Optional
import math

try:
    from backend.services.claim_normalizer import compare_claim_pair
    from backend.services.claim_extractor import claim_extractor
except ImportError:
    from services.claim_normalizer import compare_claim_pair
    from services.claim_extractor import claim_extractor

# Origin weight mapping based on journalistic independence
ORIGIN_WEIGHTS = {
    "direct_investigation": 1.0,  # Outlet's own benchmark, teardown, testing, court document
    "official_statement": 0.70,   # Corporate press release, blog post, official spokesperson
    "anonymous_leak": 0.40,       # "People familiar with the matter", unnamed source
    "secondary_citation": 0.15,   # Re-blogging another outlet's reporting
}

class ContradictionEngine:
    """Analyzes clusters of articles to detect contradictions, PR echoes, and agreement."""
    
    def calculate_claim_corroboration(self, supporting_origins: List[str]) -> float:
        """
        Calculates corroborated weight: S_c = 1 - product(1 - w_i)
        Prevents PR inflation: repeating a press release counts as one origin.
        """
        if not supporting_origins:
            return 0.0
            
        prod = 1.0
        # Deduplicate origin types to prevent artificial inflation from 3 outlets repeating 1 PR
        unique_origins = set(supporting_origins)
        for origin in unique_origins:
            w = ORIGIN_WEIGHTS.get(origin, 0.20)
            prod *= (1.0 - w)
            
        return round(1.0 - prod, 4)

    def analyze_story_cluster(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Performs cross-source fact alignment and contradiction detection across multiple articles.
        
        Args:
            articles: List of dicts with 'id', 'title', 'summary', 'source', 'published'
            
        Returns:
            Structured audit report with contradictions, PR echoes, corroborated facts, and Agreement Index.
        """
        if not articles:
            return {
                "agreement_index": 0.0,
                "confidence_level": "None",
                "summary": "No articles provided for cross-check.",
                "contradictions": [],
                "pr_echoes": [],
                "corroborated_facts": [],
                "single_source_claims": []
            }
            
        # 1. Extract grounded claims from all articles
        all_claims = []
        for art in articles:
            outlet = art.get("source") or "Unknown Outlet"
            content = f"{art.get('title', '')}. {art.get('summary', '')} {art.get('llm_summary', '')}"
            pub_date = art.get("published", "")
            
            claims = claim_extractor.extract_claims_from_text(content, outlet=outlet, publish_time=pub_date)
            for c in claims:
                c["article_id"] = art.get("id")
            all_claims.extend(claims)
            
        if not all_claims:
            return {
                "agreement_index": 100.0 if len(articles) <= 1 else 75.0,
                "confidence_level": "Low (No concrete metrics extracted)",
                "summary": "Articles contain general narrative reporting without concrete extractable metrics.",
                "contradictions": [],
                "pr_echoes": [],
                "corroborated_facts": [],
                "single_source_claims": []
            }
            
        # 2. Group claims by (canonical_entity, canonical_attribute)
        grouped_claims: Dict[str, List[Dict[str, Any]]] = {}
        for c in all_claims:
            entity_key = c.get("entity", "entity").strip().lower()
            attr_key = c.get("canonical_attribute", "attribute")
            key = f"{entity_key}::{attr_key}"
            if key not in grouped_claims:
                grouped_claims[key] = []
            grouped_claims[key].append(c)
            
        contradictions = []
        pr_echoes = []
        corroborated_facts = []
        single_source_claims = []
        
        claim_support_scores = []
        
        # 3. Analyze each group
        for key, claims_in_group in grouped_claims.items():
            outlets_involved = set(c.get("outlet") for c in claims_in_group)
            
            # Case A: Only one outlet mentioned this claim
            if len(outlets_involved) == 1:
                claim = claims_in_group[0]
                single_source_claims.append({
                    "entity": claim.get("entity"),
                    "attribute": claim.get("raw_attribute"),
                    "canonical_attribute": claim.get("canonical_attribute"),
                    "value": claim.get("raw_value"),
                    "qualifier": claim.get("qualifier"),
                    "outlet": claim.get("outlet"),
                    "attribution_type": claim.get("attribution_type"),
                    "quote_span": claim.get("quote_span"),
                    "note": "Reported exclusively by a single outlet; pending multi-source verification."
                })
                # Single source claim gets base weight
                w = ORIGIN_WEIGHTS.get(claim.get("attribution_type"), 0.3)
                claim_support_scores.append(w * 0.5)  # Discounted for single-source
                continue
                
            # Case B: Multi-source claims on same entity & attribute -> Pairwise Comparison
            has_conflict = False
            pairwise_results = []
            
            for i in range(len(claims_in_group)):
                for j in range(i + 1, len(claims_in_group)):
                    ca = claims_in_group[i]
                    cb = claims_in_group[j]
                    if ca.get("outlet") == cb.get("outlet"):
                        continue
                        
                    comp = compare_claim_pair(ca, cb)
                    pairwise_results.append((ca, cb, comp))
                    
                    if comp.get("status") == "CONTRADICTION":
                        has_conflict = True
                        contradictions.append({
                            "entity": ca.get("entity"),
                            "attribute": ca.get("raw_attribute"),
                            "canonical_attribute": ca.get("canonical_attribute"),
                            "claim_a": {
                                "outlet": ca.get("outlet"),
                                "value": ca.get("raw_value"),
                                "attribution": ca.get("attribution_type"),
                                "quote_span": ca.get("quote_span")
                            },
                            "claim_b": {
                                "outlet": cb.get("outlet"),
                                "value": cb.get("raw_value"),
                                "attribution": cb.get("attribution_type"),
                                "quote_span": cb.get("quote_span")
                            },
                            "discrepancy": comp.get("reason")
                        })
                        
            # If no conflict, determine if it's a PR Echo or Independent Corroboration
            if not has_conflict:
                supporting_origins = [c.get("attribution_type") for c in claims_in_group]
                support_score = self.calculate_claim_corroboration(supporting_origins)
                claim_support_scores.append(support_score)
                
                # Check if all sources trace to official statement / secondary citation
                is_pure_pr = all(
                    c.get("attribution_type") in ["official_statement", "secondary_citation"]
                    for c in claims_in_group
                )
                
                evidence_spans = [
                    {"outlet": c.get("outlet"), "value": c.get("raw_value"), "quote_span": c.get("quote_span")}
                    for c in claims_in_group
                ]
                
                if is_pure_pr:
                    pr_echoes.append({
                        "entity": claims_in_group[0].get("entity"),
                        "attribute": claims_in_group[0].get("raw_attribute"),
                        "value": claims_in_group[0].get("raw_value"),
                        "outlets_echoing": list(outlets_involved),
                        "evidence_spans": evidence_spans,
                        "note": "Shared corporate PR statement repeated across multiple newsrooms."
                    })
                else:
                    corroborated_facts.append({
                        "entity": claims_in_group[0].get("entity"),
                        "attribute": claims_in_group[0].get("raw_attribute"),
                        "value": claims_in_group[0].get("raw_value"),
                        "outlets": list(outlets_involved),
                        "evidence_spans": evidence_spans,
                        "support_score": support_score,
                        "note": "Independently verified across separate journalistic investigations."
                    })
            else:
                # Contradiction penalizes the score
                claim_support_scores.append(0.0)
                
        # 4. Compute Bounded Agreement Index (0 to 100%)
        total_unique_claim_groups = len(grouped_claims)
        num_conflicts = len(contradictions)
        
        if total_unique_claim_groups == 0:
            agreement_index = 80.0
        else:
            avg_support = sum(claim_support_scores) / total_unique_claim_groups
            conflict_penalty = (1.5 * num_conflicts) / total_unique_claim_groups
            raw_index = (avg_support - conflict_penalty) * 100.0
            # Strict clamping: 0.0 <= agreement_index <= 100.0
            agreement_index = max(0.0, min(100.0, round(raw_index, 1)))
            
        # 5. Determine Confidence Level
        if len(articles) >= 2 and total_unique_claim_groups >= 3 and num_conflicts == 0:
            confidence = "High Confidence (Corroborated Multi-Source)"
        elif num_conflicts > 0:
            confidence = "Contested (Discrepancies Detected)"
        elif len(pr_echoes) > 0 and len(corroborated_facts) == 0:
            confidence = "Moderate (Corporate PR Statement)"
        else:
            confidence = "Single Source Baseline"
            
        return {
            "agreement_index": agreement_index,
            "confidence_level": confidence,
            "num_articles_analyzed": len(articles),
            "outlets": list(set(a.get("source") for a in articles if a.get("source"))),
            "total_claims_analyzed": total_unique_claim_groups,
            "contradictions_count": num_conflicts,
            "pr_echoes_count": len(pr_echoes),
            "corroborated_facts_count": len(corroborated_facts),
            "single_source_claims_count": len(single_source_claims),
            "contradictions": contradictions,
            "pr_echoes": pr_echoes,
            "corroborated_facts": corroborated_facts,
            "single_source_claims": single_source_claims
        }

contradiction_engine = ContradictionEngine()
