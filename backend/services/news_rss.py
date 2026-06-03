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

# Import LAMPUNG_LOCATIONS, KABUPATEN_ALIASES, KECAMATAN_TO_KABUPATEN from event model
from backend.models.event import LAMPUNG_LOCATIONS, KABUPATEN_ALIASES, KECAMATAN_TO_KABUPATEN
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Rate limit: seconds to wait between Google News RSS requests
GOOGLE_NEWS_RATE_LIMIT_SECONDS = 1

# Fuzzy dedup threshold (word overlap ratio)
FUZZY_DEDUP_THRESHOLD = 0.6

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

# ---------------------------------------------------------------------------
# Negative keywords — filter out irrelevant articles during scraping
# ---------------------------------------------------------------------------
# Maximum age for scraped articles (days). Older articles are skipped.
MAX_ARTICLE_AGE_DAYS = 30  # 1 bulan — realistis untuk monitoring

NEGATIVE_KEYWORDS = [
    # Weather forecasts (not disasters)
    "prakiraan cuaca", "prediksi cuaca", "cuaca hari ini",
    "cuaca perairan", "ramalan cuaca",
    # Road/bridge damage (infrastructure but not telecom)
    "jalan rusak", "jembatan putus", "jalan provinsi", "infrastruktur jalan",
    "jalur mudik", "truk perusak jalan",
    # Crime
    "narkotika", "ekstasi", "pembunuhan", "pencurian motor", "penadah motor",
    "jaringan narkoba", "curanmor", "dilecehkan", "maling di pati",
    # Education
    "putus sekolah", "siswa tka", "sma terbuka", "infak pendidikan",
    # Automotive
    "v-belt", "astra motor",
    # Politics
    "pilpres", "partai politik", "bupati lampung tengah kpk",
    # Non-Lampung national figures
    "jokowi presiden", "ganjar pranowo", "bali telkom",
    # Promotional / non-disruption
    "paket internet", "pilihan paket", "kuota internet", "rekomendasi paket",
    "temani sahur", "live tiktok", "rekor muri",
    # Non-telecom infrastructure
    "bedah rumah", "belanja daerah", "kereta aceh",
    # General non-telecom
    "padi dan jagung", "singkong", "pltu batubara",
]


