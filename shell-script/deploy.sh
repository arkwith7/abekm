#!/usr/bin/env bash
set -euo pipefail

# Simple production deploy runner on the server
# Usage: ./shell-script/deploy.sh [up|down|restart|logs SERVICE]

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

COMPOSE_FILE="docker-compose.prod.yml"

# backend/.env 파일 체크
if [ ! -f "./backend/.env" ]; then
  echo "Error: backend/.env file not found" >&2
  exit 1
fi

case "${1:-up}" in
  up)
    docker compose -f "$COMPOSE_FILE" up -d --build
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" down
    ;;
  restart)
    docker compose -f "$COMPOSE_FILE" restart
    ;;
  rebuild)
    docker compose -f "$COMPOSE_FILE" up -d --build
    ;;
  logs)
    shift || true
    docker compose -f "$COMPOSE_FILE" logs -f --tail=200 ${1:-nginx}
    ;;
  ps)
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  *)
    echo "Usage: $0 [up|down|restart|rebuild|logs SERVICE|ps]" >&2
    exit 2
    ;;
esac
