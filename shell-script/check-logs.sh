#!/usr/bin/env bash
set -euo pipefail

# Lightweight log viewer for docker compose services
# Usage:
#   ./shell-script/check-logs.sh [service] [--follow] [--since 10m] [--tail 200] [--grep pattern]

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

service="${1:-}"
shift || true

follow=""
since="--since 15m"
tail="--tail 200"
grep_pattern=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --follow|-f)
      follow="--follow"; shift ;;
    --since)
      since="--since ${2}"; shift 2 ;;
    --tail)
      tail="--tail ${2}"; shift 2 ;;
    --grep)
      grep_pattern="${2}"; shift 2 ;;
    *)
      echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${service}" ]]; then
  echo "Usage: $0 <service> [--follow] [--since 10m] [--tail 200] [--grep pattern]" >&2
  echo "Services: postgres, redis, backend, frontend, nginx" >&2
  exit 2
fi

container="wkms-${service}-prod"

cmd=(docker logs ${container} ${follow} ${since} ${tail})
if [[ -n "${grep_pattern}" ]]; then
  "${cmd[@]}" | grep -E --color=always "${grep_pattern}" || true
else
  "${cmd[@]}"
fi
