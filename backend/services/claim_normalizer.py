"""
claim_normalizer.py - Deterministic Claim & Metric Normalization Layer for TechCore.

Replaces error-prone LLM value comparisons with mathematically sound,
deterministic Python parsing for:
- Currencies ($2B, €1.5M, £500K) -> canonical numbers & currency codes
- Units & multipliers (1M, 1,000,000, 500k, 3.5x)
- Canonical attribute mapping (context window == token limit == memory)
- Qualifier compatibility checks (tier, scope, region)
"""

import re
from typing import Optional, Tuple, Dict, Any

# Canonical dictionary mapping varied journalistic expressions to standard attributes
CANONICAL_ATTRIBUTES: Dict[str, str] = {
    # AI Technical Specs
    "context window": "context_length",
    "context length": "context_length",
    "token limit": "context_length",
    "token window": "context_length",
    "memory window": "context_length",
    "context size": "context_length",
    "parameter count": "model_parameters",
    "model size": "model_parameters",
    "parameters": "model_parameters",
    "weights": "model_parameters",
    "latency": "response_latency",
    "inference speed": "response_latency",
    
    # Financial & Business Metrics
    "valuation": "company_valuation",
    "company valuation": "company_valuation",
    "market cap": "company_valuation",
    "post-money valuation": "company_valuation",
    "pre-money valuation": "company_valuation",
    "funding amount": "round_size",
    "funding": "round_size",
    "investment": "round_size",
    "capital raised": "round_size",
    "round size": "round_size",
    "raised": "round_size",
    "revenue": "annual_revenue",
    "arr": "annual_revenue",
    "annual recurring revenue": "annual_revenue",
    
    # Pricing & Subscriptions
    "price": "subscription_cost",
    "pricing": "subscription_cost",
    "cost": "subscription_cost",
    "subscription fee": "subscription_cost",
    "monthly fee": "subscription_cost",
    "tier price": "subscription_cost",
    "api pricing": "token_cost",
    
    # Corporate & Legal
    "fine amount": "legal_penalty",
    "penalty": "legal_penalty",
    "settlement": "legal_penalty",
    "deal value": "acquisition_price",
    "acquisition price": "acquisition_price",
    "layoffs count": "workforce_reduction",
    "employees cut": "workforce_reduction",
    "job cuts": "workforce_reduction",
    
    # Launch & Dates
    "launch date": "release_date",
    "release date": "release_date",
    "rollout date": "release_date",
    "availability": "release_date",
}

# Currency symbol to ISO code
CURRENCY_MAP = {
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "₹": "INR",
    "inr": "INR",
    "rs": "INR",
    "¥": "JPY",
    "cny": "CNY",
}

# Multiplier mapping
MULTIPLIERS = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "million": 1e6,
    "b": 1e9,
    "billion": 1e9,
    "t": 1e12,
    "trillion": 1e12,
    "cr": 1e7,       # Indian Crore
    "crore": 1e7,
    "lakh": 1e5,
}

