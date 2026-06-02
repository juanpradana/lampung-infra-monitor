# 🏗️ Lampung Infrastructure Monitor

**Sistem Pemantauan Infrastruktur Digital Provinsi Lampung**

Real-time monitoring gangguan layanan telekomunikasi, bencana alam, dan insiden infrastruktur digital di seluruh kabupaten/kota Provinsi Lampung.

## 📋 Overview

Sistem ini memantau dan mengumpulkan data insiden infrastruktur digital dari berbagai sumber:
- **BMKG** — Gempa bumi & cuaca ekstrem real-time
- **Google News RSS** — Berita gangguan dari seluruh media online
- **Radar Lampung** — Berita lokal terkini
- **Satu Data Lampung** — Data terbuka pemerintah daerah

## ✨ Fitur

### Dashboard
- 📊 Visualisasi insiden per kabupaten/kota
- 🗺️ Filter lokasi (provinsi → kabupaten → kecamatan → kelurahan)
- 📅 Filter waktu (hari, minggu, bulan, custom range)
- 📈 Statistik & trend insiden
- 🔍 Pencarian full-text

### Monitoring Otomatis
- 🚨 **BMKG Alert** — Gempa & cuaca ekstrem (interval 5 menit)
- 📰 **Berita Monitor** — Gangguan infrastruktur (interval 1 jam)
- 🌊 **Bencana Alert** — Bencana alam (interval 2 jam)

### Notifikasi Telegram
- Alert real-time ke bot Telegram
- Filter per lokasi & kategori
- Summary harian

### Manajemen Pengguna
- **Superadmin** — Full akses, kelola user, konfigurasi sistem
- **Operator** — Input/edit data insiden, kelola alert
- **Viewer** — Dashboard read-only

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI |
| Database | SQLite (SQLAlchemy ORM) |
| Frontend | HTML, Tailwind CSS, JavaScript |
| Auth | JWT + bcrypt (RBAC) |
| Scheduler | APScheduler |
| HTTP Client | httpx, feedparser |
| Bot | python-telegram-bot |

## 📦 Instalasi

### Prerequisites
- Python 3.11+
- pip atau uv
- (Opsional) Telegram Bot Token

### Quick Start

```bash
# Clone repository
git clone https://github.com/juanpradana/lampung-infra-monitor.git
cd lampung-infra-monitor

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy & edit config
cp .env.example .env
# Edit .env dengan konfigurasi kamu

# Inisialisasi database & buat superadmin pertama
python3 -m backend.init_db

# Jalankan aplikasi
python3 -m backend.main
```

### Docker

```bash
docker compose up -d
```

Dashboard tersedia di `http://localhost:8032`

## ⚙️ Konfigurasi

Copy `.env.example` ke `.env` dan sesuaikan:

```env
# Aplikasi
APP_NAME=Lampung Infrastructure Monitor
APP_PORT=8032
SECRET_KEY=your-secret-key-change-this

# Database
DATABASE_URL=sqlite:///data/lampung_monitor.db

# Telegram Bot (opsional)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Monitoring
BMKG_CHECK_INTERVAL=300
NEWS_CHECK_INTERVAL=3600
DISASTER_CHECK_INTERVAL=7200

# Lokasi filter (koordinat Lampung)
LAMPUNG_LAT_MIN=-6.5
LAMPUNG_LAT_MAX=-3.5
LAMPUNG_LON_MIN=103.5
LAMPUNG_LON_MAX=106.0
```

## 📁 Struktur Proyek

