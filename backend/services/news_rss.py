"""News RSS fetcher - monitors Google News and local media for infrastructure incidents."""
import logging
import hashlib
import time
import asyncio
from backend.core.tz import WIB
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import feedparser
from html import unescape
import re

# Import LAMPUNG_LOCATIONS from event model for kecamatan detection
from backend.models.event import LAMPUNG_LOCATIONS

logger = logging.getLogger(__name__)

# Rate limit: seconds to wait between Google News RSS requests
GOOGLE_NEWS_RATE_LIMIT_SECONDS = 1

# Fuzzy dedup threshold (word overlap ratio)
FUZZY_DEDUP_THRESHOLD = 0.7

NEWS_QUERIES = {
    "gangguan_telekomunikasi": [
        "gangguan telekomunikasi lampung",
        "gangguan jaringan telekomunikasi lampung",
        "layanan telekomunikasi terganggu lampung",
        "Telkom gangguan lampung",
        "IndiHome gangguan lampung",
        "provider gangguan lampung",
    ],
    "gangguan_bts": [
        "BTS mati lampung",
        "BTS rusak lampung",
        "tower telekomunikasi roboh lampung",
        "tower BTS terbakar lampung",
        "BTS tower listrik padam lampung",
    ],
    "gangguan_fiber": [
        "fiber optik putus lampung",
        "kabel optik putus lampung",
        "FO terputus lampung",
        "jaringan kabel putus lampung",
    ],
    "gangguan_microwave": [
        "microwave link gangguan lampung",
        "backhaul gangguan lampung",
        "link radio terganggu lampung",
    ],
    "gangguan_internet": [
        "gangguan internet lampung",
        "internet mati lampung",
        "sinyal hilang lampung",
        "jaringan putus lampung",
        "sinyal lemah lampung",
        "internet lambat lampung",
    ],
    "gangguan_listrik": [
        "listrik padam lampung",
        "blackout lampung",
        "PLN mati lampung",
        "pemadaman listrik lampung",
    ],
    "bencana": [
        "banjir lampung tower BTS",
        "longsor lampung jaringan internet",
        "gempa lampung menara telekomunikasi",
        "puting beliung lampung tower seluler",
        "bencana lampung gangguan internet",
        "banjir lampung gangguan sinyal",
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


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

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


def _word_overlap_ratio(text_a: str, text_b: str) -> float:
    """Compute word overlap ratio between two texts (Jaccard-like).
    Returns a value between 0.0 (no overlap) and 1.0 (identical word sets).
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Fuzzy deduplication
# ---------------------------------------------------------------------------

def fuzzy_dedup(new_item: dict, existing_items: list[dict]) -> bool:
    """Return True if *new_item* is a duplicate of any item in *existing_items*.

    Criteria: title word overlap > threshold AND same kabupaten AND within 24 hours.
    """
    new_title = new_item.get("title", "")
    new_kab = new_item.get("kabupaten")
    new_time = new_item.get("occurred_at")

    for existing in existing_items:
        # Same kabupaten required (both must be non-None and equal)
        if new_kab and existing.get("kabupaten") != new_kab:
            continue
        # Skip if neither has a kabupaten — can't filter
        if not new_kab and not existing.get("kabupaten"):
            continue

        # Within 24 hours required
        ex_time = existing.get("occurred_at")
        if new_time and ex_time:
            delta = abs((new_time - ex_time).total_seconds())
            if delta > 86400:  # 24 hours
                continue
        elif (new_time is None) != (ex_time is None):
            # One has time, other doesn't — still allow word comparison
            pass

        # Fuzzy title match
        similarity = _word_overlap_ratio(new_title, existing.get("title", ""))
        if similarity > FUZZY_DEDUP_THRESHOLD:
            return True

    return False


# ---------------------------------------------------------------------------
# Location detection
# ---------------------------------------------------------------------------

def detect_kabupaten(text: str) -> Optional[str]:
    """Detect kabupaten/kota from text."""
    text_lower = text.lower()
    for keyword, kabupaten in KABUPATEN_KEYWORDS.items():
        if keyword in text_lower:
            return kabupaten
    return None


def detect_kecamatan(text: str, kabupaten: Optional[str]) -> Optional[str]:
    """Detect kecamatan from text given an already-detected kabupaten.

    Looks up the kecamatan list from LAMPUNG_LOCATIONS for the given kabupaten
    and checks if any kecamatan name appears in the text.
    Only called after detect_kabupaten has returned a result.
    """
    if not kabupaten:
        return None

    kecamatan_list = LAMPUNG_LOCATIONS.get(kabupaten, [])
    if not kecamatan_list:
        return None

    text_lower = text.lower()

    # Check longest kecamatan names first to avoid partial-match issues
    # e.g., match "Kotabumi Utara" before "Kotabumi"
    sorted_kecamatan = sorted(kecamatan_list, key=lambda k: len(k), reverse=True)
    for kecamatan in sorted_kecamatan:
        if kecamatan.lower() in text_lower:
            return kecamatan

    return None


# ---------------------------------------------------------------------------
# Severity / Category detection
# ---------------------------------------------------------------------------

def detect_severity(text: str) -> str:
    """Detect severity — berdasarkan dampak gangguan telekom."""
    text_lower = text.lower()
    # Critical: gangguan masif, mati total, darurat
    if any(w in text_lower for w in [
        "mati total", "blackout", "darurat", "korban jiwa", "roboh",
        "terputus total", "lumpuh", "gempa besar", "tsunami"
    ]):
        return "critical"
    # High: gangguan signifikan, banyak terdampak
    if any(w in text_lower for w in [
        "banjir bandang", "longsor", "rusak parah", "putus total",
        "gangguan besar", "terganggu", "terdampak", "padam total",
        "putus", "roboh"
    ]):
        return "high"
    # Medium: gangguan sedang, sebagian area
    if any(w in text_lower for w in [
        "gangguan", "padam", "rusak", "lemah", "lambat", "berkurang"
    ]):
        return "medium"
    return "low"

def detect_category(text: str) -> str:
    """Detect category — fokus gangguan telekomunikasi di Provinsi Lampung.

    Logika prioritas:
    1. Gangguan telekom LANGSUNG (sinyal hilang, internet mati, BTS rusak)
    2. KORELASI gangguan telekom (listrik padam → internet mati, banjir → tower rusak)
    3. SKIP berita positif (internet gratis, program pemerintah, promosi)
    4. Bencana HANYA jika ada kata kunci infrastruktur telekom
    """
    text_lower = text.lower()

    # === SKIP: berita positif yang bukan gangguan ===
    POSITIVE_KEYWORDS = [
        "gratis", "murah", "promosi", "program", "dukung", "dukungan",
        "meningkat", "cepat", "optimal", "berhasil", "peresmian",
        "pembangunan baru", "investasi", "penghargaan", "sosialisasi",
        "pelatihan", "workshop", "seminar", "konferensi",
    ]
    if any(w in text_lower for w in POSITIVE_KEYWORDS):
        # Cek apakah ada kata negatif juga (negasi positif)
        NEGATION_KEYWORDS = ["gangguan", "padam", "rusak", "putus", "hilang", "terganggu"]
        if not any(n in text_lower for n in NEGATION_KEYWORDS):
            return "lainnya"  # Berita positif, bukan gangguan

    # === PRIORITAS 1: Gangguan telekom LANGSUNG ===
    if any(w in text_lower for w in [
        "sinyal hilang", "sinyal lemah", "internet mati", "internet gangguan",
        "internet putus", "jaringan putus", "jaringan terganggu",
        "IndiHome gangguan", "Telkom gangguan", "Telkomsel gangguan",
        "Indosat gangguan", "XL gangguan", "provider gangguan",
        "layanan internet lumpuh", "layanan telekomunikasi terganggu",
    ]):
        return "gangguan_telekomunikasi"

    # === PRIORITAS 2: BTS & Tower ===
    if any(w in text_lower for w in [
        "BTS rusak", "BTS mati", "BTS roboh", "BTS terbakar",
        "tower telekomunikasi", "tower seluler", "menara BTS",
        "menara seluler", "tower roboh", "tower jatuh",
        "panel surya BTS", "BTS tower listrik",
    ]):
        return "gangguan_bts"

    # === PRIORITAS 3: Fiber Optik ===
    if any(w in text_lower for w in [
        "fiber optik putus", "kabel optik putus", "FO terputus",
        "kabel tembaga putus", "kabel fiber", "serat optik",
    ]):
        return "gangguan_fiber"

    # === PRIORITAS 4: Microwave & Backhaul ===
    if any(w in text_lower for w in [
        "microwave", "backhaul", "link radio", "point to point",
    ]):
        return "gangguan_microwave"

    # === PRIORITAS 5: Internet (kata kunci umum) ===
    if any(w in text_lower for w in [
        "internet", "sinyal", "jaringan", "download", "upload",
    ]):
        return "gangguan_internet"

    # === PRIORITAS 6: KORELASI — Listrik padam menyebabkan gangguan telekom ===
    if any(w in text_lower for w in ["listrik", "padam", "blackout", "PLN"]):
        return "gangguan_listrik"

    # === PRIORITAS 7: KORELASI — Bencana yang merusak infrastruktur telekom ===
    # Hanya jika ada kata kunci infrastruktur telekom dalam teks
    BENCANA_KEYWORDS = ["gempa", "tsunami", "longsor", "banjir", "bencana", "puting beliung"]
    TELECOM_INFRA_KEYWORDS = [
        "tower", "BTS", "menara", "kabel", "jaringan", "telekomunikasi",
        "internet", "sinyal", "fiber", "backhaul", "provider",
    ]
    is_bencana = any(b in text_lower for b in BENCANA_KEYWORDS)
    has_telecom_context = any(t in text_lower for t in TELECOM_INFRA_KEYWORDS)
    if is_bencana and has_telecom_context:
        return "bencana"

    # === DEFAULT: lainnya (bukan gangguan telekom) ===
    return "lainnya"


# ---------------------------------------------------------------------------
# RSS fetchers
# ---------------------------------------------------------------------------

async def fetch_google_news(query: str, category: str) -> list[dict]:
    """Fetch articles from Google News RSS."""
    results = []
    try:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=id&gl=ID&ceid=ID:id"
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0), follow_redirects=True) as client:
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
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(WIB)

            full_text = f"{title} {summary}"
            source_id = generate_source_id(title, source_name)

            # Only include if relevant to Lampung
            if "lampung" not in full_text.lower():
                continue

            kab = detect_kabupaten(full_text)
            kec = detect_kecamatan(full_text, kab)

            results.append({
                "title": title,
                "description": summary[:500],
                "category": detect_category(full_text),
                "severity": detect_severity(full_text),
                "source": f"Google News - {source_name}",
                "source_url": link,
                "source_id": source_id,
                "kabupaten": kab,
                "kecamatan": kec,
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
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0), follow_redirects=True) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:20]:
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", ""))

            # Only infrastructure-related
            relevant_keywords = [
                "gangguan", "padam", "listrik", "internet", "sinyal", "BTS",
                "tower", "telekomunikasi", "jaringan", "fiber", "optik",
                "microwave", "backhaul", "IndiHome", "Telkom", "provider",
                "seluler", "menara", "kabel", "banjir", "longsor", "gempa",
                "bencana", "rusak", "putus",
            ]

            full_text = f"{title} {summary}".lower()
            if not any(kw.lower() in full_text for kw in relevant_keywords):
                continue

            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(WIB)

            source_id = generate_source_id(title, feed_name)

            kab = detect_kabupaten(full_text)
            kec = detect_kecamatan(full_text, kab)

            results.append({
                "title": title,
                "description": summary[:500],
                "category": detect_category(full_text),
                "severity": detect_severity(full_text),
                "source": feed_name,
                "source_url": entry.get("link", ""),
                "source_id": source_id,
                "kabupaten": kab,
                "kecamatan": kec,
                "province": "Lampung",
                "occurred_at": pub_date,
            })
    except Exception as e:
        logger.error(f"Local RSS fetch error for '{feed_name}': {e}")

    return results


async def fetch_all_news() -> list[dict]:
    """Fetch news from all configured sources."""
    start_time = time.monotonic()
    all_results = []

    # Google News queries — rate limited (1 second between requests)
    query_count = 0
    for category, queries in NEWS_QUERIES.items():
        for query in queries:
            if query_count > 0:
                await asyncio.sleep(GOOGLE_NEWS_RATE_LIMIT_SECONDS)
            results = await fetch_google_news(query, category)
            all_results.extend(results)
            query_count += 1

    # Local RSS feeds (no rate limit — single feed)
    for name, url in LOCAL_RSS_FEEDS.items():
        results = await fetch_local_rss(name, url)
        all_results.extend(results)

    # Step 1: Exact dedup by source_id
    seen = set()
    source_id_unique = []
    for r in all_results:
        sid = r.get("source_id", "")
        if sid and sid not in seen:
            seen.add(sid)
            source_id_unique.append(r)

    # Step 2: Fuzzy dedup — remove near-duplicates
    # (same kabupaten + similar title + within 24 hours)
    unique_results = []
    for r in source_id_unique:
        if not fuzzy_dedup(r, unique_results):
            unique_results.append(r)

    elapsed = time.monotonic() - start_time
    logger.info(
        f"Fetched {len(unique_results)} unique news articles "
        f"(from {len(all_results)} total, {query_count} Google News queries) "
        f"in {elapsed:.1f}s"
    )
    return unique_results
