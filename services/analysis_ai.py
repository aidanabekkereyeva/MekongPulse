from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

# Models tried in order; if one is rate-limited the next is attempted.
_GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]

_CACHE_PATH = (
    Path(os.environ.get("ANALYSIS_AI_CACHE_PATH", ""))
    if os.environ.get("ANALYSIS_AI_CACHE_PATH")
    else Path(__file__).resolve().parent.parent / "data" / "ai_analysis_cache.json"
)

_AI_RESPONSE_CACHE: Dict[str, str] = {}


def _cache_key(api_key: str, prompt: str) -> str:
    return hashlib.sha256(f"{api_key}:{prompt}".encode("utf-8")).hexdigest()


def _load_ai_cache() -> Dict[str, str]:
    try:
        if _CACHE_PATH.exists():
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_ai_cache(cache: Dict[str, str]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _normalise_md(text: str) -> str:
    """Ensures markdown bullets render correctly if the model omits blank lines."""
    return re.sub(r"(?<!\n)\n([-*]|\d+\.) ", r"\n\n\1 ", text)


# Load cache on module import
_AI_RESPONSE_CACHE = _load_ai_cache()


def gemini_available() -> bool:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(api_key and api_key not in ("your_real_key_here", "paste-your-key-here", ""))


def _gemini_generate(api_key: str, prompt: str) -> str:
    """
    Call Gemini with disk caching, model fallback, and retry on quota exhaustion.
    """
    from google import genai

    cache_key = _cache_key(api_key, prompt)
    if cache_key in _AI_RESPONSE_CACHE:
        return _AI_RESPONSE_CACHE[cache_key]

    client = genai.Client(api_key=api_key)
    last_exc: Optional[Exception] = None

    for model in _GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text = _normalise_md((response.text or "").strip())
            _AI_RESPONSE_CACHE[cache_key] = text
            _save_ai_cache(_AI_RESPONSE_CACHE)
            return text
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                last_exc = exc
                time.sleep(2)
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("Gemini generation failed across all models.")


def gemini_generate_safe(api_key: str, prompt: str) -> Optional[str]:
    """
    Call _gemini_generate and return None on ANY failure instead of raising.
    Callers can check for None and serve a fallback response.
    """
    if not api_key or api_key in ("your_real_key_here", "paste-your-key-here"):
        print("[AI] Gemini skipped: API key missing or placeholder.")
        return None
    try:
        result = _gemini_generate(api_key, prompt)
        print("[AI] Gemini succeeded.")
        return result
    except Exception as exc:
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            print(f"[AI] Gemini quota/rate-limit exceeded — using fallback. ({msg[:120]})")
        elif "400" in msg or "INVALID_ARGUMENT" in msg or "expired" in msg.lower():
            print(f"[AI] Gemini API key invalid/expired — using fallback. ({msg[:120]})")
        elif "404" in msg or "NOT_FOUND" in msg:
            print(f"[AI] Gemini model not found — using fallback. ({msg[:120]})")
        else:
            print(f"[AI] Gemini failed ({type(exc).__name__}) — using fallback. ({msg[:120]})")
        return None


def generate_ai_summary(prompt: str, fallback: str = "") -> str:
    """
    Public helper — reads API key from environment, calls Gemini,
    returns markdown-rendered HTML. Falls back to `fallback` on any failure.
    """
    import markdown as md_lib

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key in ("your_real_key_here", "paste-your-key-here"):
        return fallback

    try:
        raw = _gemini_generate(api_key, prompt)
        return md_lib.markdown(raw, extensions=["nl2br"])
    except Exception:
        return fallback
