#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${1:-${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.dump}"

mkdir -p "$(dirname "$BACKUP_FILE")"

echo "Creating PostgreSQL backup..."

docker compose -p "${COMPOSE_PROJECT_NAME:-barq-assessment}" \
    exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
    > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file is empty" >&2
    exit 1
fi

echo "PASS: backup created"
echo "$BACKUP_FILE"
