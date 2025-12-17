#!/bin/bash

# WKMS 개발 환경 전체 시작 스크립트
# 개발 환경을 전부 Docker Compose 기반으로 실행

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

echo "=== WKMS 전체 개발 환경 시작 (Docker Compose) ==="
echo ""

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
	DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
	DOCKER_COMPOSE=(docker-compose)
else
	echo "❌ docker compose(또는 docker-compose)를 찾을 수 없습니다. Docker 설치/실행 상태를 확인하세요."
	exit 1
fi

COMPOSE_FILE="$REPO_ROOT_DIR/docker-compose.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
	echo "❌ docker-compose.yml을 찾을 수 없습니다: $COMPOSE_FILE"
	exit 1
fi

echo "1. 전체 서비스 기동 (postgres, redis, pgadmin, backend, celery-worker, frontend...)"
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build

echo ""
echo "📊 컨테이너 상태:"
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" ps

echo ""
echo "✅ 시작 완료"
echo "- 백엔드 로그:  docker compose logs -f --tail=200 backend"
echo "- 워커 로그:    docker compose logs -f --tail=200 celery-worker"
echo "- 프론트 로그:  docker compose logs -f --tail=200 frontend"
echo "- 전체 로그:    docker compose logs -f --tail=200"
echo ""
