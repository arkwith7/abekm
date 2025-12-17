#!/bin/bash

# WKMS 백엔드 개발 서버 시작 스크립트 (Docker Compose 기반)
# 목표:
# - 개발 환경을 운영(컨테이너 기반)과 최대한 동일하게 맞춤
# - 코드 수정 시 FastAPI는 --reload로 자동 반영
# - Celery Worker는 별도 컨테이너로 구동

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR" || exit 1

echo "==================================================================="
echo "   WKMS 백엔드 개발 서버 시작 (Docker Compose / reload)"
echo "==================================================================="
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

echo "✅ Compose 파일: $COMPOSE_FILE"
echo "✅ 실행 대상: backend, celery-worker (의존 서비스는 자동 시작)"
echo ""

# 종료 시 자식 프로세스 정리 함수
cleanup() {
    echo ""
    echo "🛑 서버를 종료합니다..."

    # 개발 편의: DB/Redis는 유지하고, backend/celery-worker만 중지
    "${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" stop backend celery-worker >/dev/null 2>&1 || true

    echo "✅ backend/celery-worker 컨테이너를 중지했습니다. (DB/Redis는 그대로 유지)"
    exit 0
}

# SIGINT, SIGTERM 시그널 캐치
trap cleanup SIGINT SIGTERM

# Docker Compose로 개발 서버 시작
echo "🚀 Docker Compose로 backend/celery-worker를 시작합니다..."
echo "-------------------------------------------------------------------"
echo "   📍 API 서버:     http://localhost:8000"
echo "   📚 API 문서:     http://localhost:8000/docs"
echo "   🔄 Swagger UI:   http://localhost:8000/docs"
echo "   📖 ReDoc:        http://localhost:8000/redoc"
echo "   ✅ FastAPI reload: 활성화 (컨테이너 내 uvicorn --reload)"
echo "   ✅ Celery Worker:  컨테이너로 실행"
echo "-------------------------------------------------------------------"
echo ""
echo "💡 서버를 중지하려면 Ctrl+C를 누르세요."
echo ""

# 백그라운드로 띄우고, 로그를 follow (Ctrl+C 시 backend/celery-worker stop)
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --build backend celery-worker

echo ""
echo "🎉 컨테이너가 시작되었습니다. 로그를 표시합니다:"
echo "==================================================================="
"${DOCKER_COMPOSE[@]}" -f "$COMPOSE_FILE" logs -f --tail=100 backend celery-worker

# logs -f 종료 후 정리
cleanup
