#!/bin/bash
# =============================================================================
# 문서 처리 데이터 초기화 실행 스크립트
# =============================================================================

set -e  # 오류 발생 시 중단

echo "================================================================================"
echo "🔧 WKMS 문서 처리 데이터 초기화"
echo "================================================================================"
echo ""
echo "⚠️  경고: 이 스크립트는 모든 문서 임베딩, 청킹, 추출 데이터를 삭제합니다!"
echo "📦 백업 옵션을 선택하면 데이터를 백업한 후 삭제합니다."
echo ""

# 데이터베이스 연결 정보
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-wkms}"
DB_USER="${DB_USER:-wkms}"

echo "📋 데이터베이스 연결 정보:"
echo "   Host: $DB_HOST"
echo "   Port: $DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo ""

# 사용자 확인
read -p "계속하시겠습니까? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ 초기화가 취소되었습니다."
    exit 0
fi

echo ""
echo "📦 백업 옵션 선택:"
echo "   1) 백업 없이 즉시 삭제 (빠름, 복구 불가)"
echo "   2) 백업 후 삭제 (안전, 복구 가능)"
echo ""
read -p "선택 (1 or 2): " backup_option

if [ "$backup_option" = "2" ]; then
    SQL_FILE="reset_document_data_with_backup.sql"
    echo "✅ 백업 포함 초기화를 실행합니다..."
else
    SQL_FILE="reset_document_data.sql"
    echo "⚠️  백업 없이 초기화를 실행합니다..."
fi

echo ""
echo "🚀 SQL 스크립트 실행 중..."
echo "================================================================================"

# PostgreSQL 비밀번호 입력 (환경변수에 없으면 프롬프트)
export PGPASSWORD="${DB_PASSWORD}"

# SQL 실행
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

echo ""
echo "================================================================================"
echo "✅ 초기화 완료!"
echo "================================================================================"

if [ "$backup_option" = "2" ]; then
    echo ""
    echo "📦 백업 테이블 확인:"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT 
            tablename as backup_table,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE tablename LIKE '%_backup_%'
        ORDER BY tablename;
    "
    echo ""
    echo "💡 백업 테이블 삭제 방법:"
    echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c \"DROP TABLE <backup_table_name>;\""
fi

echo ""
echo "🎯 다음 단계:"
echo "   1. 백엔드 서버 재시작"
echo "   2. 새로운 문서 업로드"
echo "   3. AWS Bedrock 환경으로 처리 확인"
echo ""
echo "================================================================================"
