#!/usr/bin/env bash
set -euo pipefail

# Simple Docker-based dev runner
# Usage: ./shell-script/dev.sh [up|down|logs SERVICE]

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

COMPOSE_FILE="docker-compose.yml"

case "${1:-up}" in
  up)
    docker compose -f "$COMPOSE_FILE" up -d --build
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" down
    ;;
  logs)
    shift || true
    docker compose -f "$COMPOSE_FILE" logs -f --tail=200 ${1:-backend}
    ;;
  *)
    echo "Usage: $0 [up|down|logs SERVICE]" >&2
    exit 2
    ;;
esac
