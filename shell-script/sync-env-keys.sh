#!/bin/bash
# backend/.env의 KEY를 .env.development와 .env.production에 자동 추가
# ⚠️ 값(VALUE)은 자동으로 복사하지 않음 (수동 확인 필요)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  환경 변수 KEY 자동 동기화 도우미${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ ! -f backend/.env ]; then
  echo -e "${RED}❌ backend/.env 파일이 없습니다!${NC}"
  exit 1
fi

# backend/.env에서 누락된 KEY 찾기
BACKEND_KEYS=$(grep -v '^#' backend/.env | grep -v '^$' | cut -d'=' -f1 | sort)
DEV_KEYS=$(grep -v '^#' .env.development | grep -v '^$' | cut -d'=' -f1 | sort)
PROD_KEYS=$(grep -v '^#' .env.production | grep -v '^$' | cut -d'=' -f1 | sort)

MISSING_IN_DEV=$(comm -23 <(echo "$BACKEND_KEYS") <(echo "$DEV_KEYS"))
MISSING_IN_PROD=$(comm -23 <(echo "$BACKEND_KEYS") <(echo "$PROD_KEYS"))

if [ -z "$MISSING_IN_DEV" ] && [ -z "$MISSING_IN_PROD" ]; then
  echo -e "${GREEN}✅ 모든 KEY가 동기화되어 있습니다!${NC}"
  exit 0
fi

echo -e "${YELLOW}다음 KEY를 Docker 환경 파일에 추가합니다:${NC}"
echo ""

# .env.development에 추가
if [ -n "$MISSING_IN_DEV" ]; then
  echo -e "${YELLOW}[.env.development에 추가할 KEY]${NC}"
  echo "$MISSING_IN_DEV" | while read key; do
    VALUE=$(grep "^${key}=" backend/.env | cut -d'=' -f2-)
    echo -e "  ${GREEN}${key}${NC} = ${VALUE}"
    echo "${key}=${VALUE}" >> .env.development
  done
  echo ""
fi

# .env.production에 추가
if [ -n "$MISSING_IN_PROD" ]; then
  echo -e "${YELLOW}[.env.production에 추가할 KEY]${NC}"
  echo "$MISSING_IN_PROD" | while read key; do
    VALUE=$(grep "^${key}=" backend/.env | cut -d'=' -f2-)
    echo -e "  ${GREEN}${key}${NC} = ${VALUE}"
    echo "${key}=${VALUE}  # ⚠️ 프로덕션 값으로 변경 필요!" >> .env.production
  done
  echo ""
fi

echo -e "${GREEN}✅ KEY 자동 추가 완료!${NC}"
echo -e "${YELLOW}⚠️  중요: .env.production의 값(VALUE)을 프로덕션 환경에 맞게 수정하세요!${NC}"
echo ""
echo -e "${YELLOW}다음 명령으로 확인:${NC}"
echo -e "  vi .env.development"
echo -e "  vi .env.production"
