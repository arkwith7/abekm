#!/usr/bin/env bash
set -euo pipefail

# Simple production deploy runner on the server
# Usage: ./shell-script/deploy.sh [up|down|restart|logs SERVICE]

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

case "${1:-up}" in
  up)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    ;;
  restart)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    ;;
  logs)
    shift || true
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f --tail=200 ${1:-nginx}
    ;;
  *)
    echo "Usage: $0 [up|down|restart|logs SERVICE]" >&2
    exit 2
    ;;
esac
