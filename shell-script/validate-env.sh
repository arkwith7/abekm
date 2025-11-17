#!/bin/bash
# ABEKM Docker Compose 배포 전 환경 변수 검증 스크립트
# 
# 용도: Docker Compose 배포용 환경 파일 (.env.development, .env.production) 검증
# 참고: 터미널 직접 실행 개발 환경은 backend/.env 사용 (검증 불필요)

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 환경 파라미터 (기본: development)
ENV_FILE="${1:-.env.development}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  ABEKM Docker Compose 배포 전 환경 검증${NC}"
echo -e "${BLUE}  검증 대상: ${ENV_FILE}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

ERROR_COUNT=0
WARNING_COUNT=0

# 1. Docker Compose 환경 파일 존재 확인
echo -e "${BLUE}[1/5]${NC} Docker Compose 환경 파일 확인..."
if [ ! -f "$ENV_FILE" ]; then
  echo -e "${RED}  ❌ 오류: ${ENV_FILE} 파일이 없습니다!${NC}"
  echo -e "${YELLOW}  💡 해결 방법:${NC}"
  echo -e "     ${GREEN}# 개발 환경${NC}"
  echo -e "     ${GREEN}cp .env.development.example .env.development${NC}"
  echo -e "     ${GREEN}# 또는 프로덕션 환경${NC}"
  echo -e "     ${GREEN}cp .env.production.example .env.production${NC}"
  ((ERROR_COUNT++))
else
  echo -e "${GREEN}  ✅ ${ENV_FILE} 파일 존재${NC}"
fi

