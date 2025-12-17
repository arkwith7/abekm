#!/bin/bash

# WKMS 프론트엔드 개발 서버 시작 스크립트 (Docker Compose 기반)
# - 운영과 동일하게 컨테이너로 실행
# - 로그는 docker compose logs -f 로 모니터링

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR" || exit 1

echo "=== WKMS 프론트엔드 개발 서버 시작 (Docker Compose) ==="
echo ""

# docker compose 명령 탐지
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

cleanup() {
    echo ""
    echo "🛑 프론트엔드를 종료합니다..."
    "${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" stop frontend >/dev/null 2>&1 || true
    echo "✅ frontend 컨테이너를 중지했습니다."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🚀 Docker Compose로 frontend를 시작합니다..."
echo "   🌐 접속 주소: http://localhost:3000"
echo ""
echo "💡 서버를 중지하려면 Ctrl+C를 누르세요."
echo ""

"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build frontend

echo ""
echo "🎉 컨테이너가 시작되었습니다. 로그를 표시합니다:"
echo "==================================================================="
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" logs -f --tail=100 frontend

cleanup
