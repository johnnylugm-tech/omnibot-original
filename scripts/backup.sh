#!/bin/bash
# Database Backup Script - Phase 3
set -e

BACKUP_DIR="/Users/johnny/Documents/omnibot/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/omnibot_backup_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

echo "Starting database backup..."
PGPASSWORD=password pg_dump -h localhost -U omnibot omnibot > "${BACKUP_FILE}"

echo "Backup completed: ${BACKUP_FILE}"
# Keep only last 7 days of backups
find "${BACKUP_DIR}" -name "omnibot_backup_*.sql" -mtime +7 -delete
