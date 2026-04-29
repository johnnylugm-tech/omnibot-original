#!/bin/bash
# Database Restore Script - Phase 3
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql>"
    exit 1
fi

BACKUP_FILE=$1

echo "Starting database restore from $BACKUP_FILE..."
PGPASSWORD=password psql -h localhost -U omnibot -d omnibot < "$BACKUP_FILE"

echo "Restore completed."
