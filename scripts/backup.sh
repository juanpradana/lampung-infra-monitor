#!/bin/bash
# Backup script for Lampung Infrastructure Monitor
set -e

BACKUP_DIR="data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_FILE="data/lampung_monitor.db"

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_DIR/backup_${TIMESTAMP}.db"
    echo "✅ Backup created: $BACKUP_DIR/backup_${TIMESTAMP}.db"

    # Keep only last 30 backups
    ls -t "$BACKUP_DIR"/backup_*.db | tail -n +31 | xargs -r rm
    echo "🧹 Old backups cleaned"
else
    echo "❌ Database not found: $DB_FILE"
    exit 1
fi
