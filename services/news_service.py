"""
News service: fetches, AI-filters, and stores news articles about the Mekong River.

Sources: Google News RSS (public, no API key required).
AI enrichment: Gemini API (reuses the project's existing analysis_ai module).
Storage: data/news_cache.json (same pattern as ai_analysis_cache.json).

Environment variables:
  NEWS_CACHE_PATH          Override path to news_cache.json
  NEWS_SYNC_INTERVAL_SECONDS  Seconds between background syncs (default: 1800)
  NEWS_RELEVANCE_THRESHOLD    Minimum AI relevance score to keep (default: 0.70)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
_RELEVANCE_THRESHOLD: float = float(os.environ.get("NEWS_RELEVANCE_THRESHOLD", "0.70"))

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
_sync_running = threading.Event()    # set while a sync is in progress
_force_pending = threading.Event()   # set when a manual force-refresh is queued behind a running sync
_fallback_image_urls: List[str] = []  # Mekong River photos used when articles have no og:image

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
# FALLBACK IMAGES  (Wikimedia Commons photos)
# ──────────────────────────────────────────────

def _load_fallback_images() -> None:
    """Fetch 6 real Mekong River photo URLs from Wikimedia Commons and cache them.

    Results are persisted in news_cache.json so subsequent restarts are instant.
    Uses the Wikimedia Commons search API (no key required).
    """
    global _fallback_image_urls

    # Return immediately if already loaded
    if _fallback_image_urls:
        return

    # Check the on-disk cache first
    with _news_lock:
        cache = _load_cache()
    cached = cache.get("fallback_images", [])
    if len(cached) >= 3:
        _fallback_image_urls = cached
        print(f"[News] Loaded {len(cached)} fallback images from cache.")
        return

    print("[News] Fetching Mekong River fallback images from Wikimedia Commons…")
    urls: List[str] = []
    try:
        # Wikimedia Commons search API — namespace 6 = File
        params = urllib.parse.urlencode({
            "action":      "query",
            "generator":   "search",
            "gsrnamespace": 6,
            "gsrsearch":   "Mekong River photograph landscape",
            "gsrlimit":    20,
            "prop":        "imageinfo",
            "iiprop":      "url|mime",
            "iiurlwidth":  900,
            "format":      "json",
        })
        api_url = f"https://commons.wikimedia.org/w/api.php?{params}"
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "MekongPulse-NewsBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            ii_list = page.get("imageinfo", [])
            if not ii_list:
                continue
            ii = ii_list[0]
            mime = ii.get("mime", "")
            # Only JPEG/PNG photos — skip SVG diagrams, maps, logos
            if mime not in ("image/jpeg", "image/png"):
                continue
            thumb = ii.get("thumburl", "") or ii.get("url", "")
            if thumb and thumb.startswith("http"):
                urls.append(thumb)
            if len(urls) >= 6:
                break
    except Exception as exc:
        print(f"[News] Wikimedia fallback fetch error: {exc}")

    if urls:
        _fallback_image_urls = urls
        with _news_lock:
            cache = _load_cache()
            cache["fallback_images"] = urls
            _save_cache(cache)
        print(f"[News] Loaded {len(urls)} Mekong fallback images from Wikimedia.")
    else:
        print("[News] Could not load fallback images — placeholders will be used.")


def get_fallback_images() -> List[str]:
    """Return the cached list of Mekong River fallback photo URLs."""
    return _fallback_image_urls


# ──────────────────────────────────────────────
# IMAGE FETCHING
# ──────────────────────────────────────────────

def _fetch_og_image(url: str, timeout: int = 8, _depth: int = 0) -> str:
    """Fetch og:image (or twitter:image) from an article URL.

    Google News RSS links (CBMi…) redirect to a Google News JavaScript page,
    not the real article.  We detect that case, extract the true article URL
    from the interstitial HTML, then fetch the real page for the image.
    Recurses at most once (_depth guard).  Returns "" on any failure.
    """
    if _depth > 1:
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            html = resp.read(65536).decode("utf-8", errors="ignore")

        # ── Detect Google News interstitial page ──────────────────────────────
        # When urllib follows the CBMi… redirect it often lands on a Google News
        # SPA page that uses JavaScript for the final hop.  Extract the real URL.
        if _depth == 0 and "news.google.com" in final_url:
            real_url: Optional[str] = None
            for pat in [
                r'"url"\s*:\s*"(https?://(?!news\.google\.com)[^"\\]+)"',
                r'"canonicalUrl"\s*:\s*"(https?://(?!news\.google\.com)[^"\\]+)"',
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            ]:
                m = re.search(pat, html, re.I)
                if m:
                    candidate = m.group(1).replace("\\/", "/").strip()
                    if "news.google.com" not in candidate and candidate.startswith("http"):
                        real_url = candidate
                        break
            if real_url:
                return _fetch_og_image(real_url, timeout=timeout, _depth=_depth + 1)
            return ""

        # ── Extract image meta tag ────────────────────────────────────────────
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\'<>]+)["\']',
            r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]*property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\'<>]+)["\']',
            r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]*name=["\']twitter:image["\']',
            r'<meta[^>]+property=["\']og:image:url["\'][^>]*content=["\']([^"\'<>]+)["\']',
        ]:
            m = re.search(pat, html, re.I | re.S)
            if m:
                img = m.group(1).strip()
                if img.startswith("http"):
                    return img

    except Exception:
        pass
    return ""


# ──────────────────────────────────────────────
# ARTICLE TEXT EXTRACTION
# ──────────────────────────────────────────────

def _fetch_article_text(url: str, timeout: int = 10, _depth: int = 0) -> str:
    """Follow the Google News redirect and extract the main article body text.

    Strategy:
    1. Follow HTTP redirects to the real article page.
    2. If we land on a Google News interstitial, extract the real URL from the
       page HTML and recurse once (same technique as _fetch_og_image).
    3. Strip boilerplate HTML (scripts, nav, footer, ads).
    4. Find the article body via semantic tags (<article>, <main>) or common
       class names, then extract <p> tags with ≥40 chars.
    5. Return up to 8000 characters of clean paragraph text.
    Returns "" on any failure.
    """
    if _depth > 1:
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            html = resp.read(400000).decode("utf-8", errors="ignore")

        # Landed on Google News interstitial — extract the real article URL
        if _depth == 0 and "news.google.com" in final_url:
            real_url: Optional[str] = None
            for pat in [
                r'"url"\s*:\s*"(https?://(?!news\.google\.com)[^"\\]+)"',
                r'"canonicalUrl"\s*:\s*"(https?://(?!news\.google\.com)[^"\\]+)"',
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
            ]:
                m = re.search(pat, html, re.I)
                if m:
                    candidate = m.group(1).replace("\\/", "/").strip()
                    if "news.google.com" not in candidate and candidate.startswith("http"):
                        real_url = candidate
                        break
            if real_url:
                return _fetch_article_text(real_url, timeout=timeout, _depth=_depth + 1)
            return ""

        # Remove tags that never contain article prose
        html = re.sub(
            r"<(script|style|noscript|nav|header|footer|aside|form|iframe|figure"
            r"|figcaption|button|select|option|svg|path)[^>]*>.*?</\1>",
            " ", html, flags=re.DOTALL | re.I,
        )

        # Try to isolate the article body using semantic/common selectors
        body = ""
        for pat in [
            r"<article[^>]*>(.*?)</article>",
            r'<[^>]+\bclass=["\'][^"\']*\b(?:article[_-]?body|post[_-]?body'
            r'|entry[_-]?content|story[_-]?body|article[_-]?content'
            r'|main[_-]?content|td-post-content)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            r"<main[^>]*>(.*?)</main>",
        ]:
            m = re.search(pat, html, re.DOTALL | re.I)
            if m:
                body = m.group(m.lastindex)
                break
        if not body:
            body = html  # fall back to full page

        # Extract <p> tags with meaningful content
        paragraphs: List[str] = []
        for m in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.DOTALL | re.I):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) >= 40:
                paragraphs.append(text)

        if not paragraphs:
            return ""

        content = "\n\n".join(paragraphs)
        return content[:8000]

    except Exception:
        return ""


def _generate_reading_content(article: Dict[str, Any], api_key: str) -> str:
    """Ask Gemini to write a detailed multi-paragraph article about this story."""
    prompt = _CONTENT_ONLY_PROMPT.format(
        title=article.get("title", ""),
        source_name=article.get("source_name", ""),
        description=article.get("content_snippet", "") or article.get("summary", ""),
    )
    result = gemini_generate_safe(api_key, prompt)
    return (result or "").strip()


def fetch_and_cache_content(article_id: str) -> str:
    """Return reading_content for an article, generating/scraping it if missing.

    Called on-demand when a user opens the detail panel.  The result is written
    back to the cache so subsequent opens are instant.
    """
    with _news_lock:
        cache = _load_cache()
    article = next((a for a in cache.get("articles", []) if a["id"] == article_id), None)
    if article is None:
        return ""

    # Already have content — return immediately
    cached = (article.get("reading_content") or "").strip()
    if cached:
        return cached

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # 1. Try scraping the real article page
    scraped = _fetch_article_text(article["article_url"])

    # 2. If scraping failed or too short, generate with Gemini
    if len(scraped) < 200 and api_key:
        content = _generate_reading_content(article, api_key)
    else:
        content = scraped

    if not content:
        return ""

    # Cache the result
    with _news_lock:
        cache = _load_cache()
        for a in cache.get("articles", []):
            if a["id"] == article_id:
                a["reading_content"] = content
                break
        _save_cache(cache)

    return content


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
    """Fetch all RSS feeds in parallel — typically ~3-4× faster than sequential."""
    all_items: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(_RSS_FEEDS), thread_name_prefix="rss") as pool:
        futures = {pool.submit(_fetch_rss_feed, f["url"], f["topic"]): f for f in _RSS_FEEDS}
        for future in as_completed(futures):
            try:
                all_items.extend(future.result())
            except Exception as exc:
                print(f"[News] RSS feed error: {exc}")
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
You are a senior journalist and expert on Southeast Asian river systems and climate events.

Analyse the following news article about the Mekong River region.

Title: {title}
Source: {source_name}
Snippet: {description}
Published: {published_at}

Instructions — return ALL fields below:

1. relevance_score: float 0.0–1.0.
   - 0.9–1.0: DIRECTLY about Mekong River conditions, floods, water levels, hydropower, or related policy.
   - 0.7–0.8: substantially Mekong-related (Mekong delta, Lancang dam releases, basin countries).
   - 0.4–0.6: tangentially related — general Southeast Asia news that mentions Mekong in passing.
   - 0.0–0.3: unrelated (restaurant, brand, tourism, etc.).
2. is_relevant: true if relevance_score >= 0.70, else false.
3. summary: 2–3 plain-English sentences — a concise headline-style overview. No HTML.
4. reading_content: 3–4 rich, informative paragraphs (250–400 words total) written for a reader who wants to understand this story deeply. Cover: what is happening, why it matters for the Mekong ecosystem or communities, relevant background context (hydrology, geopolitics, climate), and any key figures or developments. Separate paragraphs with \\n\\n. No bullet points, no headers, no markdown.
5. country_or_region: comma-separated countries/regions mentioned (e.g. "Thailand, Laos, Cambodia"). Empty string if none.
6. is_flood_related: true if primarily about flooding or flood risk.
7. tags: list of 3–5 short lowercase keyword strings.

Respond ONLY with a single JSON object — no markdown fences, no extra text:
{{"is_relevant": true, "relevance_score": 0.85, "summary": "...", "reading_content": "Paragraph one...\\n\\nParagraph two...\\n\\nParagraph three...", "country_or_region": "Thailand, Laos", "is_flood_related": false, "tags": ["mekong river", "water level", "hydropower"]}}
"""

