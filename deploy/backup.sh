#!/usr/bin/env bash
# Ежедневный бэкап базы KeyPulse (SQLite .backup — безопасно на живой базе).
#
# Установка:
#   sudo cp deploy/backup.sh /opt/keypulse/backup.sh
#   sudo chmod +x /opt/keypulse/backup.sh
#   sudo crontab -e
#   # каждый день в 4:00
#   0 4 * * * /opt/keypulse/backup.sh >> /var/log/keypulse-backup.log 2>&1

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/keypulse}"
DB="${DB:-$APP_DIR/data/keypulse.db}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB" ]; then
    echo "$(date -Iseconds) база не найдена: $DB"
    exit 0
fi

STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$BACKUP_DIR/keypulse-$STAMP.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"

find "$BACKUP_DIR" -name "keypulse-*.db.gz" -mtime "+$KEEP_DAYS" -delete

echo "$(date -Iseconds) бэкап готов: $OUT.gz"
