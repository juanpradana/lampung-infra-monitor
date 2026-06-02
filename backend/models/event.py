"""Event/Incident model - core data model for infrastructure incidents."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Enum
from backend.core.database import Base
import enum


class EventCategory(str, enum.Enum):
    BENCANA = "bencana"
    GANGGUAN_LISTRIK = "gangguan_listrik"
    GANGGUAN_TELEKOMUNIKASI = "gangguan_telekomunikasi"
    INFRASTRUKTUR = "infrastruktur"
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


# Kabupaten/Kota di Provinsi Lampung
LAMPUNG_LOCATIONS = {
    "Bandar Lampung": [
        "Tanjung Karang Pusat", "Tanjung Karang Timur", "Tanjung Karang Barat",
        "Tanjung Senang", "Teluk Betung Selatan", "Teluk Betung Barat",
        "Teluk Betung Utara", "Teluk Betung Timur", "Panjang",
        "Kedamaian", "Rajabasa", "Kemiling", "Labuhan Ratu",
        "Sukarame", "Sukabumi", "Way Halim", "Bumi Waras",
        "Enggal", "Kedaton", "Langkapura", "Tanjung Karang Pusat"
    ],
    "Metro": [
        "Metro Pusat", "Metro Utara", "Metro Barat", "Metro Timur", "Metro Selatan"
    ],
    "Lampung Selatan": [
        "Kalianda", "Rajabasa", "Sidomulyo", "Katibung", "Penengahan",
        "Palas", "Sragi", "Ketapang", "Bakauheni", "Tanjung Bintang"
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
    "Lampung Timur": [
        "Sukadana", "Labuhan Maringgai", "Way Jepara", "Batanghari",
        "Pekalongan", "Sekampung", "Sekampung Udik", "Margatiga",
        "Jabung", "Braja Selebah", "Purbolinggo", "Raman Utara"
    ],
}


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
    reported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON string of original data

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
            "status_display": self.status,
            "severity_display": self.severity,
        }
