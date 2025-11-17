#!/bin/bash

# WKMS 개발 환경 Docker 시작 스크립트

echo "=== WKMS 개발 환경 (Docker) 시작 ==="

# 기존 개발 컨테이너 정리
echo "🧹 기존 개발 컨테이너 정리 중..."
docker compose --env-file .env.docker down --remove-orphans

# 개발 환경 시작
echo "🚀 개발 환경 시작 중..."

# 프론트엔드 환경 변수 파일도 함께 로드
export $(cat .env.docker | grep -v '^#' | xargs)
export $(cat frontend/.env.docker 2>/dev/null | grep -v '^#' | xargs) || echo "⚠️  frontend/.env.docker 파일이 없습니다."

docker compose --env-file .env.docker up -d

echo ""
echo "📊 컨테이너 상태:"
docker compose --env-file .env.docker ps

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
echo "로그 확인: docker compose --env-file .env.docker logs -f [service_name]"
echo "서비스 중지: docker compose --env-file .env.docker down"