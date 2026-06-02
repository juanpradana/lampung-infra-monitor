"""News RSS fetcher - monitors Google News and local media for infrastructure incidents."""
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
import httpx
import feedparser
from html import unescape
import re

logger = logging.getLogger(__name__)

# Google News RSS queries for Lampung
NEWS_QUERIES = {
    "telekomunikasi": [
        "gangguan internet lampung",
        "BTS rusak lampung",
        "sinyal hilang lampung",
        "jaringan putus lampung",
        "fiber optik lampung",
        "tower roboh lampung",
    ],
    "listrik": [
        "listrik padam lampung",
        "blackout lampung",
        "PLN mati lampung",
        "pemadaman listrik lampung",
    ],
    "bencana": [
        "banjir lampung",
        "longsor lampung",
        "gempa lampung",
        "bencana alam lampung",
        "puting beliung lampung",
        "cuaca ekstrem lampung",
        "tsunami lampung",
    ],
    "infrastruktur": [
        "infrastruktur rusak lampung",
        "jalan putus lampung",
        "jembatan rusak lampung",
    ],
}

# Local media RSS feeds
LOCAL_RSS_FEEDS = {
    "Radar Lampung": "https://radarlampung.co.id/feed",
}

# Keywords to determine severity
SEVERITY_KEYWORDS = {
    "critical": ["tsunami", "gempa besar", "mati total", "blackout", "darurat", "korban jiwa", "roboh"],
    "high": ["banjir bandang", "longsor", "padam", "rusak parah", "putus total", "gangguan besar"],
    "medium": ["gangguan", "putus", "padam", "rusak", "terdampak", "banjir"],
    "low": ["perbaikan", "pemeliharaan", "maintenance", "update"],
}

# Kabupaten mapping from text
KABUPATEN_KEYWORDS = {
    "bandar lampung": "Bandar Lampung",
    "kota bandar lampung": "Bandar Lampung",
    "metro": "Metro",
    "lampung selatan": "Lampung Selatan",
    "lam sel": "Lampung Selatan",
    "lampung tengah": "Lampung Tengah",
    "lam teng": "Lampung Tengah",
    "lampung utara": "Lampung Utara",
    "lam utara": "Lampung Utara",
    "lampung timur": "Lampung Timur",
    "lam tim": "Lampung Timur",
    "lampung barat": "Lampung Barat",
    "lam bar": "Lampung Barat",
    "tanggamus": "Tanggamus",
    "tulang bawang barat": "Tulang Bawang Barat",
    "tulang bawang": "Tulang Bawang",
    "way kanan": "Way Kanan",
    "pesawaran": "Pesawaran",
    "pringsewu": "Pringsewu",
    "mesuji": "Mesuji",
    "pesisir barat": "Pesisir Barat",
    "krui": "Pesisir Barat",
    "kalianda": "Lampung Selatan",
    "kotabumi": "Lampung Utara",
    "sukadana": "Lampung Timur",
    "liwa": "Lampung Barat",
    "menggala": "Tulang Bawang",
    "blambangan umpu": "Way Kanan",
    "gedong tataan": "Pesawaran",
    "pringsewu": "Pringsewu",
    "mesuji": "Mesuji",
}


def clean_html(text: str) -> str:
    """Remove HTML tags and clean text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_source_id(title: str, source: str) -> str:
    """Generate a unique ID for deduplication."""
    content = f"{title}|{source}".lower().strip()
    return hashlib.md5(content.encode()).hexdigest()


def detect_kabupaten(text: str) -> Optional[str]:
    """Detect kabupaten/kota from text."""
    text_lower = text.lower()
    for keyword, kabupaten in KABUPATEN_KEYWORDS.items():
        if keyword in text_lower:
            return kabupaten
    return None


def detect_severity(text: str) -> str:
    """Detect severity from text keywords."""
    text_lower = text.lower()
    for level in ["critical", "high", "medium"]:
        for keyword in SEVERITY_KEYWORDS[level]:
            if keyword in text_lower:
                return level
    return "low"


def detect_category(text: str) -> str:
    """Detect category from text keywords."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["gempa", "tsunami", "longsor", "banjir", "bencana", "puting beliung"]):
        return "bencana"
    if any(w in text_lower for w in ["listrik", "padam", "blackout", "PLN"]):
        return "gangguan_listrik"
    if any(w in text_lower for w in ["internet", "sinyal", "BTS", "tower", "fiber", "jaringan", "telekomunikasi"]):
        return "gangguan_telekomunikasi"
    if any(w in text_lower for w in ["infrastruktur", "jalan", "jembatan"]):
        return "infrastruktur"
    return "lainnya"


async def fetch_google_news(query: str, category: str) -> list[dict]:
    """Fetch articles from Google News RSS."""
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=id&gl=ID&ceid=ID:id"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:10]:
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", ""))
            source_name = entry.get("source", {}).get("title", "Unknown")
            link = entry.get("link", "")

            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            full_text = f"{title} {summary}"
            source_id = generate_source_id(title, source_name)

            # Only include if relevant to Lampung
            if "lampung" not in full_text.lower():
                continue

            results.append({
                "title": title,
                "description": summary[:500],
                "category": detect_category(full_text),
                "severity": detect_severity(full_text),
                "source": f"Google News - {source_name}",
                "source_url": link,
                "source_id": source_id,
                "kabupaten": detect_kabupaten(full_text),
                "province": "Lampung",
                "occurred_at": pub_date,
            })
    except Exception as e:
        logger.error(f"Google News fetch error for '{query}': {e}")

    return results


async def fetch_local_rss(feed_name: str, feed_url: str) -> list[dict]:
    """Fetch articles from local RSS feeds."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:20]:
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", ""))

            # Only infrastructure-related
            relevant_keywords = [
                "gangguan", "padam", "listrik", "internet", "sinyal", "BTS",
                "tower", "banjir", "longsor", "gempa", "bencana", "rusak",
                "putus", "infrastruktur", "telekomunikasi", "jaringan"
            ]

            full_text = f"{title} {summary}".lower()
            if not any(kw.lower() in full_text for kw in relevant_keywords):
                continue

            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            source_id = generate_source_id(title, feed_name)

            results.append({
                "title": title,
                "description": summary[:500],
                "category": detect_category(full_text),
                "severity": detect_severity(full_text),
                "source": feed_name,
                "source_url": entry.get("link", ""),
                "source_id": source_id,
                "kabupaten": detect_kabupaten(full_text),
                "province": "Lampung",
                "occurred_at": pub_date,
            })
    except Exception as e:
        logger.error(f"Local RSS fetch error for '{feed_name}': {e}")

    return results


async def fetch_all_news() -> list[dict]:
    """Fetch news from all configured sources."""
    all_results = []

    # Google News queries
    for category, queries in NEWS_QUERIES.items():
        for query in queries:
            results = await fetch_google_news(query, category)
            all_results.extend(results)

    # Local RSS feeds
    for name, url in LOCAL_RSS_FEEDS.items():
        results = await fetch_local_rss(name, url)
        all_results.extend(results)

    # Deduplicate by source_id
    seen = set()
    unique_results = []
    for r in all_results:
        sid = r.get("source_id", "")
        if sid and sid not in seen:
            seen.add(sid)
            unique_results.append(r)

    logger.info(f"Fetched {len(unique_results)} unique news articles")
    return unique_results
