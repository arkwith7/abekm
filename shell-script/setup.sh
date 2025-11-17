#!/bin/bash

# WKMS 클라우드 네이티브 개발환경 설정 스크립트

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

echo "🚀 WKMS 클라우드 네이티브 개발환경 설정을 시작합니다..."

# 필요한 디렉토리 생성
echo "📁 디렉토리 구조 확인 중..."
mkdir -p backend/uploads
mkdir -p frontend/public

echo "🔧 환경 변수 파일 설정 중..."
if [ ! -f backend/.env ]; then
    if [ -f backend/.env.example ]; then
        cp backend/.env.example backend/.env
        echo "✅ backend/.env 파일이 생성되었습니다. 필요한 설정을 수정해주세요."
    else
        echo "ℹ️  backend/.env.example 템플릿이 없어 생성을 건너뜁니다."
    fi
else
    echo "ℹ️  backend/.env 파일이 이미 존재합니다."
fi

echo "🌐 Docker 네트워크 생성 중..."
docker network create wkms-network 2>/dev/null || echo "ℹ️  네트워크가 이미 존재합니다."

echo "🐳 Docker 서비스 빌드 및 실행 중..."
docker compose up --build -d

echo "⏳ 서비스 초기화 대기 중... (30초)"
sleep 30

echo "📄 데이터베이스 마이그레이션 실행 중..."
docker compose exec backend alembic revision --autogenerate -m "Initial migration" || true
docker compose exec backend alembic upgrade head || true

echo "✅ 설정이 완료되었습니다!"
echo ""
echo "🌟 서비스 접속 정보:"
echo "   - 프론트엔드: http://localhost:3000"
echo "   - 백엔드 API: http://localhost:8000"
echo "   - API 문서: http://localhost:8000/docs"
echo "   - PgAdmin: http://localhost:5050"
echo ""
echo "🎨 UI 프레임워크: TailwindCSS"
echo "   - 유틸리티 우선 CSS 프레임워크"
echo "   - 반응형 디자인 지원"
echo "   - Lucide React 아이콘 사용"
echo ""
echo "🔧 개발 명령어:"
echo "   - 로그 확인: docker compose logs -f"
echo "   - 서비스 중지: docker compose down"
echo "   - 서비스 재시작: docker compose restart"
echo ""
echo "📚 자세한 내용은 README.md를 참고하세요."
