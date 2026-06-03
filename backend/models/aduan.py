"""Aduan/Complaint model — laporan gangguan layanan telekomunikasi."""
from backend.core.tz import WIB
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from backend.core.database import Base
import enum


class AduanKategori(str, enum.Enum):
    GANGGUAN_SINYAL = "gangguan_sinyal"
    GANGGUAN_INTERNET = "gangguan_internet"
    GANGGUAN_BTS = "gangguan_bts"
    GANGGUAN_FIBER = "gangguan_fiber"
    GANGGUAN_LISTRIK = "gangguan_listrik"
    GANGGUAN_LAIN = "gangguan_lain"


class AduanKeparahan(str, enum.Enum):
    RENDAH = "rendah"
    SEDANG = "sedang"
    TINGGI = "tinggi"
    KRITIS = "kritis"


class AduanStatus(str, enum.Enum):
    DITERIMA = "diterima"
    DIPROSES = "diproses"
    DITINDAKLANJUTI = "ditindaklanjuti"
    SELESAI = "selesai"
    DITOLAK = "ditolak"


class AduanSumber(str, enum.Enum):
    MASYARAKAT = "masyarakat"
    INTERNAL = "internal"
    OTOMATIS = "otomatis"


class Aduan(Base):
    __tablename__ = "aduan"

    id = Column(Integer, primary_key=True, index=True)
    nomor = Column(String(30), nullable=True, unique=True)  # ADM-YYYYMM-XXXX

    # Isi aduan
    judul = Column(String(300), nullable=False)
    deskripsi = Column(Text, nullable=True)

    # Pelapor
    pelapor_nama = Column(String(150), nullable=False)
    pelapor_telp = Column(String(30), nullable=True)
    pelapor_email = Column(String(150), nullable=True)

    # Klasifikasi
    kategori = Column(String(50), nullable=False, default=AduanKategori.GANGGUAN_LAIN)
    keparahan = Column(String(20), nullable=False, default=AduanKeparahan.SEDANG)
    sumber = Column(String(20), nullable=False, default=AduanSumber.MASYARAKAT)

    # Lokasi
    lokasi_kabupaten = Column(String(100), nullable=True)
    lokasi_kecamatan = Column(String(100), nullable=True)
    lokasi_kelurahan = Column(String(100), nullable=True)
    lokasi_detail = Column(Text, nullable=True)  # Alamat spesifik

    # Status & penanganan
    status = Column(String(20), nullable=False, default=AduanStatus.DITERIMA)
    penanganan = Column(Text, nullable=True)  # Tindakan yang diambil
    catatan_internal = Column(Text, nullable=True)  # Catatan internal tim

    # Relasi ke event (jika aduan terkait insiden yang sudah ada)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)

    # Timestamps
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(WIB))
    updated_at = Column(DateTime, default=lambda: datetime.now(WIB),
                        onupdate=lambda: datetime.now(WIB))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nomor": self.nomor,
            "judul": self.judul,
            "deskripsi": self.deskripsi,
            "pelapor_nama": self.pelapor_nama,
            "pelapor_telp": self.pelapor_telp,
            "pelapor_email": self.pelapor_email,
            "kategori": self.kategori,
            "keparahan": self.keparahan,
            "sumber": self.sumber,
            "lokasi_kabupaten": self.lokasi_kabupaten,
            "lokasi_kecamatan": self.lokasi_kecamatan,
            "lokasi_kelurahan": self.lokasi_kelurahan,
            "lokasi_detail": self.lokasi_detail,
            "status": self.status,
            "penanganan": self.penanganan,
            "catatan_internal": self.catatan_internal,
            "event_id": self.event_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
