"""
dedup/config.py - Central Configuration for Story Clustering & Deduplication Pipeline.

All thresholds, weights, window intervals, and model identifiers are declared here
as a typed dataclass so they can be tuned without modifying algorithm code.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import os

@dataclass
class ClusterConfig:
    # --- Layer 1: Copy Detection (MinHash LSH) ---
    minhash_num_perm: int = 128
    minhash_threshold: float = 0.70
    shingle_k_full: int = 5
    shingle_k_snippet: int = 3
    snippet_word_threshold: int = 80

    # --- Layer 2: Same-Event Clustering ---
    # Similarity Thresholds (Default guesses to be validated by eval/evaluate.py sweep)
    t_low: float = 0.50
    t_high: float = 0.70

    # Linear combination weights (Must sum to 1.0)
    w_cos: float = 0.60
    w_ent: float = 0.25
    w_time: float = 0.15

    # Rolling window for clustering in RAM
    window_hours: int = 72
    time_decay_half_life_hours: float = 24.0

    # Models
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    spacy_model_name: str = "en_core_web_sm"

    # Entities: Target labels from spaCy
    target_entity_labels: List[str] = field(default_factory=lambda: ["ORG", "PRODUCT", "PERSON"])

    # Regex/Alias list for novel tech entities small spaCy models miss
    entity_aliases: List[str] = field(default_factory=lambda: [
        "GPT-5", "GPT-4o", "GPT-4", "ChatGPT", "Claude 3.5", "Claude 3", "Claude",
        "Gemini 1.5", "Gemini", "Llama 3.3", "Llama 3.1", "Llama 3", "Llama",
        "DeepSeek", "Mistral", "Qwen", "Grok", "Sora", "Cybercab", "Robotaxi",
        "Starlink", "Waymo", "Anduril", "Anthropic", "OpenAI", "xAI", "Perplexity"
    ])

    # --- Layer 3: Borderline LLM Verification ---
    groq_model: str = "llama-3.1-8b-instant"
    groq_temperature: float = 0.0
    groq_timeout_seconds: int = 8

    # --- Feature Flag ---
    dedup_mode: str = field(default_factory=lambda: os.getenv("DEDUP_MODE", "cluster"))

    @property
    def lsh_threshold(self) -> float:
        return self.minhash_threshold

    @property
    def snippet_threshold_words(self) -> int:
        return self.snippet_word_threshold

    def validate(self) -> None:
        """Validate configuration sanity."""
        if not (0.0 <= self.t_low <= self.t_high <= 1.0):
            raise ValueError(f"Invalid thresholds: 0 <= {self.t_low} <= {self.t_high} <= 1")
        total_w = self.w_cos + self.w_ent + self.w_time
        if abs(total_w - 1.0) > 1e-4:
            raise ValueError(f"Weights must sum to 1.0; got {total_w}")

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

# Default singleton instance
DEFAULT_CONFIG = ClusterConfig()
DEFAULT_CONFIG.validate()
