#!/bin/bash

# WKMS 개발 환경 Docker 시작 스크립트
# (과거 .env.docker 기반 방식을 단순화하여, 기본 docker-compose.yml만 사용)

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

echo "=== WKMS 개발 환경 (Docker) 시작 ==="

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

echo "🧹 기존 개발 컨테이너 정리 중..."
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" down --remove-orphans || true

echo "🚀 개발 환경 시작 중..."
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build

echo ""
echo "📊 컨테이너 상태:"
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" ps

echo ""
echo "🎉 개발 환경 시작 완료!"
echo ""
echo "서비스 접속 정보:"
echo "  - 프론트엔드: http://localhost:3000"
echo "  - 백엔드 API: http://localhost:8000"
echo "  - API 문서: http://localhost:8000/docs"
echo "  - PgAdmin: http://localhost:5050"
echo "  - Nginx 프록시: http://localhost"
echo ""
echo "로그 확인: docker compose logs -f [service_name]"
echo "서비스 중지: docker compose down"
