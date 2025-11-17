#!/bin/bash
# 환경 변수 파일 간 KEY 동기화 검증 스크립트

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  환경 변수 동기화 검증${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 환경 변수 KEY 추출 함수
extract_keys() {
  grep -v '^#' "$1" | grep -v '^$' | cut -d'=' -f1 | sort
}

# backend/.env의 KEY 추출
if [ -f backend/.env ]; then
  BACKEND_KEYS=$(extract_keys backend/.env)
  echo -e "${BLUE}[1/4]${NC} backend/.env 분석 완료 ($(echo "$BACKEND_KEYS" | wc -l)개 KEY)"
else
  echo -e "${YELLOW}⚠️  backend/.env 파일이 없습니다 (터미널 직접 실행용)${NC}"
  BACKEND_KEYS=""
fi

# .env.development의 KEY 추출
if [ -f .env.development ]; then
  DEV_KEYS=$(extract_keys .env.development)
  echo -e "${BLUE}[2/4]${NC} .env.development 분석 완료 ($(echo "$DEV_KEYS" | wc -l)개 KEY)"
else
  echo -e "${RED}❌ .env.development 파일이 없습니다!${NC}"
  exit 1
fi

# .env.production의 KEY 추출
if [ -f .env.production ]; then
  PROD_KEYS=$(extract_keys .env.production)
  echo -e "${BLUE}[3/4]${NC} .env.production 분석 완료 ($(echo "$PROD_KEYS" | wc -l)개 KEY)"
else
  echo -e "${RED}❌ .env.production 파일이 없습니다!${NC}"
  exit 1
fi

echo ""
echo -e "${BLUE}[4/4]${NC} KEY 동기화 검증 중..."
echo ""

# backend/.env에만 있는 KEY (Docker 배포 시 누락될 KEY)
MISSING_IN_DEV=$(comm -23 <(echo "$BACKEND_KEYS") <(echo "$DEV_KEYS"))
MISSING_IN_PROD=$(comm -23 <(echo "$BACKEND_KEYS") <(echo "$PROD_KEYS"))

ERROR=0

if [ -n "$MISSING_IN_DEV" ]; then
  echo -e "${RED}❌ .env.development에 누락된 KEY (backend/.env에만 존재):${NC}"
  echo "$MISSING_IN_DEV" | while read key; do
    echo -e "   ${RED}$key${NC}"
    VALUE=$(grep "^${key}=" backend/.env | cut -d'=' -f2-)
    echo -e "   ${YELLOW}→ backend/.env 값: ${VALUE}${NC}"
  done
  echo ""
  ERROR=1
fi

if [ -n "$MISSING_IN_PROD" ]; then
  echo -e "${RED}❌ .env.production에 누락된 KEY (backend/.env에만 존재):${NC}"
  echo "$MISSING_IN_PROD" | while read key; do
    echo -e "   ${RED}$key${NC}"
    VALUE=$(grep "^${key}=" backend/.env | cut -d'=' -f2-)
    echo -e "   ${YELLOW}→ backend/.env 값: ${VALUE}${NC}"
  done
  echo ""
  ERROR=1
fi

# .env.development와 .env.production 간 차이
ONLY_IN_DEV=$(comm -23 <(echo "$DEV_KEYS") <(echo "$PROD_KEYS"))
ONLY_IN_PROD=$(comm -23 <(echo "$PROD_KEYS") <(echo "$DEV_KEYS"))

if [ -n "$ONLY_IN_DEV" ]; then
  echo -e "${YELLOW}⚠️  .env.development에만 있는 KEY:${NC}"
  echo "$ONLY_IN_DEV" | while read key; do
    echo -e "   ${YELLOW}$key${NC}"
  done
  echo ""
fi

if [ -n "$ONLY_IN_PROD" ]; then
  echo -e "${YELLOW}⚠️  .env.production에만 있는 KEY:${NC}"
  echo "$ONLY_IN_PROD" | while read key; do
    echo -e "   ${YELLOW}$key${NC}"
  done
  echo ""
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $ERROR -eq 0 ]; then
  echo -e "${GREEN}✅ 모든 환경 변수 파일이 동기화되어 있습니다!${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  exit 0
else
  echo -e "${RED}❌ 동기화 오류 발견!${NC}"
  echo -e "${YELLOW}💡 해결 방법: backend/.env의 누락된 KEY를 Docker 환경 파일에 추가하세요.${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  exit 1
fi
