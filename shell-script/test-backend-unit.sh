#!/usr/bin/env bash
set -euo pipefail

# Runs unit tests inside BOTH backend + celery-worker containers.
# Requires: docker compose services are up.

services=(backend celery-worker)

for svc in "${services[@]}"; do
  echo "=== [${svc}] pytest -m unit ==="
  docker compose exec -T -w /app "${svc}" env PYTHONPATH=/app pytest -m unit tests/unit
done
