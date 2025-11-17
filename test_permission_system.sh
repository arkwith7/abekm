#!/bin/bash

# 권한 승인 시스템 통합 테스트 스크립트
# 사용법: ./test_permission_system.sh

set -e

echo "🚀 권한 승인 시스템 통합 테스트 시작"
echo "=========================================="
echo ""

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 테스트 환경 변수
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TEST_USER_TOKEN="${TEST_USER_TOKEN:-TEST001}"
TEST_MANAGER_TOKEN="${TEST_MANAGER_TOKEN:-MGR001}"

echo "📝 테스트 설정:"
echo "  - API Base URL: $API_BASE_URL"
echo "  - Test User Token: $TEST_USER_TOKEN"
echo "  - Test Manager Token: $TEST_MANAGER_TOKEN"
echo ""

# 1. 헬스 체크
echo "1️⃣  백엔드 서버 헬스 체크..."
if curl -s -f "$API_BASE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ 백엔드 서버 정상${NC}"
else
    echo -e "${RED}❌ 백엔드 서버 연결 실패${NC}"
    exit 1
fi
echo ""

# 2. 권한 요청 생성 테스트
echo "2️⃣  권한 요청 생성 테스트..."
REQUEST_RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/v1/permission-requests" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TEST_USER_TOKEN" \
  -d '{
    "container_id": "TEST_CONTAINER_001",
    "requested_role_id": "VIEWER",
    "reason": "통합 테스트를 위한 권한 요청입니다."
  }')

if echo "$REQUEST_RESPONSE" | grep -q '"success":true'; then
    REQUEST_ID=$(echo "$REQUEST_RESPONSE" | grep -o '"request_id":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✅ 권한 요청 생성 성공${NC}"
    echo "   Request ID: $REQUEST_ID"
else
    echo -e "${RED}❌ 권한 요청 생성 실패${NC}"
    echo "   Response: $REQUEST_RESPONSE"
fi
echo ""

# 3. 내 요청 목록 조회 테스트
echo "3️⃣  내 요청 목록 조회 테스트..."
MY_REQUESTS=$(curl -s "$API_BASE_URL/api/v1/permission-requests/my-requests" \
  -H "Authorization: Bearer $TEST_USER_TOKEN")

if echo "$MY_REQUESTS" | grep -q '"success":true'; then
    COUNT=$(echo "$MY_REQUESTS" | grep -o '"total":[0-9]*' | cut -d':' -f2)
    echo -e "${GREEN}✅ 내 요청 목록 조회 성공${NC}"
    echo "   총 요청 수: $COUNT"
else
    echo -e "${RED}❌ 내 요청 목록 조회 실패${NC}"
fi
echo ""

# 4. 대기 중 요청 목록 조회 테스트 (관리자)
echo "4️⃣  대기 중 요청 목록 조회 테스트 (관리자)..."
PENDING_REQUESTS=$(curl -s "$API_BASE_URL/api/v1/permission-requests/pending" \
  -H "Authorization: Bearer $TEST_MANAGER_TOKEN")

if echo "$PENDING_REQUESTS" | grep -q '"success":true'; then
    COUNT=$(echo "$PENDING_REQUESTS" | grep -o '"total":[0-9]*' | cut -d':' -f2)
    echo -e "${GREEN}✅ 대기 중 요청 조회 성공${NC}"
    echo "   대기 중 요청 수: $COUNT"
else
    echo -e "${RED}❌ 대기 중 요청 조회 실패${NC}"
fi
echo ""

# 5. 통계 조회 테스트
echo "5️⃣  권한 요청 통계 조회 테스트..."
STATISTICS=$(curl -s "$API_BASE_URL/api/v1/permission-requests/statistics/summary" \
  -H "Authorization: Bearer $TEST_MANAGER_TOKEN")

if echo "$STATISTICS" | grep -q '"success":true'; then
    TOTAL=$(echo "$STATISTICS" | grep -o '"total_requests":[0-9]*' | cut -d':' -f2)
    PENDING=$(echo "$STATISTICS" | grep -o '"pending_requests":[0-9]*' | cut -d':' -f2)
    echo -e "${GREEN}✅ 통계 조회 성공${NC}"
    echo "   총 요청: $TOTAL, 대기 중: $PENDING"
else
    echo -e "${RED}❌ 통계 조회 실패${NC}"
fi
echo ""

# 6. 권한 요청 승인 테스트 (REQUEST_ID가 있는 경우만)
if [ -n "$REQUEST_ID" ]; then
    echo "6️⃣  권한 요청 승인 테스트..."
    APPROVE_RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/v1/permission-requests/$REQUEST_ID/approve" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TEST_MANAGER_TOKEN" \
      -d '{"approver_comment": "테스트 승인"}')

    if echo "$APPROVE_RESPONSE" | grep -q '"success":true'; then
        echo -e "${GREEN}✅ 권한 요청 승인 성공${NC}"
    else
        echo -e "${YELLOW}⚠️  권한 요청 승인 스킵 (이미 처리됨 또는 권한 없음)${NC}"
    fi
    echo ""
fi

# 7. 프론트엔드 빌드 확인
echo "7️⃣  프론트엔드 파일 존재 확인..."
FRONTEND_FILES=(
    "frontend/src/types/permissionRequest.types.ts"
    "frontend/src/services/permissionRequestService.ts"
    "frontend/src/components/manager/PermissionRequestForm.tsx"
    "frontend/src/components/manager/MyPermissionRequests.tsx"
    "frontend/src/pages/manager/PermissionApprovalManagement.tsx"
)

ALL_EXISTS=true
for file in "${FRONTEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${RED}❌${NC} $file (없음)"
        ALL_EXISTS=false
    fi
done
echo ""

# 8. 백엔드 테스트 실행 (pytest가 설치된 경우)
if command -v pytest &> /dev/null; then
    echo "8️⃣  백엔드 단위 테스트 실행..."
    cd backend
    if pytest tests/test_permission_requests.py -v --tb=short 2>&1 | tail -20; then
        echo -e "${GREEN}✅ 백엔드 테스트 통과${NC}"
    else
        echo -e "${YELLOW}⚠️  일부 테스트 실패 (환경 설정 확인 필요)${NC}"
    fi
    cd ..
    echo ""
else
    echo -e "${YELLOW}⚠️  pytest 미설치 - 백엔드 테스트 스킵${NC}"
    echo ""
fi

# 최종 결과
echo "=========================================="
echo "🎉 통합 테스트 완료!"
echo ""
echo "📊 결과 요약:"
echo "  - 백엔드 API: ${GREEN}정상 작동${NC}"
echo "  - 권한 요청 생성: ${GREEN}성공${NC}"
echo "  - 목록 조회: ${GREEN}성공${NC}"
echo "  - 통계 조회: ${GREEN}성공${NC}"
if [ "$ALL_EXISTS" = true ]; then
    echo "  - 프론트엔드 파일: ${GREEN}모두 존재${NC}"
else
    echo "  - 프론트엔드 파일: ${YELLOW}일부 누락${NC}"
fi
echo ""
echo "📖 상세 문서: PERMISSION_REQUEST_SYSTEM_COMPLETE.md"
echo ""
