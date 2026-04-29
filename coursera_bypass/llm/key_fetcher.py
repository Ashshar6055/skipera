"""
Fetches free LLM API keys from the alistaitsacle/free-llm-api-keys GitHub repo.
Keys are OpenAI-compatible and work with base URL: https://aiapiv2.pekpik.com/v1

Keys are cached locally and refreshed every hour.
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional

import requests
from loguru import logger

RAW_README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md"
BASE_URL = "https://aiapiv2.pekpik.com/v1"
CACHE_DIR = Path.home() / ".coursera-bypass"
CACHE_FILE = CACHE_DIR / "free_keys_cache.json"
CACHE_TTL_SECONDS = 3600  # 1 hour

# Models we want for answering quiz questions (chat-capable models only)
CHAT_MODELS = {
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro",
    "deepseek-chat", "deepseek-reasoner",
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5",
    "flagship-chat", "smart-chat",
    "mistral-medium-latest", "codestral-latest", "devstral-latest",
    "glm-5", "glm-4.5", "glm-4.6",
    "kimi-k2.5",
    "command-a-vision-07-2025", "command-a-reasoning-08-2025",
}

# Priority order for model selection (higher = better for quiz answering)
MODEL_PRIORITY = {
    "gpt-5.4": 100,
    "gpt-5.4-pro": 95,
    "gpt-5.4-mini": 90,
    "claude-opus-4-6": 88,
    "claude-sonnet-4-6": 85,
    "gemini-2.5-pro": 82,
    "deepseek-reasoner": 80,
    "deepseek-chat": 78,
    "command-a-reasoning-08-2025": 75,
    "gemini-2.5-flash": 70,
    "flagship-chat": 65,
    "smart-chat": 60,
    "mistral-medium-latest": 55,
    "kimi-k2.5": 50,
    "glm-5": 45,
    "glm-4.6": 40,
    "glm-4.5": 35,
    "codestral-latest": 30,
    "devstral-latest": 25,
    "gemini-2.5-flash-lite": 20,
    "claude-haiku-4-5": 15,
    "gpt-5.4-nano": 10,
    "command-a-vision-07-2025": 5,
}


def _parse_keys_from_readme(readme_text: str) -> List[Dict]:
    """
    Parses API keys from the README markdown.
    Extracts keys from markdown table rows like:
    | `sk-XXX` | gpt-5.4-mini | 🆕 New | $30 | 20 RPM | 2026-04-23 |
    """
    keys = []
    seen_keys = set()

    # Match table rows with key, model, and other info
    # Pattern: | `sk-XXXX` | model-name | status | budget | rate | expires |
    table_pattern = re.compile(
        r'\|\s*`(sk-[A-Za-z0-9]+)`\s*\|\s*([^\|]+?)\s*\|\s*([^\|]*?)\s*\|\s*\$?(\d+)\s*\|\s*(\d+)\s*RPM\s*\|\s*([^\|]+?)\s*\|'
    )

    for match in table_pattern.finditer(readme_text):
        key = match.group(1).strip()
        model = match.group(2).strip()
        status = match.group(3).strip()
        budget = int(match.group(4).strip())
        rpm = int(match.group(5).strip())
        expires = match.group(6).strip()

        # Skip non-chat models (embeddings, rerank, TTS, DALL-E, etc.)
        if model not in CHAT_MODELS:
            continue

        # Skip duplicate keys
        if key in seen_keys:
            continue
        seen_keys.add(key)

        priority = MODEL_PRIORITY.get(model, 0)

        keys.append({
            "key": key,
            "model": model,
            "status": status,
            "budget": budget,
            "rpm": rpm,
            "expires": expires,
            "priority": priority,
            "base_url": BASE_URL,
        })

    # Sort by priority (highest first)
    keys.sort(key=lambda x: x["priority"], reverse=True)
    return keys


def _fetch_keys_from_github() -> List[Dict]:
    """Fetches the README from GitHub and parses keys."""
    logger.info("Fetching free API keys from GitHub...")
    try:
        response = requests.get(RAW_README_URL, timeout=15)
        response.raise_for_status()
        keys = _parse_keys_from_readme(response.text)
        logger.success(f"Fetched {len(keys)} free API keys from GitHub")
        return keys
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch keys from GitHub: {e}")
        return []


def _load_cache() -> Optional[Dict]:
    """Load cached keys if valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = cache.get("fetched_at", 0)

        # Check if cache is still fresh
        if time.time() - cached_at < CACHE_TTL_SECONDS:
            return cache
        else:
            logger.debug("Key cache expired, will re-fetch")
            return None
    except (json.JSONDecodeError, KeyError):
        return None


def _save_cache(keys: List[Dict]) -> None:
    """Save keys to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "fetched_at": time.time(),
        "keys": keys,
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    logger.debug(f"Cached {len(keys)} keys to {CACHE_FILE}")


def get_free_keys(force_refresh: bool = False) -> List[Dict]:
    """
    Get free API keys, using cache if available.
    
    Returns a list of dicts with: key, model, base_url, priority, etc.
    Sorted by model priority (best models first).
    """
    if not force_refresh:
        cache = _load_cache()
        if cache:
            keys = cache["keys"]
            logger.debug(f"Loaded {len(keys)} free keys from cache")
            return keys

    keys = _fetch_keys_from_github()

    if keys:
        _save_cache(keys)
    else:
        # If fetch failed, try to use stale cache
        if CACHE_FILE.exists():
            try:
                cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                keys = cache.get("keys", [])
                logger.warning(f"Using stale cache with {len(keys)} keys")
            except (json.JSONDecodeError, KeyError):
                pass

    return keys


def get_keys_for_model(model: str = None) -> List[Dict]:
    """
    Get free keys filtered by a specific model.
    If model is None, returns all chat-capable keys sorted by priority.
    """
    keys = get_free_keys()

    if model:
        filtered = [k for k in keys if k["model"] == model]
        if filtered:
            return filtered
        logger.debug(f"No keys found for model '{model}', returning all keys")

    return keys