# 2. 필수 환경 변수 확인 (Docker Compose용)
echo -e "${BLUE}[2/5]${NC} Docker Compose 필수 환경 변수 확인..."
REQUIRED_VARS=(
  "POSTGRES_DB"
  "POSTGRES_USER"
  "POSTGRES_PASSWORD"
  "DATABASE_URL"
  "REDIS_URL"
  "SECRET_KEY"
  "CORS_ORIGINS"
  "STORAGE_BACKEND"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
  if [ -f "$ENV_FILE" ] && ! grep -q "^${var}=" "$ENV_FILE"; then
    MISSING_VARS+=("$var")
  fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  echo -e "${RED}  ❌ 오류: 다음 필수 환경 변수가 누락되었습니다:${NC}"
  for var in "${MISSING_VARS[@]}"; do
    echo -e "     - ${RED}${var}${NC}"
  done
  ((ERROR_COUNT++))
else
  echo -e "${GREEN}  ✅ 필수 환경 변수 완료 (${#REQUIRED_VARS[@]}개)${NC}"
fi

# 3. 보안 설정 확인
echo -e "${BLUE}[3/5]${NC} 보안 설정 확인..."
if [ -f "$ENV_FILE" ]; then
  # 프로덕션 환경인 경우 더 엄격하게 검증
  if [[ "$ENV_FILE" == *"production"* ]]; then
    if grep -q "POSTGRES_PASSWORD=wkms123" "$ENV_FILE"; then
      echo -e "${RED}  ❌ POSTGRES_PASSWORD가 기본값입니다! 프로덕션에서는 반드시 변경 필요!${NC}"
      ((ERROR_COUNT++))
    fi
    if grep -q 'SECRET_KEY=.*your.*secret' "$ENV_FILE"; then
      echo -e "${RED}  ❌ SECRET_KEY가 기본값입니다! 프로덕션에서는 반드시 변경 필요!${NC}"
      ((ERROR_COUNT++))
    fi
    if grep -q 'CORS_ORIGINS=.*localhost' "$ENV_FILE"; then
      echo -e "${YELLOW}  ⚠️  CORS_ORIGINS에 localhost가 포함되어 있습니다. 프로덕션 도메인으로 변경 권장!${NC}"
      ((WARNING_COUNT++))
    fi
  else
    # 개발 환경은 경고만
    if grep -q "POSTGRES_PASSWORD=wkms123" "$ENV_FILE"; then
      echo -e "${YELLOW}  ⚠️  POSTGRES_PASSWORD가 기본값입니다 (개발 환경이므로 허용).${NC}"
    fi
  fi
fi

if [ $WARNING_COUNT -eq 0 ] && [ $ERROR_COUNT -eq 0 ]; then
  echo -e "${GREEN}  ✅ 보안 설정 양호${NC}"
fi

# 4. frontend/.env 파일 확인
echo -e "${BLUE}[4/5]${NC} 프론트엔드 .env 파일 확인..."
if [ ! -f frontend/.env ]; then
  echo -e "${RED}  ❌ 오류: frontend/.env 파일이 없습니다!${NC}"
  echo -e "${YELLOW}  💡 해결 방법: frontend/.env 파일을 생성하세요.${NC}"
  echo -e "     ${GREEN}cat > frontend/.env << 'EOF'${NC}"
  echo -e "     ${GREEN}REACT_APP_API_URL=http://localhost:8000${NC}"
  echo -e "     ${GREEN}REACT_APP_ENV=development${NC}"
  echo -e "     ${GREEN}EOF${NC}"
  ((ERROR_COUNT++))
else
  echo -e "${GREEN}  ✅ frontend/.env 존재${NC}"
  
  # REACT_APP_API_URL 확인
  if ! grep -q "^REACT_APP_API_URL=" frontend/.env; then
    echo -e "${RED}  ❌ REACT_APP_API_URL이 설정되지 않았습니다!${NC}"
    ((ERROR_COUNT++))
  else
    API_URL=$(grep "^REACT_APP_API_URL=" frontend/.env | cut -d'=' -f2)
    echo -e "     API URL: ${GREEN}${API_URL}${NC}"
    
    # 프로덕션에서 localhost 경고
    if [[ "$ENV_FILE" == *"production"* ]] && echo "$API_URL" | grep -q "localhost"; then
      echo -e "${RED}     ❌ 프로덕션 환경에서 localhost 사용 중! 실제 서버 IP/도메인으로 변경 필수!${NC}"
      ((ERROR_COUNT++))
    fi
  fi
fi

# 5. Docker Compose 파일 확인
echo -e "${BLUE}[5/5]${NC} Docker Compose 설정 파일 확인..."
if [[ "$ENV_FILE" == *"production"* ]]; then
  COMPOSE_FILE="docker-compose.prod.yml"
else
  COMPOSE_FILE="docker-compose.yml"
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo -e "${YELLOW}  ⚠️  ${COMPOSE_FILE} 파일이 없습니다.${NC}"
  ((WARNING_COUNT++))
else
  echo -e "${GREEN}  ✅ ${COMPOSE_FILE} 존재${NC}"
fi

# 결과 요약
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ERROR_COUNT -eq 0 ]; then
  echo -e "${GREEN}✅ 검증 통과!${NC}"
  if [ $WARNING_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠️  경고 ${WARNING_COUNT}개 (프로덕션 배포 전 확인 필요)${NC}"
  fi
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}다음 명령으로 배포를 진행하세요:${NC}"
  if [[ "$ENV_FILE" == *"production"* ]]; then
    echo -e "  ${GREEN}docker-compose -f docker-compose.prod.yml --env-file .env.production up -d${NC}"
  else
    echo -e "  ${GREEN}docker-compose --env-file .env.development up -d${NC}"
  fi
  exit 0
else
  echo -e "${RED}❌ 검증 실패! 오류 ${ERROR_COUNT}개${NC}"
  if [ $WARNING_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠️  경고 ${WARNING_COUNT}개${NC}"
  fi
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}위의 오류를 수정 후 다시 실행하세요.${NC}"
  echo ""
  echo -e "${YELLOW}💡 도움말:${NC}"
  echo -e "  - 개발 환경 검증: ${GREEN}./shell-script/validate-env.sh .env.development${NC}"
  echo -e "  - 프로덕션 검증:   ${GREEN}./shell-script/validate-env.sh .env.production${NC}"
  exit 1
fi
