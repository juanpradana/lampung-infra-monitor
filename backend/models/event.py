"""Event/Incident model - core data model for infrastructure incidents."""
from backend.core.tz import WIB
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Enum
from backend.core.database import Base
import enum


class EventCategory(str, enum.Enum):
    GANGGUAN_TELEKOMUNIKASI = "gangguan_telekomunikasi"
    GANGGUAN_BTS = "gangguan_bts"
    GANGGUAN_FIBER = "gangguan_fiber"
    GANGGUAN_MICROWAVE = "gangguan_microwave"
    GANGGUAN_INTERNET = "gangguan_internet"
    GANGGUAN_LISTRIK = "gangguan_listrik"
    BENCANA = "bencana"
    CUACA_EKSTREM = "cuaca_ekstrem"
    LAINNYA = "lainnya"


class EventSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(str, enum.Enum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class VerifiedStatus(str, enum.Enum):
    PENDING = "pending"       # Menunggu verifikasi
    CONFIRMED = "confirmed"   # Dipastikan gangguan telekom
    REJECTED = "rejected"     # Bukan gangguan telekom


# Kabupaten/Kota di Provinsi Lampung
# Canonical names (keys) + kecamatan lists (values)
LAMPUNG_LOCATIONS = {
    "Bandar Lampung": [
        "Tanjung Karang Pusat", "Tanjung Karang Timur", "Tanjung Karang Barat",
        "Tanjung Senang", "Teluk Betung Selatan", "Teluk Betung Barat",
        "Teluk Betung Utara", "Teluk Betung Timur", "Panjang",
        "Kedamaian", "Rajabasa", "Kemiling", "Labuhan Ratu",
        "Sukarame", "Sukabumi", "Way Halim", "Bumi Waras",
        "Enggal", "Kedaton", "Langkapura", "Way Kandis",
    ],
    "Metro": [
        "Metro Pusat", "Metro Utara", "Metro Barat", "Metro Timur", "Metro Selatan"
    ],
    "Lampung Selatan": [
        "Kalianda", "Rajabasa", "Sidomulyo", "Katibung", "Penengahan",
        "Palas", "Sragi", "Ketapang", "Bakauheni", "Tanjung Bintang", "Natar"
    ],
    "Lampung Tengah": [
        "Gunung Sugih", "Terbanggi Besar", "Kota Gajah", "Seputih Raman",
        "Seputih Banyak", "Seputih Mataram", "Rumbia", "Bangunrejo",
        "Kalirejo", "Pubian", "Padang Ratu", "Selagai Lingga"
    ],
    "Lampung Utara": [
        "Kotabumi", "Kotabumi Utara", "Kotabumi Selatan", "Abung Timur",
        "Abung Barat", "Abung Selatan", "Abung Tengah", "Abung Tinggi",
        "Abung Semuli", "Sungkai Selatan", "Sungkai Utara", "Bunga Mayang"
    ],
    "Lampung Timur": [
        "Sukadana", "Labuhan Maringgai", "Jabung", "Pekalongan",
        "Batanghari", "Way Jepara", "Braja Selebah", "Purbolinggo",
        "Raman Utara", "Metro Kibang", "Marga Tiga", "Sekampung"
    ],
    "Lampung Barat": [
        "Liwa", "Balik Bukit", "Sumber Jaya", "Belalau",
        "Way Tenong", "Sukau", "Kebun Tebu", "Air Hitam",
        "Batu Brak", "Pagar Dewa", "Lumbok Seminung", "Bandar Negeri Suoh"
    ],
    "Tanggamus": [
        "Kota Agung", "Talang Padang", "Pugung", "Pulau Panggung",
        "Cukuh Balak", "Wonosobo", "Semaka", "Bandar Negeri Semuong",
        "Air Naningan", "Ulu Belu", "Sumberejo", "Gisting"
    ],
    "Tulang Bawang": [
        "Menggala", "Banjar Agung", "Banjar Margo", "Banjar Baru",
        "Gedung Aji", "Penawar Tama", "Rawa Jitu Selatan",
        "Rawa Jitu Timur", "Dente Teladas", "Meraksa Aji"
    ],
    "Tulang Bawang Barat": [
        "Tulang Bawang Tengah", "Tumijajar", "Tulang Bawang Udik",
        "Gunung Terang", "Gunung Agung", "Way Kenanga",
        "Lambu Kibang", "Pagar Dewa"
    ],
    "Way Kanan": [
        "Blambangan Umpu", "Baradatu", "Bahuga", "Pakuan Ratu",
        "Negeri Agung", "Way Tuba", "Rebang Tangkas", "Kasui",
        "Negara Batin", "Buay Bahuga", "Bumi Agung"
    ],
    "Pesawaran": [
        "Gedong Tataan", "Padang Cermin", "Punduh Pidada",
        "Kedondong", "Way Ratai", "Tegineneng", "Negeri Katon",
        "Marga Punduh", "Teluk Pandan"
    ],
    "Pringsewu": [
        "Pringsewu", "Gading Rejo", "Ambarawa", "Pardasuka",
        "Pagelaran", "Sukoharjo", "Banyumas", "Adiluwih"
    ],
    "Mesuji": [
        "Mesuji", "Mesuji Timur", "Mesuji Barat", "Rawa Jitu Utara",
        "Way Serdang", "Simpang Pematang", "Panca Jaya", "Tanju Raya"
    ],
    "Pesisir Barat": [
        "Krui", "Pesisir Tengah", "Pesisir Selatan", "Pesisir Utara",
        "Karya Penggawa", "Way Krui", "Lemong", "Bengkunat",
        "Bengkunat Belimbing", "Ngambur", "Ngaras", "Bangkunat"
    ],
}

# Common abbreviations/aliases → canonical kabupaten name
# Used by detect_kabupaten() for quick lookup before fuzzy fallback
KABUPATEN_ALIASES = {
    # Bandar Lampung variants
    "bandar lampung": "Bandar Lampung",
    "kota bandar lampung": "Bandar Lampung",
    "kota bandarlampung": "Bandar Lampung",
    "bandarlampung": "Bandar Lampung",
    "balam": "Bandar Lampung",
    "bd Lampung": "Bandar Lampung",
    # Metro
    "metro": "Metro",
    # Lampung Selatan
    "lampung selatan": "Lampung Selatan",
    "lamsel": "Lampung Selatan",
    "lam sel": "Lampung Selatan",
    "lam-sel": "Lampung Selatan",
    "lampsel": "Lampung Selatan",
    # Lampung Tengah
    "lampung tengah": "Lampung Tengah",
    "lamteng": "Lampung Tengah",
    "lam teng": "Lampung Tengah",
    "lam-teng": "Lampung Tengah",
    "lampteng": "Lampung Tengah",
    # Lampung Utara
    "lampung utara": "Lampung Utara",
    "lamut": "Lampung Utara",
    "lam utara": "Lampung Utara",
    "lam-utara": "Lampung Utara",
    "lampura": "Lampung Utara",
    "lamp utara": "Lampung Utara",
    # Lampung Timur
    "lampung timur": "Lampung Timur",
    "lamtim": "Lampung Timur",
    "lam tim": "Lampung Timur",
    "lam-tim": "Lampung Timur",
    "lamptim": "Lampung Timur",
    # Lampung Barat
    "lampung barat": "Lampung Barat",
    "lambar": "Lampung Barat",
    "lam bar": "Lampung Barat",
    "lam-bar": "Lampung Barat",
    "lampbar": "Lampung Barat",
    # Tanggamus
    "tanggamus": "Tanggamus",
    "tenggamus": "Tanggamus",  # common misspelling
    # Tulang Bawang
    "tulang bawang": "Tulang Bawang",
    # Tulang Bawang Barat
    "tulang bawang barat": "Tulang Bawang Barat",
    "tubabar": "Tulang Bawang Barat",
    # Way Kanan
    "way kanan": "Way Kanan",
    # Pesawaran
    "pesawaran": "Pesawaran",
    # Pringsewu
    "pringsewu": "Pringsewu",
    # Mesuji
    "mesuji": "Mesuji",
    # Pesisir Barat
    "pesisir barat": "Pesisir Barat",
    "pesbar": "Pesisir Barat",
    "krui": "Pesisir Barat",
}

# Kecamatan → Kabupaten reverse mapping (for detecting kabupaten from kecamatan names)
KECAMATAN_TO_KABUPATEN = {}
for _kab, _kecs in LAMPUNG_LOCATIONS.items():
    for _kec in _kecs:
        KECAMATAN_TO_KABUPATEN[_kec.lower()] = _kab


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    category = Column(String(50), nullable=False, default=EventCategory.LAINNYA)
    severity = Column(String(20), nullable=False, default=EventSeverity.MEDIUM)
    status = Column(String(20), nullable=False, default=EventStatus.ACTIVE)

    # Source
    source = Column(String(100), nullable=True)  # BMKG, Google News, Manual, etc.
    source_url = Column(String(500), nullable=True)
    source_id = Column(String(200), nullable=True, unique=True)  # Dedup key

    # Location
    province = Column(String(50), default="Lampung")
    kabupaten = Column(String(100), nullable=True)
    kecamatan = Column(String(100), nullable=True)
    kelurahan = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Timestamps
    occurred_at = Column(DateTime, nullable=True)
    reported_at = Column(DateTime, default=lambda: datetime.now(WIB))
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(WIB))
    updated_at = Column(DateTime, default=lambda: datetime.now(WIB), onupdate=lambda: datetime.now(WIB))

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON string of original data

    # Verifikasi — apakah benar gangguan telekom?
    verified_status = Column(String(20), nullable=False, default=VerifiedStatus.PENDING)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verifier_notes = Column(Text, nullable=True)  # Catatan verifikator

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "source": self.source,
            "source_url": self.source_url,
            "province": self.province,
            "kabupaten": self.kabupaten,
            "kecamatan": self.kecamatan,
            "kelurahan": self.kelurahan,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_status": self.verified_status,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verifier_notes": self.verifier_notes,
            "status_display": self.status,
            "severity_display": self.severity,
        }
