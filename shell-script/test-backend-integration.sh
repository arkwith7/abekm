#!/usr/bin/env bash
set -euo pipefail

# Runs integration tests inside BOTH backend + celery-worker containers.
# Requires: docker compose services are up AND test DB config is available.

services=(backend celery-worker)

for svc in "${services[@]}"; do
  echo "=== [${svc}] pytest -m integration ==="
  docker compose exec -T -w /app "${svc}" env PYTHONPATH=/app pytest -m integration tests/integration
done