def canonicalize_attribute(attr_name: str) -> str:
    """Map natural language attribute variations into canonical keys."""
    if not attr_name:
        return "general_metric"
    cleaned = attr_name.strip().lower()
    cleaned = re.sub(r"[_\-\.]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    # Exact lookup
    if cleaned in CANONICAL_ATTRIBUTES:
        return CANONICAL_ATTRIBUTES[cleaned]
    
    # Substring lookup
    for key, canonical in CANONICAL_ATTRIBUTES.items():
        if key in cleaned:
            return canonical
            
    # Default to snake_case of cleaned string
    return cleaned.replace(" ", "_")

def parse_numeric_with_unit(raw_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Deterministically parses numbers, currencies, multipliers, and units.
    
    Examples:
        "$2.5B" -> (2500000000.0, "USD")
        "1M tokens" -> (1000000.0, "tokens")
        "€500 million" -> (500000000.0, "EUR")
        "$20 / month" -> (20.0, "USD/month")
        "42%" -> (42.0, "%")
    """
    if not raw_str or not isinstance(raw_str, str):
        return None, None
        
    s = raw_str.strip().lower().replace(",", "")
    
    # 1. Detect currency if present
    currency = None
    for sym, code in CURRENCY_MAP.items():
        if sym in s:
            currency = code
            break
            
    # 2. Extract price rate like /month or /year (handling arbitrary spacing like / month)
    is_per_month = bool(re.search(r"/\s*(month|mo)\b|per\s+month\b|a\s+month\b", s))
    is_per_year = bool(re.search(r"/\s*(year|yr)\b|per\s+year\b|annually\b", s))
    
    # 3. Detect percentage
    is_percent = "%" in s or "percent" in s
    
    # 4. Extract base number and optional multiplier
    pattern = r"([0-9]+(?:\.[0-9]+)?)\s*(k|thousand|m|million|b|billion|t|trillion|cr|crore|lakh)?"
    match = re.search(pattern, s)
    if not match:
        return None, None
        
    num_str, mult_str = match.groups()
    try:
        val = float(num_str)
        if mult_str and mult_str.lower() in MULTIPLIERS:
            val *= MULTIPLIERS[mult_str.lower()]
    except (ValueError, TypeError):
        return None, None
        
    # Determine canonical unit
    unit = None
    if currency:
        if is_per_month:
            unit = f"{currency}/month"
        elif is_per_year:
            unit = f"{currency}/year"
        else:
            unit = currency
    elif is_percent:
        unit = "%"
    elif "token" in s:
        unit = "tokens"
    elif "parameter" in s:
        unit = "parameters"
    elif "user" in s:
        unit = "users"
    elif "employee" in s or "job" in s or "worker" in s:
        unit = "people"
    elif "day" in s:
        unit = "days"
    elif "hour" in s:
        unit = "hours"
        
    return val, unit

def normalize_qualifier(qual_str: Optional[str]) -> Optional[str]:
    """Standardize tier, scope, or regional qualifiers."""
    if not qual_str:
        return None
    q = qual_str.strip().lower()
    
    # Tiers
    if any(k in q for k in ["plus", "chatgpt plus"]): return "plus_tier"
    if any(k in q for k in ["pro", "claude pro", "enterprise"]): return "enterprise_tier"
    if any(k in q for k in ["team", "business"]): return "team_tier"
    if any(k in q for k in ["free", "free tier"]): return "free_tier"
    
    # Temporal / Phased Rollout
    if any(k in q for k in ["initially", "first", "preview", "beta", "phased"]): return "initial_rollout"
    if any(k in q for k in ["eventually", "general availability", "all users", "global"]): return "general_availability"
    
    # Numeric bounds
    if any(k in q for k in ["up to", "at most", "maximum"]): return "upper_bound"
    if any(k in q for k in ["at least", "minimum", "more than"]): return "lower_bound"
    if any(k in q for k in ["approximately", "around", "roughly", "about"]): return "estimate"
    
    return q[:30]

def compare_claim_pair(claim_a: Dict[str, Any], claim_b: Dict[str, Any], relative_tolerance: float = 0.08) -> Dict[str, Any]:
    """
    Compares two grounded claims for agreement, contradiction, or scoped difference.
    
    Returns:
        status: 'AGREEMENT' | 'CONTRADICTION' | 'SCOPED_DIFFERENCE' | 'INCOMPARABLE'
        explanation: Detailed reasoning string
    """
    attr_a = claim_a.get("canonical_attribute")
    attr_b = claim_b.get("canonical_attribute")
    
    if attr_a != attr_b:
        return {"status": "INCOMPARABLE", "reason": "Different attributes"}
        
    qual_a = claim_a.get("canonical_qualifier")
    qual_b = claim_b.get("canonical_qualifier")
    
    # If qualifiers are explicitly distinct tiers or scopes, it's a scoped difference (NOT a contradiction)
    # e.g., $20/month for Plus vs $200/month for Enterprise
    if qual_a and qual_b and qual_a != qual_b:
        return {
            "status": "SCOPED_DIFFERENCE",
            "reason": f"Scoped context distinction ({qual_a} vs. {qual_b}). Not a conflict."
        }
        
    val_a = claim_a.get("normalized_value")
    val_b = claim_b.get("normalized_value")
    unit_a = claim_a.get("unit")
    unit_b = claim_b.get("unit")
    
    # Both are numeric
    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        # Check unit consistency
        if unit_a and unit_b and unit_a != unit_b:
            return {
                "status": "SCOPED_DIFFERENCE",
                "reason": f"Different units measured ({unit_a} vs. {unit_b})"
            }
            
        # Tolerance check
        max_val = max(abs(val_a), abs(val_b))
        diff = abs(val_a - val_b)
        
        # Exact match or within relative tolerance (e.g. 8%)
        if max_val == 0 or (diff / max_val) <= relative_tolerance:
            return {
                "status": "AGREEMENT",
                "reason": f"Values align within {int(relative_tolerance * 100)}% tolerance ({val_a} vs {val_b})"
            }
        else:
            return {
                "status": "CONTRADICTION",
                "reason": f"Direct numerical discrepancy: {claim_a.get('outlet')} reports {claim_a.get('raw_value')} while {claim_b.get('outlet')} reports {claim_b.get('raw_value')}"
            }
            
    # Textual claims comparison
    text_a = str(claim_a.get("raw_value", "")).strip().lower()
    text_b = str(claim_b.get("raw_value", "")).strip().lower()
    
    if text_a == text_b:
        return {"status": "AGREEMENT", "reason": "Exact textual match"}
        
    return {
        "status": "AGREEMENT" if (text_a in text_b or text_b in text_a) else "SCOPED_DIFFERENCE",
        "reason": f"Textual report variation: '{text_a}' vs '{text_b}'"
    }
