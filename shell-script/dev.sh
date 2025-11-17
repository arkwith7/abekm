#!/usr/bin/env bash
set -euo pipefail

# Simple local dev runner
# Usage: ./shell-script/dev.sh [up|down|logs SERVICE]

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env.development"

case "${1:-up}" in
  up)
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
    ;;
  down)
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
    ;;
  logs)
    shift || true
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs -f --tail=200 ${1:-backend}
    ;;
  *)
    echo "Usage: $0 [up|down|logs SERVICE]" >&2
    exit 2
    ;;
esac
