"""
News service: fetches, AI-filters, and stores news articles about the Mekong River.

Sources: Google News RSS (public, no API key required).
AI enrichment: Gemini API (reuses the project's existing analysis_ai module).
Storage: data/news_cache.json (same pattern as ai_analysis_cache.json).

Environment variables:
  NEWS_CACHE_PATH          Override path to news_cache.json
  NEWS_SYNC_INTERVAL_SECONDS  Seconds between background syncs (default: 1800)
  NEWS_RELEVANCE_THRESHOLD    Minimum AI relevance score to keep (default: 0.55)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import threading
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.analysis_ai import gemini_generate_safe

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
_NEWS_CACHE_PATH: Path = (
    Path(os.environ["NEWS_CACHE_PATH"])
    if os.environ.get("NEWS_CACHE_PATH")
    else Path(__file__).resolve().parent.parent / "data" / "news_cache.json"
)

_SYNC_INTERVAL_SECONDS: int = int(os.environ.get("NEWS_SYNC_INTERVAL_SECONDS", "1800"))
_MAX_STORE: int = 50          # max articles kept in cache
_MAX_DISPLAY: int = 10        # default limit for API responses
_RELEVANCE_THRESHOLD: float = float(os.environ.get("NEWS_RELEVANCE_THRESHOLD", "0.55"))

# Google News RSS feeds – public, no key required.
_RSS_FEEDS: List[Dict[str, str]] = [
    {
        "url": "https://news.google.com/rss/search?q=Mekong+River&hl=en-US&gl=US&ceid=US:en",
        "topic": "Mekong River",
    },
    {
        "url": "https://news.google.com/rss/search?q=Mekong+river+floods&hl=en-US&gl=US&ceid=US:en",
        "topic": "Mekong River Floods",
    },
    {
        "url": "https://news.google.com/rss/search?q=Mekong+flooding&hl=en-US&gl=US&ceid=US:en",
        "topic": "Mekong Flooding",
    },
    {
        "url": "https://news.google.com/rss/search?q=flood+Mekong+region&hl=en-US&gl=US&ceid=US:en",
        "topic": "Mekong Region Flood",
    },
]

_news_lock = threading.Lock()
_sync_thread: Optional[threading.Thread] = None

# ──────────────────────────────────────────────
# STORAGE HELPERS
# ──────────────────────────────────────────────

def _load_cache() -> Dict[str, Any]:
    try:
        if _NEWS_CACHE_PATH.exists():
            data = json.loads(_NEWS_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"articles": [], "last_sync": None, "sync_count": 0}


def _save_cache(cache: Dict[str, Any]) -> None:
    try:
        _NEWS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _NEWS_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[News] Cache save error: {exc}")


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


# ──────────────────────────────────────────────
# RSS PARSING
# ──────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _fetch_rss_feed(url: str, topic: str) -> List[Dict[str, Any]]:
    """Fetch one RSS feed; return list of raw article dicts. Never raises."""
    items: List[Dict[str, Any]] = []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MekongPulse-NewsBot/1.0 (+https://mekongpulse.local)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_xml = resp.read()

        root = ET.fromstring(raw_xml)
        channel = root.find("channel")
        if channel is None:
            return items

        for item in channel.findall("item"):
            def _t(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            title = _t("title")
            link = _t("link")
            description = _strip_html(_t("description"))
            pub_date_str = _t("pubDate")
            source_el = item.find("source")
            source_name = (source_el.text or "").strip() if source_el is not None else ""
            source_url = source_el.get("url", "") if source_el is not None else ""

            # Parse RFC-2822 pub date
            try:
                published_at = parsedate_to_datetime(pub_date_str).astimezone(timezone.utc).isoformat()
            except Exception:
                published_at = datetime.now(timezone.utc).isoformat()

            if title and link:
                items.append({
                    "title": title,
                    "article_url": link,
                    "description": description[:800],
                    "published_at": published_at,
                    "source_name": source_name,
                    "source_url": source_url,
                    "image_url": "",
                    "topic": topic,
                })
    except Exception as exc:
        print(f"[News] RSS fetch error ({url[:60]}): {exc}")
    return items


def _fetch_all_feeds() -> List[Dict[str, Any]]:
    all_items: List[Dict[str, Any]] = []
    for feed in _RSS_FEEDS:
        items = _fetch_rss_feed(feed["url"], feed["topic"])
        all_items.extend(items)
        time.sleep(0.4)  # be a polite client
    return all_items


# ──────────────────────────────────────────────
# DEDUPLICATION
# ──────────────────────────────────────────────

def _title_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_urls: set = set()
    seen_titles: List[str] = []
    result: List[Dict[str, Any]] = []
    for item in items:
        url = item.get("article_url", "")
        title = item.get("title", "")
        if not url or url in seen_urls:
            continue
        # Near-duplicate title check (>85 % similarity → skip)
        if any(_title_sim(title, t) > 0.85 for t in seen_titles):
            continue
        seen_urls.add(url)
        seen_titles.append(title)
        result.append(item)
    return result


# ──────────────────────────────────────────────
# AI ENRICHMENT
# ──────────────────────────────────────────────

_ENRICHMENT_PROMPT = """\
You are a news analyst specialising in Southeast Asian river systems and climate events.

