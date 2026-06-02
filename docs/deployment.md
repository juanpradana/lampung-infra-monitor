# Deployment Guide

## 🖥️ Local Development

```bash
# 1. Clone & setup
git clone https://github.com/juanpradana/lampung-infra-monitor.git
cd lampung-infra-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your settings

# 3. Initialize database
python3 -m backend.init_db

# 4. Run
python3 -m backend.main
# Access: http://localhost:8000
```

## 🐳 Docker

```bash
# Build & run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 🌐 Production (VPS)

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv nginx -y

# Install certbot for SSL
sudo apt install certbot python3-certbot-nginx -y
```

### 2. Application Setup
```bash
# Clone to /opt
cd /opt
git clone https://github.com/juanpradana/lampung-infra-monitor.git
cd lampung-infra-monitor

# Setup venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Edit with production values

# Generate secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Initialize database
python3 -m backend.init_db
```

### 3. Systemd Service
```bash
sudo tee /etc/systemd/system/lampung-monitor.service << EOF
[Unit]
Description=Lampung Infrastructure Monitor
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/lampung-infra-monitor
Environment=PATH=/opt/lampung-infra-monitor/.venv/bin
ExecStart=/opt/lampung-infra-monitor/.venv/bin/python -m backend.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable lampung-monitor
sudo systemctl start lampung-monitor
```

### 4. Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name monitor.balmon-lampung.go.id;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5. SSL
```bash
sudo certbot --nginx -d monitor.balmon-lampung.go.id
```

## 📱 Telegram Bot Setup

### 1. Buat Bot
1. Buka Telegram, cari @BotFather
2. Kirim `/newbot`
3. Ikuti instruksi, simpan token

### 2. Dapatkan Chat ID
1. Kirim pesan ke bot kamu
2. Buka `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Cari `chat.id` di response

### 3. Konfigurasi
Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

## 🔄 Backup

```bash
# Manual backup
bash scripts/backup.sh

# Cron backup (daily at 2 AM)
echo "0 2 * * * /opt/lampung-infra-monitor/scripts/backup.sh" | crontab -
```

## 📊 Monitoring

```bash
# Check service status
sudo systemctl status lampung-monitor

# View logs
sudo journalctl -u lampung-monitor -f

# Check database size
ls -lh data/lampung_monitor.db
```
