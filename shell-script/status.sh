#!/usr/bin/env bash
set -euo pipefail

# Docker 배포 상태 확인 스크립트
# Usage: ./shell-script/status.sh [dev|prod]

ENVIRONMENT="${1:-prod}"
REPO_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT"

if [ "$ENVIRONMENT" = "dev" ]; then
  COMPOSE_FILE="docker-compose.dev.yml"
else
  COMPOSE_FILE="docker-compose.prod.yml"
fi

echo "=========================================="
echo "Docker 배포 상태 ($ENVIRONMENT)"
echo "=========================================="
echo ""

echo "📦 컨테이너 상태:"
docker compose -f "$COMPOSE_FILE" ps
echo ""

echo "📊 리소스 사용량:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null) 2>/dev/null || echo "실행 중인 컨테이너 없음"
echo ""

echo "💾 볼륨 목록:"
docker volume ls --filter=name=abkms
echo ""

echo "🌐 네트워크 목록:"
docker network ls --filter=name=abkms
echo ""

echo "🖼️  이미지 목록:"
docker images --filter=reference='abkms-*'
echo ""

echo "=========================================="
echo "빠른 명령어:"
echo "=========================================="
echo "로그 확인: docker compose -f $COMPOSE_FILE logs -f [service]"
echo "재시작: docker compose -f $COMPOSE_FILE restart [service]"
echo "중지: docker compose -f $COMPOSE_FILE down"
echo "재빌드: docker compose -f $COMPOSE_FILE up -d --build"
echo ""