Analyse the following news article to determine its relevance to the Mekong River, Mekong basin hydrology, or Mekong-related flooding.

Title: {title}
Source: {source_name}
Snippet: {description}
Published: {published_at}

Instructions:
1. relevance_score: float 0.0–1.0.
   - 0.9–1.0: article is DIRECTLY about Mekong River conditions, floods, water levels, hydropower, or related policy.
   - 0.6–0.8: tangentially related (e.g. general Southeast Asia floods that mention Mekong).
   - 0.0–0.5: the word "Mekong" appears but the article is about something unrelated (restaurant, brand, etc.).
2. is_relevant: true if relevance_score >= 0.55, else false.
3. summary: 2–4 plain-English sentences summarising the article. No HTML, no bullet points.
4. country_or_region: comma-separated list of countries/regions explicitly mentioned (e.g. "Thailand, Laos, Cambodia"). Empty string if none.
5. is_flood_related: true if the article is primarily about flooding or flood risk.
6. tags: list of 3–5 short lowercase keyword strings relevant to the article.

Respond ONLY with a JSON object — no markdown fences, no extra text:
{{"is_relevant": true, "relevance_score": 0.85, "summary": "...", "country_or_region": "Thailand, Laos", "is_flood_related": false, "tags": ["mekong river", "water level", "hydropower"]}}
"""


def _keyword_enrich(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keyword-based fallback used when Gemini is unavailable.

    Strategy: articles returned by a Mekong RSS query that contain "mekong" in
    the title score 0.80 (trusted). Those that mention it only in the description
    score 0.65.  Non-Mekong content that slipped through an RSS query scores low
    and is dropped.  Flood signals add a bonus on top.
    """
    title_lower = raw.get("title", "").lower()
    desc_lower  = raw.get("description", "").lower()
    full_text   = title_lower + " " + desc_lower

    flood_words  = {"flood", "flooding", "inundation", "overflow", "floodwater", "deluge", "submerged"}
    mekong_words = {"mekong", "lancang", "mekong delta", "mekong basin", "mekong river"}
    hydro_words  = {"water level", "discharge", "dam", "hydropower", "reservoir", "drought", "salinity"}
    region_words = {"thailand", "laos", "cambodia", "vietnam", "myanmar", "yunnan", "china"}

    in_title = any(w in title_lower for w in mekong_words)
    in_desc  = any(w in desc_lower  for w in mekong_words)
    is_flood = any(w in full_text   for w in flood_words)
    is_hydro = any(w in full_text   for w in hydro_words)

    # Base score from where "mekong" appears
    if in_title:
        score = 0.80
    elif in_desc:
        score = 0.65
    else:
        score = 0.10  # probably off-topic; will be dropped

    # Bonuses
    if is_flood:
        score = min(score + 0.10, 1.0)
    if is_hydro:
        score = min(score + 0.05, 1.0)

    # Infer region tags
    regions = [r.capitalize() for r in region_words if r in full_text]
    tags = ["mekong"]
    if is_flood:
        tags.append("flooding")
    if is_hydro:
        tags.append("hydrology")
    tags += [r.lower() for r in regions[:2]]

    # Build a minimal summary from the snippet
    snippet = raw.get("description", "").strip()
    summary = snippet[:300] if snippet else raw.get("title", "")

    return {
        "is_relevant": score >= _RELEVANCE_THRESHOLD,
        "relevance_score": round(score, 2),
        "summary": summary,
        "country_or_region": ", ".join(regions),
        "is_flood_related": is_flood,
        "tags": list(dict.fromkeys(tags)),  # deduplicate, preserve order
    }


