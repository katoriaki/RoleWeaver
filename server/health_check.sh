#!/usr/bin/env bash
set -euo pipefail

PORT="${ROLEWEAVER_PORT:-8000}"
HOST="${ROLEWEAVER_HEALTH_HOST:-127.0.0.1}"

curl -fsS "http://${HOST}:${PORT}/health"
echo
