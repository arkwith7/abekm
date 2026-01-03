#!/usr/bin/env bash
set -euo pipefail

# Runs functional (API wiring) tests inside BOTH backend + celery-worker containers.
# Requires: docker compose services are up.

services=(backend celery-worker)

for svc in "${services[@]}"; do
  echo "=== [${svc}] pytest -m functional ==="
  docker compose exec -T -w /app "${svc}" env PYTHONPATH=/app pytest -m functional tests/functional
done
