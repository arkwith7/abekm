#!/usr/bin/env bash
set -euo pipefail

# 배포 전 환경 체크 스크립트
# Usage: ./shell-script/check-deployment.sh [dev|test|prod]

ENVIRONMENT="${1:-prod}"
REPO_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "배포 환경 체크: $ENVIRONMENT"
echo "=========================================="
echo ""

# 1. 필수 파일 체크
echo "✓ 필수 파일 체크..."
REQUIRED_FILES=(
  "backend/.env"
  "docker-compose.prod.yml"
  "backend/Dockerfile"
  "frontend/Dockerfile.prod"
  "nginx/Dockerfile"
)

MISSING_FILES=()
for FILE in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$FILE" ]; then
    MISSING_FILES+=("$FILE")
  fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
  echo "❌ 누락된 파일:"
  printf '  - %s\n' "${MISSING_FILES[@]}"
  exit 1
fi
echo "  ✅ 모든 필수 파일 존재"
echo ""

# 2. backend/.env 필수 변수 체크
echo "✓ backend/.env 필수 변수 체크..."
REQUIRED_ENV_VARS=(
  "POSTGRES_PASSWORD"
  "SECRET_KEY"
  "AWS_ACCESS_KEY_ID"
  "AWS_SECRET_ACCESS_KEY"
  "AWS_REGION"
  "AWS_S3_BUCKET"
)

MISSING_VARS=()
for VAR in "${REQUIRED_ENV_VARS[@]}"; do
  if ! grep -q "^${VAR}=" backend/.env; then
    MISSING_VARS+=("$VAR")
  fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  echo "❌ backend/.env에 누락된 변수:"
  printf '  - %s\n' "${MISSING_VARS[@]}"
  exit 1
fi
echo "  ✅ 모든 필수 환경 변수 존재"
echo ""

# 3. 민감 정보 체크 (기본값 사용 여부)
echo "✓ 민감 정보 보안 체크..."
INSECURE_VALUES=()

if grep -q "SECRET_KEY=your-super-secret" backend/.env 2>/dev/null; then
  INSECURE_VALUES+=("SECRET_KEY가 기본값입니다")
fi

if grep -q "POSTGRES_PASSWORD=wkms123" backend/.env 2>/dev/null; then
  INSECURE_VALUES+=("POSTGRES_PASSWORD가 기본값입니다")
fi

if [ ${#INSECURE_VALUES[@]} -gt 0 ]; then
  echo "⚠️  보안 경고:"
  printf '  - %s\n' "${INSECURE_VALUES[@]}"
  if [ "$ENVIRONMENT" = "prod" ]; then
    echo ""
    read -p "운영 환경에 기본값 사용은 위험합니다. 계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      exit 1
    fi
  fi
else
  echo "  ✅ 보안 설정 정상"
fi
echo ""

# 4. Docker 상태 체크
echo "✓ Docker 서비스 체크..."
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker가 실행되고 있지 않습니다"
  exit 1
fi
echo "  ✅ Docker 정상 실행 중"
echo ""

# 5. 디스크 공간 체크
echo "✓ 디스크 공간 체크..."
AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 10 ]; then
  echo "⚠️  디스크 공간 부족: ${AVAILABLE_SPACE}GB (최소 10GB 권장)"
  if [ "$ENVIRONMENT" = "prod" ]; then
    exit 1
  fi
else
  echo "  ✅ 디스크 공간 충분: ${AVAILABLE_SPACE}GB"
fi
echo ""

# 6. 포트 충돌 체크
echo "✓ 포트 충돌 체크..."
PORTS_TO_CHECK=(80 443 5432 6379 8000)
PORTS_IN_USE=()

for PORT in "${PORTS_TO_CHECK[@]}"; do
  if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
    PORTS_IN_USE+=("$PORT")
  fi
done

if [ ${#PORTS_IN_USE[@]} -gt 0 ]; then
  echo "⚠️  사용 중인 포트:"
  printf '  - %s\n' "${PORTS_IN_USE[@]}"
  echo ""
  echo "  기존 컨테이너를 중지하려면: docker compose -f docker-compose.prod.yml down"
else
  echo "  ✅ 모든 포트 사용 가능"
fi
echo ""

# 7. 환경별 설정 요약
echo "=========================================="
echo "환경 설정 요약 ($ENVIRONMENT)"
echo "=========================================="
echo "DATABASE_URL: $(grep -E '^DATABASE_URL=' backend/.env | cut -d'=' -f2 | sed 's/:.*@/:***@/')"
echo "REDIS_URL: $(grep -E '^REDIS_URL=' backend/.env | cut -d'=' -f2)"
echo "STORAGE_BACKEND: $(grep -E '^STORAGE_BACKEND=' backend/.env | cut -d'=' -f2 || echo 's3')"
echo "AWS_REGION: $(grep -E '^AWS_REGION=' backend/.env | cut -d'=' -f2)"
echo "AWS_S3_BUCKET: $(grep -E '^AWS_S3_BUCKET=' backend/.env | cut -d'=' -f2)"
echo ""

echo "=========================================="
echo "✅ 배포 전 체크 완료"
echo "=========================================="
echo ""
echo "다음 명령어로 배포를 시작하세요:"
echo "  ./shell-script/deploy.sh up"
echo ""
