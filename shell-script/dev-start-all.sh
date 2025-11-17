#!/bin/bash

# WKMS 개발 환경 전체 시작 스크립트
# 데이터베이스 서비스 + 백엔드 + 프론트엔드 모두 실행

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

echo "=== WKMS 전체 개발 환경 시작 ==="
echo ""

# 데이터베이스 서비스 시작
echo "1. 데이터베이스 서비스 시작..."
./shell-script/dev-start-db.sh

echo ""
echo "2. 잠시 대기 중... (데이터베이스 초기화)"
sleep 5

echo ""
echo "3. 백엔드와 프론트엔드를 별도 터미널에서 실행하세요:"
echo ""
echo "백엔드 실행:"
echo "  ./shell-script/dev-start-backend.sh"
echo ""
echo "프론트엔드 실행:"
echo "  ./shell-script/dev-start-frontend.sh"
echo ""
echo "또는 Docker Compose로 전체 실행:"
echo "  docker compose up -d"
echo ""