_CONTENT_ONLY_PROMPT = """\
You are a senior journalist covering Southeast Asian environmental and climate news.

Write 3–4 rich, informative paragraphs (250–400 words) about the following Mekong River news article. \
A reader should be able to fully understand the story without visiting the original article.

Cover: what is happening, why it matters for the Mekong ecosystem or affected communities, \
relevant hydrology or geopolitical background, and any key figures or developments.

Title: {title}
Source: {source_name}
Snippet: {description}

Respond with ONLY the article text — no headlines, no bullet points, no markdown, no JSON. \
Separate paragraphs with a blank line.
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
        "reading_content": "",   # filled by AI only; keyword fallback leaves it blank
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
    # Guard: only one sync at a time
    if _sync_running.is_set():
        with _news_lock:
            cache = _load_cache()
        stored = cache.get("articles", [])
        return {"new_articles": 0, "total_articles": len(stored), "last_sync": cache.get("last_sync")}

    _sync_running.set()
    try:
        return _sync_news_inner(force=force)
    finally:
        _sync_running.clear()


_MEKONG_KEYWORDS = {"mekong", "lancang", "mekong delta", "mekong basin", "mekong river"}


def _needs_ai(raw: Dict[str, Any]) -> bool:
    text = (raw.get("title", "") + " " + raw.get("description", "")).lower()
    return any(kw in text for kw in _MEKONG_KEYWORDS)


def _sync_news_inner(force: bool = False) -> Dict[str, Any]:
    """Inner implementation — called only by sync_news() with _sync_running set.

    When force=True (manual refresh) we process the full current RSS snapshot:
    articles already in the cache are carried through without re-calling AI,
    genuinely new articles are enriched normally.  This ensures the user always
    sees the latest set of articles even when the cache was already populated.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    print(f"[News] Sync started (force={force})…")
    start_ts = time.monotonic()

    # 1. Fetch raw items from all feeds
    raw_items = _fetch_all_feeds()
    print(f"[News] {len(raw_items)} raw items fetched from {len(_RSS_FEEDS)} feeds")

    # 2. Deduplicate within this fetch
    candidates = _deduplicate(raw_items)
    print(f"[News] {len(candidates)} unique candidates after deduplication")

    # 3. Load existing cache as an id→article lookup
    with _news_lock:
        cache = _load_cache()
    existing: Dict[str, Any] = {a["id"]: a for a in cache.get("articles", [])}

    # 4. Decide what to process
    candidates.sort(key=lambda x: _parse_dt(x["published_at"]), reverse=True)

    if force:
        # Manual refresh: work from the full current RSS snapshot (top 30).
        # Articles already cached are carried through (no AI); only new articles
        # go through enrichment.  This avoids showing stale results while still
        # being fast.
        to_process = candidates[:30]
    else:
        # Background sync: only process genuinely new articles.
        new_candidates = [c for c in candidates if _article_id(c["article_url"]) not in existing]
        print(f"[News] {len(new_candidates)} are new (not yet in store)")
        to_process = new_candidates[:12]

    # 5. Split: carry-through (already cached) vs. needs AI enrichment
    carry: List[Dict[str, Any]] = []   # already-cached articles from current RSS snapshot
    ai_queue: List[Dict[str, Any]] = []  # new articles that need enrichment
    skipped = 0

    for raw in to_process:
        aid = _article_id(raw["article_url"])
        if aid in existing:
            # Reuse cached enrichment — no AI needed
            cached_article = existing[aid]
            if float(cached_article.get("relevance_score", 0)) >= _RELEVANCE_THRESHOLD:
                carry.append(cached_article)
        elif _needs_ai(raw):
            ai_queue.append(raw)
        else:
            skipped += 1

    print(f"[News] {len(carry)} carried from cache, {len(ai_queue)} need AI, {skipped} skipped (no keywords)")

    # Fetch og:image for carried articles that still have no image.
    # Runs in parallel; articles that already have an image are skipped.
    def _fill_image(article: Dict[str, Any]) -> Dict[str, Any]:
        if article.get("image_url"):
            return article
        img = _fetch_og_image(article["article_url"])
        if img:
            return {**article, "image_url": img}
        return article

    needs_image = [a for a in carry if not a.get("image_url")]
    if needs_image:
        print(f"[News] Fetching images for {len(needs_image)} cached articles missing images…")
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="img-fetch") as img_pool:
            updated = list(img_pool.map(_fill_image, needs_image))
        # Rebuild carry list with updated image URLs
        updated_by_id = {a["id"]: a for a in updated}
        carry = [updated_by_id.get(a["id"], a) for a in carry]

    # Semaphore caps concurrent Gemini calls to avoid hammering the API.
    _ai_semaphore = threading.Semaphore(5)

    def _enrich_one(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
        """Worker: AI relevance scoring + og:image fetch for one article.
        Returns (raw, enrichment_or_None, image_url).
        Both network calls run inside the thread; the semaphore only gates the AI call.
        """
        with _ai_semaphore:
            enrichment = _enrich_article(raw, api_key)
        image_url = _fetch_og_image(raw["article_url"])
        return raw, enrichment, image_url

    # Run AI + image calls in parallel across articles
    newly_enriched: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="ai-enrich") as pool:
        futures = {pool.submit(_enrich_one, raw): raw for raw in ai_queue}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                raw, enrichment, image_url = future.result()
            except Exception as exc:
                print(f"[News] Enrichment worker error: {exc}")
                continue

            title_short = raw["title"][:65]
            if enrichment is None:
                print(f"[News] [{completed}/{len(ai_queue)}] enrichment failed: {title_short}")
                continue
            if not enrichment.get("is_relevant", False):
                score = enrichment.get("relevance_score", 0)
                print(f"[News] [{completed}/{len(ai_queue)}] not relevant ({score:.2f}): {title_short}")
                continue
            score = float(enrichment.get("relevance_score", 0))
            if score < _RELEVANCE_THRESHOLD:
                print(f"[News] [{completed}/{len(ai_queue)}] below threshold ({score:.2f}): {title_short}")
                continue

            print(f"[News] [{completed}/{len(ai_queue)}] KEPT ({score:.2f}): {title_short}")
            aid = _article_id(raw["article_url"])
            slug = re.sub(r"[^a-z0-9]+", "-", raw["title"].lower())[:80].strip("-")
            newly_enriched.append({
                "id": aid,
                "title": raw["title"],
                "slug": slug,
                "source_name": raw.get("source_name", ""),
                "source_url": raw.get("source_url", ""),
                "article_url": raw["article_url"],
                "canonical_url": raw["article_url"],
                "image_url": image_url,
                "published_at": raw["published_at"],
                "summary": enrichment.get("summary", ""),
                "reading_content": enrichment.get("reading_content", ""),
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

    print(f"[News] {len(newly_enriched)} new articles passed AI filter")

    # 6. Build the merged article list
    #    Priority: newly enriched > carried-through > everything else still in cache
    #    Also purge stored articles that fall below the current relevance threshold.
    rss_ids = {_article_id(c["article_url"]) for c in to_process}
    with _news_lock:
        cache = _load_cache()
        stored = cache.get("articles", [])
        # Keep stored articles above threshold that weren't in this RSS snapshot
        stored_extras = [
            a for a in stored
            if a["id"] not in rss_ids
            and float(a.get("relevance_score", 1.0)) >= _RELEVANCE_THRESHOLD
        ]

        fresh_ids = {a["id"] for a in newly_enriched} | {a["id"] for a in carry}
        merged = newly_enriched + carry + [a for a in stored_extras if a["id"] not in fresh_ids]
        merged.sort(key=lambda x: _parse_dt(x["published_at"]), reverse=True)
        merged = merged[:_MAX_STORE]

        cache["articles"] = merged
        cache["last_sync"] = datetime.now(timezone.utc).isoformat()
        cache["sync_count"] = cache.get("sync_count", 0) + 1
        _save_cache(cache)

    elapsed = round(time.monotonic() - start_ts, 1)
    print(f"[News] Sync complete in {elapsed}s — stored: {len(merged)}, new: {len(newly_enriched)}, carried: {len(carry)}")
    return {
        "new_articles": len(newly_enriched),
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
        "syncing": _sync_running.is_set(),
    }


def is_syncing() -> bool:
    """Return True while a sync is currently running."""
    return _sync_running.is_set()


def sync_news_async() -> None:
    """Start a force sync in a background thread.
    If a sync is already running, queue the force flag so it runs immediately after.
    """
    if _sync_running.is_set():
        # Can't start a second sync; flag it so _sync_loop picks it up right away.
        _force_pending.set()
        return
    t = threading.Thread(target=sync_news, args=(True,), daemon=True, name="news-sync-manual")
    t.start()


# ──────────────────────────────────────────────
# BACKGROUND SYNC THREAD
# ──────────────────────────────────────────────

def _sync_loop() -> None:
    """Daemon thread: run an initial sync after 15 s, then every interval.
    Also drains any force-refresh that was queued while a sync was running.
    """
    time.sleep(15)
    while True:
        try:
            sync_news()
        except Exception as exc:
            print(f"[News] Background sync error: {exc}")
        # If a manual force-refresh was requested while we were busy, run it now.
        if _force_pending.is_set():
            _force_pending.clear()
            try:
                sync_news(force=True)
            except Exception as exc:
                print(f"[News] Queued force sync error: {exc}")
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


def _backfill_images() -> None:
    """One-shot background task: fetch og:image for any cached article that has none.
    Runs once at startup so existing cache entries get images without a full sync.
    """
    with _news_lock:
        cache = _load_cache()
    articles = cache.get("articles", [])
    missing = [a for a in articles if not a.get("image_url")]
    if not missing:
        return
    print(f"[News] Backfilling images for {len(missing)} cached articles…")

    def _fetch_one(article: Dict[str, Any]) -> Tuple[str, str]:
        return article["id"], _fetch_og_image(article["article_url"])

    updated: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="img-backfill") as pool:
        for aid, img in pool.map(_fetch_one, missing):
            if img:
                updated[aid] = img

    if not updated:
        return

    with _news_lock:
        cache = _load_cache()
        for article in cache.get("articles", []):
            if article["id"] in updated:
                article["image_url"] = updated[article["id"]]
        _save_cache(cache)
    print(f"[News] Backfilled images for {len(updated)}/{len(missing)} articles.")


def _backfill_content() -> None:
    """One-shot background task: generate reading_content for cached articles that lack it."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return

    with _news_lock:
        cache = _load_cache()
    missing = [a for a in cache.get("articles", []) if not a.get("reading_content")]
    if not missing:
        return

    print(f"[News] Backfilling reading content for {len(missing)} cached articles…")
    updated: Dict[str, str] = {}
    sem = threading.Semaphore(3)

    def _gen_one(article: Dict[str, Any]) -> Tuple[str, str]:
        prompt = _CONTENT_ONLY_PROMPT.format(
            title=article.get("title", ""),
            source_name=article.get("source_name", ""),
            description=article.get("content_snippet", "") or article.get("summary", ""),
        )
        with sem:
            text = gemini_generate_safe(api_key, prompt)
        return article["id"], (text or "").strip()

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="content-backfill") as pool:
        for aid, content in pool.map(_gen_one, missing):
            if content:
                updated[aid] = content

    if not updated:
        return

    with _news_lock:
        cache = _load_cache()
        for article in cache.get("articles", []):
            if article["id"] in updated:
                article["reading_content"] = updated[article["id"]]
        _save_cache(cache)
    print(f"[News] Backfilled reading content for {len(updated)}/{len(missing)} articles.")


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
    # Patch images for any articles already in cache that have none
    threading.Thread(target=_backfill_images, daemon=True, name="img-backfill").start()
    # Generate reading content for articles that don't have it yet
    threading.Thread(target=_backfill_content, daemon=True, name="content-backfill").start()
    # Load Mekong River fallback photos from Wikimedia Commons
    threading.Thread(target=_load_fallback_images, daemon=True, name="img-fallbacks").start()
