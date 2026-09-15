"""
groq_client.py - Dynamic, Auto-Adaptive Groq API Client for TechCore.

Features:
1. Dynamic Live Model Discovery: Queries Groq's /models endpoint to automatically
   discover the exact models available right now.
2. In-Memory Model Cache: Caches available models for 15 minutes for maximum speed.
3. Multi-Tier Intelligent Fallback: If a model is deprecated, rate-limited, or unavailable,
   it seamlessly moves to the next live model in real time.
4. Unified Interface: Powers both news summarization and AI assistant chat across local
   and production deployments.
"""

import os
import time
import requests
import json
import re

# Priority ranking for sorting discovered Groq models (best quality & stability first)
MODEL_PRIORITY_ORDER = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
    "allam-2-7b",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

# Static emergency fallback list in case Groq's /models discovery endpoint is unreachable
STATIC_FALLBACK_CHAIN = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
    "groq/compound",
    "allam-2-7b",
]

# Non-chat model keywords to exclude from live chat/summary discovery
EXCLUDE_MODEL_KEYWORDS = [
    "whisper",
    "prompt-guard",
    "safeguard",
    "orpheus",
    "tts",
    "audio",
    "embedding",
    "rerank",
    "vision-preview",
]

_GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
_GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# Global in-memory cache for discovered models
_CACHED_LIVE_MODELS = []
_CACHE_TIMESTAMP = 0
_CACHE_TTL_SECONDS = 900  # 15 minutes


def get_live_groq_models(api_key: str = None) -> list:
    """
    Fetch all active, valid chat/text models from Groq API in real-time.
    Caches results for 15 minutes to eliminate latency.
    """
    global _CACHED_LIVE_MODELS, _CACHE_TIMESTAMP

    now = time.time()
    if _CACHED_LIVE_MODELS and (now - _CACHE_TIMESTAMP < _CACHE_TTL_SECONDS):
        return list(_CACHED_LIVE_MODELS)

    if not api_key:
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")

    if not api_key:
        return list(STATIC_FALLBACK_CHAIN)

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        resp = requests.get(_GROQ_MODELS_URL, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            raw_models = data.get("data", [])
            active_chat_models = []
            for item in raw_models:
                m_id = item.get("id", "")
                is_active = item.get("active", True)
                if not is_active:
                    continue
                # Exclude non-text/safety/audio models
                if any(kw in m_id.lower() for kw in EXCLUDE_MODEL_KEYWORDS):
                    continue
                active_chat_models.append(m_id)

            if active_chat_models:
                # Sort according to our quality priority ranking
                def get_priority(model_id):
                    try:
                        return MODEL_PRIORITY_ORDER.index(model_id)
                    except ValueError:
                        return 999

                sorted_models = sorted(active_chat_models, key=get_priority)
                _CACHED_LIVE_MODELS = sorted_models
                _CACHE_TIMESTAMP = now
                return list(_CACHED_LIVE_MODELS)
    except Exception as e:
        print(f"[GROQ DISCOVERY WARNING] Could not fetch live models: {e}")

    return list(STATIC_FALLBACK_CHAIN)


def call_groq(api_key: str, payload: dict, timeout: int = 25, preferred_model: str = None) -> tuple[str, str]:
    """
    Executes a chat completion request on Groq with auto-adaptive live model fallback.
    
    Args:
        api_key: Groq API Key
        payload: Dict containing messages, temperature, max_tokens, etc.
        timeout: Request timeout in seconds
        preferred_model: Optional specific model requested by user or config

    Returns:
        (response_content, model_used)

    Raises:
        RuntimeError if all available models fail.
    """
    if not api_key:
        raise ValueError("Groq API Key is not set.")

    # 1. Fetch live available models dynamically
    live_models = get_live_groq_models(api_key)

    # 2. Build prioritized candidate list
    candidate_models = []

    # Check preferred_model parameter
    if preferred_model and preferred_model.strip():
        candidate_models.append(preferred_model.strip())

    # Check GROQ_MODEL environment variable
    env_model = os.getenv("GROQ_MODEL")
    if env_model and env_model.strip():
        candidate_models.append(env_model.strip())

    # Add dynamically discovered live models
    candidate_models.extend(live_models)

    # Add static fallback models to ensure zero single-point-of-failure
    candidate_models.extend(STATIC_FALLBACK_CHAIN)

    # Deduplicate while strictly maintaining priority order
    seen = set()
    ordered_models = [m for m in candidate_models if m and m not in seen and not seen.add(m)]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error = "No models available"

    for model in ordered_models:
        cur_payload = dict(payload)
        cur_payload["model"] = model

        for attempt in range(2):
            try:
                response = requests.post(
                    _GROQ_CHAT_URL,
                    headers=headers,
                    json=cur_payload,
                    timeout=timeout,
                )

                # 429 Rate limited -> short backoff or switch model
                if response.status_code == 429:
                    print(f"[GROQ] Rate limited on '{model}'. Switching model or retrying...")
                    time.sleep(1)
                    continue

                # 400 / 404 Model deprecated, not found or invalid -> immediately try next model
                if response.status_code in (400, 404):
                    err_text = response.text.lower()
                    if any(kw in err_text for kw in ("not found", "deprecated", "does not exist", "model_not_found", "invalid model")):
                        print(f"[GROQ] Model '{model}' unavailable/deprecated -> Trying next fallback model.")
                        last_error = f"Model '{model}' deprecated or not found"
                        # Remove from in-memory cache if present
                        global _CACHED_LIVE_MODELS
                        if model in _CACHED_LIVE_MODELS:
                            _CACHED_LIVE_MODELS = [m for m in _CACHED_LIVE_MODELS if m != model]
                        break  # Break inner attempt loop -> move to next candidate model

                response.raise_for_status()

                data = response.json()
                choice = data["choices"][0]["message"]
                content = choice.get("content", "")

                # If content is empty or model only returned reasoning, extract appropriately
                if not content and "reasoning" in choice and choice["reasoning"]:
                    content = choice["reasoning"]

                clean_text = content.strip() if content else ""
                print(f"[GROQ SUCCESS] Handled via model: '{model}'")
                return clean_text, model

            except requests.exceptions.Timeout:
                last_error = f"Timeout on '{model}' (attempt {attempt + 1})"
                print(f"[GROQ] {last_error}")
                if attempt == 0:
                    time.sleep(0.5)

            except requests.exceptions.ConnectionError as e:
                last_error = f"Network connection error on '{model}': {e}"
                print(f"[GROQ] {last_error}")
                if attempt == 0:
                    time.sleep(0.5)

            except Exception as e:
                last_error = f"Error on '{model}' attempt {attempt + 1}: {e}"
                print(f"[GROQ] {last_error}")
                if attempt == 0:
                    time.sleep(0.5)

    raise RuntimeError(f"All Groq models exhausted. Last error: {last_error} | Tried: {ordered_models}")


# Re-export for backward compatibility
_call_groq = call_groq
GROQ_MODEL_FALLBACK_CHAIN = STATIC_FALLBACK_CHAIN