```
lampung-infra-monitor/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── init_db.py           # Database initialization
│   ├── core/
│   │   ├── config.py        # Settings & env
│   │   ├── database.py      # SQLAlchemy setup
│   │   └── security.py      # JWT & password hashing
│   ├── models/
│   │   ├── user.py          # User model
│   │   ├── event.py         # Event/incident model
│   │   └── alert.py         # Alert & notification model
│   ├── routes/
│   │   ├── auth.py          # Login, register, user management
│   │   ├── events.py        # CRUD events
│   │   ├── dashboard.py     # Dashboard data & stats
│   │   └── admin.py         # Admin routes
│   └── services/
│       ├── bmkg.py          # BMKG data fetcher
│       ├── news_rss.py      # Google News RSS fetcher
│       ├── telegram_bot.py  # Telegram notification service
│       └── scheduler.py     # APScheduler background jobs
├── frontend/
│   ├── static/
│   │   ├── css/style.css    # Custom styles
│   │   └── js/app.js        # Frontend logic
│   └── templates/
│       ├── base.html        # Base template
│       ├── login.html       # Login page
│       ├── dashboard.html   # Main dashboard
│       └── admin.html       # Admin panel
├── scripts/
│   ├── backup.sh            # Database backup script
│   └── seed_data.py         # Seed sample data
├── docs/
│   ├── api.md               # API documentation
│   └── deployment.md        # Deployment guide
├── tests/
│   └── test_api.py          # API tests
├── data/                    # SQLite database (gitignored)
├── .env.example             # Environment template
├── docker-compose.yml       # Docker setup
├── Dockerfile               # Docker image
├── requirements.txt         # Python dependencies
├── Makefile                 # Common commands
└── README.md                # This file
```

## 🔌 API Endpoints

### Auth
| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| POST | `/api/auth/login` | Login | Public |
| POST | `/api/auth/register` | Register | Superadmin |
| GET | `/api/auth/me` | Current user | Authenticated |

### Events
| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/api/events` | List events (filtered) | Viewer+ |
| POST | `/api/events` | Create event | Operator+ |
| PUT | `/api/events/{id}` | Update event | Operator+ |
| DELETE | `/api/events/{id}` | Delete event | Superadmin |

### Dashboard
| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/api/dashboard/stats` | Summary statistics | Viewer+ |
| GET | `/api/dashboard/timeline` | Timeline data | Viewer+ |
| GET | `/api/dashboard/by-location` | Events by location | Viewer+ |
| GET | `/api/dashboard/by-category` | Events by category | Viewer+ |

### Admin
| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| GET | `/api/admin/users` | List users | Superadmin |
| PUT | `/api/admin/users/{id}` | Update user | Superadmin |
| DELETE | `/api/admin/users/{id}` | Delete user | Superadmin |
| POST | `/api/admin/monitoring/trigger` | Manual trigger | Superadmin |

## 📊 Data Model

### Event
| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| title | str | Judul insiden |
| description | str | Detail insiden |
| category | enum | bencana, gangguan_listrik, gangguan_telekomunikasi, infrastruktur, lainnya |
| severity | enum | low, medium, high, critical |
| source | str | Sumber data (BMKG, Google News, manual) |
| source_url | str | URL sumber asli |
| province | str | Provinsi (default: Lampung) |
| kabupaten | str | Kabupaten/Kota |
| kecamatan | str | Kecamatan |
| kelurahan | str | Kelurahan |
| latitude | float | Koordinat lintang |
| longitude | float | Koordinat bujur |
| occurred_at | datetime | Waktu kejadian |
| reported_at | datetime | Waktu dilaporkan |
| resolved_at | datetime | Waktu selesai (nullable) |
| status | enum | active, monitoring, resolved, closed |
| created_by | int | User ID pembuat |

## 🚀 Deployment

Lihat [docs/deployment.md](docs/deployment.md) untuk panduan deployment lengkap.

## 📝 Lisensi

MIT License — untuk penggunaan internal Balai Monitor Spektrum Frekuensi Radio Kelas II Lampung.

## 👥 Kontribusi

Dikembangkan oleh **Farzani RBA** untuk kebutuhan monitoring infrastruktur digital Provinsi Lampung.

---

**Balai Monitor Spektrum Frekuensi Radio Kelas II Lampung**
Tim Kualitas Layanan Infrastruktur Digital
