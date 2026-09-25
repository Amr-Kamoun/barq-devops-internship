#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <backup-file>" >&2
    exit 2
fi

BACKUP_FILE="$1"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file does not exist or is empty: $BACKUP_FILE" >&2
    exit 1
fi

echo "Restoring PostgreSQL backup: $BACKUP_FILE"

docker compose -p "${COMPOSE_PROJECT_NAME:-barq-assessment}" \
    exec -T postgres \
    sh -c 'pg_restore \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --clean \
        --if-exists \
        --no-owner \
        --exit-on-error' \
    < "$BACKUP_FILE"

echo "PASS: restore completed"
