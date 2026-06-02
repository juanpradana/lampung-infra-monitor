#!/bin/bash
# Setup script for Lampung Infrastructure Monitor
set -e

echo "🔧 Setting up Lampung Infrastructure Monitor..."

# Create data directory
mkdir -p data
chmod 777 data

# Create .env from template if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env created from template - please edit it!"
fi

# Initialize database
echo "🔧 Initializing database..."
.venv/bin/python3 -m backend.init_db 2>/dev/null || python3 -m backend.init_db

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env with your settings"
echo "   2. Run: docker compose up -d"
echo "   3. Open: http://localhost:8032"
echo ""
