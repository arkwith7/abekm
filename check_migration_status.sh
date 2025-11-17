#!/bin/bash
# =============================================================================
# AWS 환경 마이그레이션 상태 확인 스크립트
# =============================================================================

echo "================================================================================"
echo "🔍 WKMS AWS 마이그레이션 상태 확인"
echo "================================================================================"
echo ""

# 데이터베이스 연결 정보
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-wkms}"
DB_USER="${DB_USER:-wkms}"
export PGPASSWORD="${DB_PASSWORD}"

echo "📋 데이터베이스: $DB_NAME@$DB_HOST:$DB_PORT"
echo ""

# 1. Azure 데이터 확인
echo "================================================================================"
echo "1️⃣  Azure 기반 데이터 확인"
echo "================================================================================"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f check_azure_data.sql

echo ""
echo ""

# 2. 현재 백엔드 설정 확인
echo "================================================================================"
echo "2️⃣  백엔드 환경 설정 확인"
echo "================================================================================"

if [ -f "backend/.env" ]; then
    echo "📄 현재 .env 설정:"
    echo ""
    
    echo "🌩️  클라우드 Provider:"
    grep -E "^DEFAULT_LLM_PROVIDER|^DEFAULT_EMBEDDING_PROVIDER" backend/.env | sed 's/^/   /'
    
    echo ""
    echo "🤖 LLM 모델:"
    grep -E "^BEDROCK_LLM_MODEL_ID" backend/.env | sed 's/^/   /'
    
    echo ""
    echo "📊 임베딩 모델:"
    grep -E "^BEDROCK_EMBEDDING_MODEL_ID|^BEDROCK_EMBEDDING_DIMENSION" backend/.env | sed 's/^/   /'
    
    echo ""
    echo "🎨 멀티모달 모델:"
    grep -E "^BEDROCK_MULTIMODAL" backend/.env | sed 's/^/   /'
    
    echo ""
    echo "📄 문서 처리:"
    grep -E "^DOCUMENT_PROCESSING_PROVIDER|^DOCUMENT_PROCESSING_FALLBACK" backend/.env | sed 's/^/   /'
    
else
    echo "⚠️  backend/.env 파일을 찾을 수 없습니다."
fi

echo ""
echo ""

# 3. 권장 조치사항
echo "================================================================================"
echo "3️⃣  권장 조치사항"
echo "================================================================================"
echo ""

# Azure 데이터 확인
AZURE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
    SELECT COUNT(*) FROM doc_embedding 
    WHERE provider IN ('azure', 'azure_openai') 
       OR model_name LIKE '%text-embedding-3%'
       OR model_name LIKE '%azure%';
" 2>/dev/null | tr -d ' ')

if [ -n "$AZURE_COUNT" ] && [ "$AZURE_COUNT" -gt 0 ]; then
    echo "⚠️  Azure 기반 데이터가 ${AZURE_COUNT}개 발견되었습니다."
    echo ""
    echo "📋 권장 조치:"
    echo "   1. 데이터베이스 초기화 스크립트 실행"
    echo "      ./reset_document_data.sh"
    echo ""
    echo "   2. 백엔드 재시작"
    echo "      ./shell-script/dev-start-backend.sh"
    echo ""
    echo "   3. 새로운 문서 업로드하여 AWS 환경 테스트"
    echo ""
else
    echo "✅ Azure 기반 데이터가 발견되지 않았습니다."
    echo "✅ 시스템이 AWS 환경으로 정상 전환되었습니다."
    echo ""
fi

# 백엔드 실행 여부 확인
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "🟢 백엔드 서버가 실행 중입니다."
else
    echo "🔴 백엔드 서버가 실행되지 않았습니다."
    echo "   시작 명령: ./shell-script/dev-start-backend.sh"
fi

echo ""
echo "================================================================================"
echo "📚 추가 정보"
echo "================================================================================"
echo ""
echo "📖 관련 스크립트:"
echo "   - check_azure_data.sql          : Azure 데이터 상세 분석"
echo "   - check_document_data.sql       : 전체 문서 데이터 상태 확인"
echo "   - reset_document_data.sh        : 데이터베이스 초기화"
echo "   - reset_document_data.sql       : 빠른 초기화 (백업 없음)"
echo "   - reset_document_data_with_backup.sql : 안전한 초기화 (백업 포함)"
echo ""
echo "📝 환경 설정:"
echo "   - backend/.env                  : 백엔드 환경 변수"
echo "   - UPSTAGE_INTEGRATION_FLOW_REPORT.md : Upstage 통합 가이드"
echo ""
echo "================================================================================"
