#!/bin/bash
# 프로바이더별 동적 필터링 검증 스크립트
# .env의 DEFAULT_EMBEDDING_PROVIDER 설정에 따라 올바른 문서만 조회되는지 테스트

set -e

echo "=========================================="
echo "🧪 프로바이더 동적 필터링 검증 시작"
echo "=========================================="

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 현재 .env 설정 확인
echo ""
echo "📋 현재 .env 설정 확인:"
grep "^DEFAULT_EMBEDDING_PROVIDER=" backend/.env || echo "  ⚠️  DEFAULT_EMBEDDING_PROVIDER 설정 없음"
grep "^DEFAULT_LLM_PROVIDER=" backend/.env || echo "  ⚠️  DEFAULT_LLM_PROVIDER 설정 없음"

# DB 상태 확인
echo ""
echo "=========================================="
echo "📊 데이터베이스 상태 확인"
echo "=========================================="

echo ""
echo "1️⃣  doc_extraction_session 테이블의 pipeline_type 분포:"
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
SELECT 
    pipeline_type, 
    provider,
    status,
    COUNT(*) as count 
FROM doc_extraction_session 
GROUP BY pipeline_type, provider, status 
ORDER BY count DESC;
" 2>/dev/null || echo -e "${RED}❌ DB 조회 실패${NC}"

echo ""
echo "2️⃣  doc_embedding 테이블의 provider/model 분포:"
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
SELECT 
    provider, 
    model_name, 
    dimension, 
    COUNT(*) as count 
FROM doc_embedding 
GROUP BY provider, model_name, dimension 
ORDER BY count DESC;
" 2>/dev/null || echo -e "${RED}❌ DB 조회 실패${NC}"

echo ""
echo "3️⃣  tb_file_bss_info 테이블의 processing_status 분포:"
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
SELECT 
    processing_status, 
    COUNT(*) as count 
FROM tb_file_bss_info 
WHERE del_yn != 'Y'
GROUP BY processing_status 
ORDER BY count DESC;
" 2>/dev/null || echo -e "${RED}❌ DB 조회 실패${NC}"

# provider_filters.py 유틸 동작 확인
echo ""
echo "=========================================="
echo "🔧 provider_filters.py 유틸 동작 확인"
echo "=========================================="

echo ""
echo "4️⃣  현재 프로바이더 설정 요약:"
python3 - <<'EOF'
import sys
sys.path.insert(0, 'backend')

try:
    from app.utils.provider_filters import get_provider_summary, get_current_provider_pipeline_types
    
    summary = get_provider_summary()
    print(f"  - 임베딩 프로바이더: {summary['embedding_provider']}")
    print(f"  - 허용 pipeline_type: {summary['allowed_pipelines']}")
    print(f"  - 임베딩 모델: {summary['embedding_model']}")
    print(f"  - 임베딩 차원: {summary['embedding_dimension']}d")
    print(f"  - Storage: {summary['storage_backend']} ({summary['storage_bucket']})")
    print(f"  - 멀티모달 활성화: {summary['multimodal_enabled']}")
    if summary['multimodal_enabled']:
        print(f"  - 멀티모달 모델: {summary['multimodal_model']}")
        print(f"  - 멀티모달 차원: {summary['multimodal_dimension']}d")
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ provider_filters.py 정상 동작${NC}"
else
    echo -e "${RED}❌ provider_filters.py 오류 발생${NC}"
    exit 1
fi

# 프로바이더별 필터링 테스트
echo ""
echo "=========================================="
echo "🧪 프로바이더별 필터링 SQL 테스트"
echo "=========================================="

echo ""
echo "5️⃣  Bedrock 환경 시뮬레이션 - 허용 문서 조회:"
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
-- Bedrock 환경: pipeline_type IN ('bedrock', 'upstage')
SELECT 
    f.file_bss_info_sno,
    f.file_lgc_nm,
    f.processing_status,
    e.pipeline_type,
    e.status
FROM tb_file_bss_info f
LEFT JOIN doc_extraction_session e ON f.file_bss_info_sno = e.file_bss_info_sno
WHERE f.del_yn != 'Y'
  AND (
    (e.pipeline_type IN ('bedrock', 'upstage') AND e.status = 'success')
    OR f.processing_status IN ('pending', 'processing')
  )
ORDER BY f.created_date DESC
LIMIT 5;
" 2>/dev/null || echo -e "${RED}❌ SQL 테스트 실패${NC}"

echo ""
echo "6️⃣  Azure 환경 시뮬레이션 - 허용 문서 조회:"
docker exec -it abkms-postgres psql -U wkms -d wkms -c "
-- Azure 환경: pipeline_type IN ('azure_di', 'azure_openai')
SELECT 
    f.file_bss_info_sno,
    f.file_lgc_nm,
    f.processing_status,
    e.pipeline_type,
    e.status
FROM tb_file_bss_info f
LEFT JOIN doc_extraction_session e ON f.file_bss_info_sno = e.file_bss_info_sno
WHERE f.del_yn != 'Y'
  AND (
    (e.pipeline_type IN ('azure_di', 'azure_openai') AND e.status = 'success')
    OR f.processing_status IN ('pending', 'processing')
  )
ORDER BY f.created_date DESC
LIMIT 5;
" 2>/dev/null || echo -e "${RED}❌ SQL 테스트 실패${NC}"

# Storage 검증 테스트
echo ""
echo "=========================================="
echo "💾 Storage 경로 검증 테스트"
echo "=========================================="

echo ""
echo "7️⃣  Storage 경로 유효성 검사:"
python3 - <<'EOF'
import sys
sys.path.insert(0, 'backend')

try:
    from app.utils.provider_filters import is_valid_storage_for_provider
    
    test_cases = [
        ("bedrock", "raw/USER_123/file.pdf", True),
        ("bedrock", "https://account.blob.core.windows.net/container/file.pdf", False),
        ("azure_openai", "https://account.blob.core.windows.net/container/file.pdf", True),
        ("azure_openai", "raw/USER_123/file.pdf", False),
    ]
    
    all_passed = True
    for provider, path, expected in test_cases:
        result = is_valid_storage_for_provider(path, provider)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"  {status} {provider:15} | {path:50} | Expected: {expected}, Got: {result}")
    
    if all_passed:
        print("\n✅ 모든 Storage 검증 테스트 통과")
    else:
        print("\n❌ 일부 테스트 실패")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Storage 검증 통과${NC}"
else
    echo -e "${RED}❌ Storage 검증 실패${NC}"
    exit 1
fi

# 최종 요약
echo ""
echo "=========================================="
echo "📊 검증 요약"
echo "=========================================="

echo ""
echo "✅ 완료된 검증 항목:"
echo "  1. .env 설정 확인"
echo "  2. DB 테이블 상태 확인"
echo "  3. provider_filters.py 유틸 동작"
echo "  4. 프로바이더별 SQL 필터링"
echo "  5. Storage 경로 검증"

echo ""
echo "🎯 다음 단계:"
echo "  1. 백엔드 재시작: ./shell-script/dev-start-backend.sh"
echo "  2. 대시보드 API 테스트: curl localhost:8000/api/v1/dashboard/recent-documents"
echo "  3. 문서 목록 API 테스트: curl localhost:8000/api/v1/documents"
echo "  4. .env에서 DEFAULT_EMBEDDING_PROVIDER 변경 후 재테스트"

echo ""
echo -e "${GREEN}=========================================="
echo "🎉 프로바이더 동적 필터링 검증 완료"
echo "==========================================${NC}"
