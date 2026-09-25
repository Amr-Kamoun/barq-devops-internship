#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-barq-assessment-app-01:latest}"

if ! command -v docker >/dev/null 2>&1; then
    echo "FAIL: docker is not installed" >&2
    exit 1
fi

if ! docker scout version >/dev/null 2>&1; then
    echo "FAIL: Docker Scout is not available" >&2
    exit 1
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "FAIL: local image not found: $IMAGE" >&2
    echo "Build it first with: docker compose build" >&2
    exit 1
fi

echo "Scanning local image: $IMAGE"
echo "Severity filter: critical,high"

ARGS=(
    cves
    --only-severity critical,high
)

if [ "${SCOUT_STRICT:-0}" = "1" ]; then
    echo "Strict mode enabled: vulnerabilities cause a non-zero exit."
    ARGS+=(--exit-code)
else
    echo "Report-only mode: findings are reported without failing the command."
fi

docker scout "${ARGS[@]}" "local://${IMAGE}"