def _is_negative_match(text: str) -> bool:
    """Return True if text matches any negative keyword pattern."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in NEGATIVE_KEYWORDS)


# ---------------------------------------------------------------------------
# Positive keywords boost — telecom-specific terms that increase relevance
# ---------------------------------------------------------------------------
POSITIVE_KEYWORDS_BOOST = [
    "telkomsel", "indihome", "bts roboh", "kabel putus",
    "gangguan sinyal", "tower roboh", "jaringan internet down",
    "gangguan layanan", "sinyal hilang", "internet mati",
    "pemadaman listrik", "tower mitratel", "frekuensi radio",
]


def _relevance_score(text: str) -> float:
    """Compute a relevance score (0.0–1.0) based on telecom-specific terms."""
    text_lower = text.lower()
    hits = sum(1 for kw in POSITIVE_KEYWORDS_BOOST if kw in text_lower)
    # 0 hits → 0.0, 1 hit → 0.5, 2+ hits → 1.0
    return min(hits * 0.5, 1.0)


# Kabupaten mapping from text (kept for backward compat; KABUPATEN_ALIASES is the
# canonical source of truth, see event.py)
KABUPATEN_KEYWORDS = {
    "bandar lampung": "Bandar Lampung",
    "kota bandar lampung": "Bandar Lampung",
    "bandarlampung": "Bandar Lampung",
    "kota bandarlampung": "Bandar Lampung",
    "balam": "Bandar Lampung",
    "metro": "Metro",
    "lampung selatan": "Lampung Selatan",
    "lam sel": "Lampung Selatan",
    "lamsel": "Lampung Selatan",
    "lampung tengah": "Lampung Tengah",
    "lam teng": "Lampung Tengah",
    "lamteng": "Lampung Tengah",
    "lampung utara": "Lampung Utara",
    "lam utara": "Lampung Utara",
    "lampura": "Lampung Utara",
    "lampung timur": "Lampung Timur",
    "lam tim": "Lampung Timur",
    "lamtim": "Lampung Timur",
    "lampung barat": "Lampung Barat",
    "lam bar": "Lampung Barat",
    "lambar": "Lampung Barat",
    "tanggamus": "Tanggamus",
    "tenggamus": "Tanggamus",
    "tulang bawang barat": "Tulang Bawang Barat",
    "tubabar": "Tulang Bawang Barat",
    "tulang bawang": "Tulang Bawang",
    "way kanan": "Way Kanan",
    "pesawaran": "Pesawaran",
    "pringsewu": "Pringsewu",
    "mesuji": "Mesuji",
    "pesisir barat": "Pesisir Barat",
    "pesbar": "Pesisir Barat",
    "krui": "Pesisir Barat",
    # Kecamatan-level → kabupaten (common city names)
    "kalianda": "Lampung Selatan",
    "kotabumi": "Lampung Utara",
    "sukadana": "Lampung Timur",
    "liwa": "Lampung Barat",
    "menggala": "Tulang Bawang",
    "blambangan umpu": "Way Kanan",
    "gedong tataan": "Pesawaran",
    "gunung sugih": "Lampung Tengah",
    "terbanggi besar": "Lampung Tengah",
    "kota gajah": "Lampung Tengah",
    "natar": "Lampung Selatan",
    "penengahan": "Lampung Selatan",
    "bakauheni": "Lampung Selatan",
    "ketapang": "Lampung Selatan",
    "tanjung bintang": "Lampung Selatan",
    "panjang": "Bandar Lampung",
    "way kandis": "Bandar Lampung",
    "way halim": "Bandar Lampung",
    "tanjung karang": "Bandar Lampung",
    "teluk betung": "Bandar Lampung",
    "kedamaian": "Bandar Lampung",
    "rajabasa": "Lampung Selatan",
    "kota agung": "Tanggamus",
    "kotaagung": "Tanggamus",
}


def _normalize_location_token(text: str) -> str:
    """Collapse whitespace and strip for matching."""
    return re.sub(r"\s+", " ", text).strip()


def detect_kabupaten(text: str) -> Optional[str]:
    """Detect kabupaten/kota from text.

    Strategy (in order):
    1. Exact substring match via KABUPATEN_KEYWORDS (longest key first).
    2. Alias lookup via KABUPATEN_ALIASES from event.py.
    3. Kecamatan reverse-lookup: if a known kecamatan name appears in text,
       return its parent kabupaten.
    4. Fuzzy fallback via difflib.get_close_matches against canonical names.
    """
    if not text:
        return None

    text_lower = text.lower()

    # --- 1. Exact match (longest key first to avoid partial matches) ---
    sorted_keys = sorted(KABUPATEN_KEYWORDS.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in text_lower:
            return KABUPATEN_KEYWORDS[keyword]

    # --- 2. Alias lookup ---
    for alias, kab in KABUPATEN_ALIASES.items():
        if alias in text_lower:
            return kab

    # --- 3. Kecamatan reverse-lookup ---
    # Sort by length descending so "Kotabumi Utara" matches before "Kotabumi"
    sorted_kec = sorted(KECAMATAN_TO_KABUPATEN.keys(), key=len, reverse=True)
    for kec_lower in sorted_kec:
        if kec_lower in text_lower:
            return KECAMATAN_TO_KABUPATEN[kec_lower]

    # --- 4. Fuzzy fallback ---
    # Only try fuzzy matching on short words (3-8 chars) that look like
    # abbreviations, and require a high similarity cutoff to avoid false
    # positives from common Indonesian words like "meter", "radar", etc.
    COMMON_WORDS_TO_SKIP = {
        "the", "dan", "untuk", "dari", "yang", "dalam", "dengan", "pada",
        "ini", "itu", "tidak", "ada", "juga", "akan", "sudah", "lebih",
        "lampung", "indonesia", "radar", "meter", "berita", "news",
        "report", "times", "online", "kompas", "detik", "tempo",
    }
    words = re.findall(r"[a-zA-Z]+", text_lower)
    canonical_names = list(LAMPUNG_LOCATIONS.keys())
    canonical_lower = [n.lower() for n in canonical_names]
    for word in words:
        if len(word) < 3 or len(word) > 8:
            continue
        if word in COMMON_WORDS_TO_SKIP:
            continue
        matches = get_close_matches(word, canonical_lower, n=1, cutoff=0.85)
        if matches:
            # Map back to canonical name
            for cn in canonical_names:
                if cn.lower() == matches[0]:
                    return cn

    return None


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

    Criteria (any one triggers dedup):
    - title word overlap > 60% AND same kabupaten AND within 24 hours
    - same kabupaten AND titles share first 20 characters (prefix match)
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

        existing_title = existing.get("title", "")

        # Fast prefix match: same first 20 characters
        if (new_title.lower()[:20] == existing_title.lower()[:20]
                and len(new_title) >= 10):
            return True

        # Fuzzy title match (Jaccard word overlap)
        similarity = _word_overlap_ratio(new_title, existing_title)
        if similarity > FUZZY_DEDUP_THRESHOLD:
            return True

    return False


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
    0. SKIP berita positif (internet gratis, program pemerintah, promosi)
    1. Gangguan telekom LANGSUNG (sinyal hilang, internet mati, BTS rusak)
    2. Gangguan BTS & Tower
    3. Gangguan Fiber Optik
    4. Gangguan Microwave & Backhaul
    5. Gangguan Internet (kata kunci umum)
    6. Gangguan Listrik (korelasi)
    7. Bencana (natural disasters & severe weather alerts)
    8. DEFAULT: lainnya
    """
    text_lower = text.lower()

    # === SKIP: berita positif yang bukan gangguan ===
    POSITIVE_KEYWORDS = [
        "gratis", "murah", "promosi", "program", "dukung", "dukungan",
        "meningkat", "cepat", "optimal", "berhasil", "peresmian",
        "pembangunan baru", "investasi", "penghargaan", "sosialisasi",
        "pelatihan", "workshop", "seminar", "konferensi",
        "ujiceoba", "uji coba", "testing", "kunjungan", "edukasi",
        "temani", "bermakna", "hiburan",
    ]
    NEGATION_KEYWORDS = ["gangguan", "padam", "rusak", "putus", "hilang", "terganggu"]
    if any(w in text_lower for w in POSITIVE_KEYWORDS):
        if not any(n in text_lower for n in NEGATION_KEYWORDS):
            return "lainnya"

    # === PRIORITAS 1: Gangguan telekom LANGSUNG ===
    TELECOM_DIRECT_KEYWORDS = [
        "sinyal hilang", "sinyal lemah", "sinyal putus",
        "internet mati", "internet gangguan", "internet putus",
        "internet lambat",
        "jaringan putus", "jaringan terganggu",
        "IndiHome gangguan", "Telkom gangguan", "Telkomsel gangguan",
        "Indosat gangguan", "XL gangguan", "provider gangguan",
        "layanan internet lumpuh", "layanan telekomunikasi terganggu",
        "gangguan layanan", "gangguan satelit", "gangguan komunikasi",
        "layanan terganggu", "gangguan jaringan",
        "Telkomsel pulihkan", "berhasil pulihkan site",
        "demo telkomsel", "tuntut perbaikan layanan",
        "gangguan provider",
    ]
    if any(w in text_lower for w in TELECOM_DIRECT_KEYWORDS):
        return "gangguan_telekomunikasi"

    # === PRIORITAS 3: BTS & Tower ===
    BTS_KEYWORDS = [
        "BTS rusak", "BTS mati", "BTS roboh", "BTS terbakar",
        "tower telekomunikasi", "tower seluler", "menara BTS",
        "menara seluler", "tower roboh", "tower jatuh",
        "panel surya BTS", "BTS tower listrik",
        "membakar BTS", "bakar BTS", "membakar bts", "bakar bts",
        "tiang provider", "tiang ilegal provider",
        "tower bts",
    ]
    # Exclude "BTS" in non-telecom contexts (e.g. "Bus Skema BTS")
    if "bus" not in text_lower and any(w in text_lower for w in BTS_KEYWORDS):
        return "gangguan_bts"

    # === PRIORITAS 4: Fiber Optik ===
    FIBER_KEYWORDS = [
        "fiber optik putus", "kabel optik putus", "FO terputus",
        "kabel tembaga putus", "kabel fiber", "serat optik",
        "kabel utama telkom", "kabel optik",
    ]
    if any(w in text_lower for w in FIBER_KEYWORDS):
        return "gangguan_fiber"

    # === PRIORITAS 5: Microwave & Backhaul ===
    MICROWAVE_KEYWORDS = [
        "microwave", "backhaul", "link radio", "point to point",
    ]
    if any(w in text_lower for w in MICROWAVE_KEYWORDS):
        return "gangguan_microwave"

    # === PRIORITAS 6: Internet (kata kunci umum) ===
    INTERNET_KEYWORDS = [
        "internet", "sinyal", "jaringan", "download", "upload",
    ]
    if any(w in text_lower for w in INTERNET_KEYWORDS):
        return "gangguan_internet"

    # === PRIORITAS 7: KORELASI — Listrik padam menyebabkan gangguan telekom ===
    if any(w in text_lower for w in ["listrik", "padam", "blackout", "PLN"]):
        return "gangguan_listrik"

    # === PRIORITAS 8: BENCANA — bencana alam & peringatan cuaca ekstrem ===
    # Bencana alam selalu relevan untuk monitoring infrastruktur
    BENCANA_IMPACT_KEYWORDS = [
        "banjir", "longsor", "gempa", "tsunami", "puting beliung",
        "bencana", "kebakaran", "badai",
    ]
    BENCANA_WEATHER_ALERTS = [
        "cuaca ekstrem", "hujan sangat lebat", "hujan lebat",
        "angin kencang",
    ]
    # Weather forecasts (prakiraan/prediksi cuaca) are NOT disasters
    WEATHER_FORECAST_PATTERNS = ["prakiraan cuaca", "prediksi cuaca"]

    is_bencana = any(b in text_lower for b in BENCANA_IMPACT_KEYWORDS)
    is_weather_alert = any(a in text_lower for a in BENCANA_WEATHER_ALERTS)
    is_forecast = any(f in text_lower for f in WEATHER_FORECAST_PATTERNS)

    if (is_bencana or is_weather_alert) and not is_forecast:
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

            # Filter out irrelevant articles
            if _is_negative_match(full_text):
                continue

            # Skip old articles (>14 days)
            if pub_date and (datetime.now(WIB) - pub_date).days > MAX_ARTICLE_AGE_DAYS:
                continue

            kab = detect_kabupaten(full_text)
            kec = detect_kecamatan(full_text, kab)

            results.append({
                "title": title,
                "description": summary[:500],
                "category": detect_category(full_text),
                "severity": detect_severity(full_text),
                "relevance_score": _relevance_score(full_text),
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

            # Filter out irrelevant articles
            if _is_negative_match(f"{title} {summary}"):
                continue

            # Skip old articles (>14 days)
            if pub_date and (datetime.now(WIB) - pub_date).days > MAX_ARTICLE_AGE_DAYS:
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
                "relevance_score": _relevance_score(f"{title} {summary}"),
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