def _enrich_article(raw: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    """
    Try Gemini first; fall back to keyword heuristic if AI is unavailable.
    The keyword fallback is intentionally generous so that clearly-Mekong
    articles are always displayed even when the API is rate-limited.
    """
    prompt = _ENRICHMENT_PROMPT.format(
        title=raw.get("title", ""),
        source_name=raw.get("source_name", ""),
        description=raw.get("description", ""),
        published_at=raw.get("published_at", ""),
    )
    raw_response = gemini_generate_safe(api_key, prompt)

    if raw_response is not None:
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            print(f"[News] AI JSON parse error: {exc}")

    # Gemini was unavailable or returned unparseable output — use keyword fallback
    print(f"[News]   → using keyword fallback for: {raw.get('title', '')[:60]}")
    return _keyword_enrich(raw)


# ──────────────────────────────────────────────
# DATE PARSING HELPER
# ──────────────────────────────────────────────

def _parse_dt(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


# ──────────────────────────────────────────────
# CORE SYNC
# ──────────────────────────────────────────────

def sync_news(force: bool = False) -> Dict[str, Any]:
    """
    Fetch news from all RSS feeds, filter with AI, and persist to disk.
    Idempotent — safe to call any number of times.
    Returns a summary dict with new_articles, total_articles, last_sync.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    print("[News] Sync started…")
    start_ts = time.monotonic()

    # 1. Fetch raw items from all feeds
    raw_items = _fetch_all_feeds()
    print(f"[News] {len(raw_items)} raw items fetched from {len(_RSS_FEEDS)} feeds")

    # 2. Deduplicate within this fetch
    candidates = _deduplicate(raw_items)
    print(f"[News] {len(candidates)} unique candidates after deduplication")

    # 3. Load existing cache to skip already-stored articles
    with _news_lock:
        cache = _load_cache()
    existing_ids = {a["id"] for a in cache.get("articles", [])}

    new_candidates = [c for c in candidates if _article_id(c["article_url"]) not in existing_ids]
    print(f"[News] {len(new_candidates)} are new (not yet in store)")

    # 4. Sort newest-first, process up to 25 candidates
    new_candidates.sort(key=lambda x: _parse_dt(x["published_at"]), reverse=True)
    to_process = new_candidates[:25]

    # 5. Enrich with AI, keep those above threshold
    enriched: List[Dict[str, Any]] = []
    for idx, raw in enumerate(to_process):
        print(f"[News] Enriching {idx + 1}/{len(to_process)}: {raw['title'][:70]}…")
        enrichment = _enrich_article(raw, api_key)
        if enrichment is None:
            continue
        if not enrichment.get("is_relevant", False):
            print(f"[News]   → not relevant (score={enrichment.get('relevance_score', 0):.2f})")
            continue
        score = float(enrichment.get("relevance_score", 0))
        if score < _RELEVANCE_THRESHOLD:
            print(f"[News]   → below threshold ({score:.2f} < {_RELEVANCE_THRESHOLD})")
            continue

        now_iso = datetime.now(timezone.utc).isoformat()
        article_id = _article_id(raw["article_url"])
        slug = re.sub(r"[^a-z0-9]+", "-", raw["title"].lower())[:80].strip("-")

        enriched.append({
            "id": article_id,
            "title": raw["title"],
            "slug": slug,
            "source_name": raw.get("source_name", ""),
            "source_url": raw.get("source_url", ""),
            "article_url": raw["article_url"],
            "canonical_url": raw["article_url"],
            "image_url": raw.get("image_url", ""),
            "published_at": raw["published_at"],
            "summary": enrichment.get("summary", ""),
            "content_snippet": raw.get("description", "")[:500],
            "topic": raw.get("topic", "Mekong"),
            "country_or_region": enrichment.get("country_or_region", ""),
            "is_flood_related": bool(enrichment.get("is_flood_related", False)),
            "relevance_score": round(score, 3),
            "tags": enrichment.get("tags", []),
            "raw_payload": {
                "title": raw["title"],
                "article_url": raw["article_url"],
                "source_name": raw.get("source_name", ""),
                "published_at": raw["published_at"],
            },
            "created_at": now_iso,
            "updated_at": now_iso,
        })

        time.sleep(1.2)  # Gemini rate-limit courtesy delay

    print(f"[News] {len(enriched)} new articles passed AI filter")

    # 6. Merge with stored articles
    with _news_lock:
        cache = _load_cache()
        stored = cache.get("articles", [])
        seen_ids = {a["id"] for a in enriched}
        merged = enriched + [a for a in stored if a["id"] not in seen_ids]
        merged.sort(key=lambda x: _parse_dt(x["published_at"]), reverse=True)
        merged = merged[:_MAX_STORE]

        cache["articles"] = merged
        cache["last_sync"] = datetime.now(timezone.utc).isoformat()
        cache["sync_count"] = cache.get("sync_count", 0) + 1
        _save_cache(cache)

    elapsed = round(time.monotonic() - start_ts, 1)
    print(f"[News] Sync complete in {elapsed}s — stored: {len(merged)}, new: {len(enriched)}")
    return {
        "new_articles": len(enriched),
        "total_articles": len(merged),
        "last_sync": cache["last_sync"],
    }


# ──────────────────────────────────────────────
# READ HELPERS (called by Flask routes)
# ──────────────────────────────────────────────

def get_articles(
    limit: int = _MAX_DISPLAY,
    flood_only: bool = False,
    tag: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with _news_lock:
        cache = _load_cache()
    articles = cache.get("articles", [])
    if flood_only:
        articles = [a for a in articles if a.get("is_flood_related")]
    if tag:
        tag_lower = tag.lower()
        articles = [a for a in articles if any(tag_lower in t for t in a.get("tags", []))]
    return articles[:limit]


def get_article_by_id(article_id: str) -> Optional[Dict[str, Any]]:
    with _news_lock:
        cache = _load_cache()
    for a in cache.get("articles", []):
        if a["id"] == article_id:
            return a
    return None


def get_sync_status() -> Dict[str, Any]:
    with _news_lock:
        cache = _load_cache()
    return {
        "last_sync": cache.get("last_sync"),
        "sync_count": cache.get("sync_count", 0),
        "total_articles": len(cache.get("articles", [])),
    }


# ──────────────────────────────────────────────
# BACKGROUND SYNC THREAD
# ──────────────────────────────────────────────

def _sync_loop() -> None:
    """Daemon thread: run an initial sync after 15 s, then every interval."""
    time.sleep(15)
    while True:
        try:
            sync_news()
        except Exception as exc:
            print(f"[News] Background sync error: {exc}")
        time.sleep(_SYNC_INTERVAL_SECONDS)


def _seed_if_empty() -> None:
    """Populate cache with built-in seed articles if the cache is empty on first run."""
    import subprocess, sys
    with _news_lock:
        cache = _load_cache()
    if cache.get("articles"):
        return  # already has content — skip
    seed_script = Path(__file__).resolve().parent.parent / "scripts" / "seed_news.py"
    if seed_script.exists():
        print("[News] Cache is empty — running seed script…")
        try:
            subprocess.run([sys.executable, str(seed_script)], check=True)
            print("[News] Seed complete.")
        except Exception as exc:
            print(f"[News] Seed script failed: {exc}")


def start_background_sync() -> None:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return
    _seed_if_empty()
    _sync_thread = threading.Thread(
        target=_sync_loop,
        daemon=True,
        name="news-sync",
    )
    _sync_thread.start()
    print(f"[News] Background sync thread started (interval={_SYNC_INTERVAL_SECONDS}s)")
