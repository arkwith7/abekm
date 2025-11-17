#!/bin/bash

# WKMS 시스템 완전 초기화 스크립트
# - Alembic 마이그레이션을 통한 스키마 생성
# - CSV 데이터를 활용한 마스터 데이터 로딩
# - 한국어 검색 확장 기능 통합

set -e  # 오류 발생 시 스크립트 중단

echo "🚀 WKMS 시스템 완전 초기화 시작..."
echo "=============================================="

# 1. 현재 디렉터리 확인
if [ ! -f "alembic.ini" ]; then
    echo "❌ backend 디렉터리에서 실행해주세요!"
    exit 1
fi

# 2. 가상환경 활성화 확인
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  가상환경이 활성화되지 않았습니다. .venv를 활성화합니다..."
    if [ -f "../.venv/bin/activate" ]; then
        source ../.venv/bin/activate
        echo "✅ 가상환경 활성화됨"
    else
        echo "❌ 가상환경을 찾을 수 없습니다!"
        exit 1
    fi
fi

# 3. PostgreSQL 연결 확인
echo "🔍 PostgreSQL 연결 확인 중..."
if ! docker exec wkms-postgres pg_isready -U wkms -d wkms > /dev/null 2>&1; then
    echo "❌ PostgreSQL 연결 실패! Docker 컨테이너를 확인해주세요."
    exit 1
fi
echo "✅ PostgreSQL 연결 확인됨"

# 4. 기존 Alembic 기록 확인 (선택사항)
read -p "🤔 기존 마이그레이션 히스토리를 초기화하시겠습니까? (y/N): " reset_migration
if [[ $reset_migration =~ ^[Yy]$ ]]; then
    echo "🗑️  Alembic 히스토리 초기화 중..."
    docker exec -it wkms-postgres psql -U wkms -d wkms -c "DROP TABLE IF EXISTS alembic_version CASCADE;" || true
    echo "   초기화 완료"
fi

# 5. Alembic 마이그레이션 실행
echo "📋 5단계: 데이터베이스 스키마 생성 중..."
echo "   Alembic 마이그레이션 실행..."
alembic upgrade head

if [ $? -ne 0 ]; then
    echo "❌ Alembic 마이그레이션 실패!"
    exit 1
fi
echo "✅ 데이터베이스 스키마 생성 완료"

# 6. 시드 데이터 로딩 여부 확인
read -p "🌱 마스터 데이터를 로딩하시겠습니까? (Y/n): " load_seeds
if [[ ! $load_seeds =~ ^[Nn]$ ]]; then
    echo "📊 6단계: 마스터 데이터 로딩 중..."
    
    # 자동으로 기존 데이터 삭제하고 새로운 데이터 로드
    echo "y" | python -m data.seeds.run_all_seeders
    
    if [ $? -ne 0 ]; then
        echo "❌ 시드 데이터 로딩 실패!"
        exit 1
    fi
    echo "✅ 마스터 데이터 로딩 완료"
else
    echo "⏭️  시드 데이터 로딩 건너뜀"
fi

# 7. 한국어 검색 확장 확인
echo "🔍 7단계: 한국어 검색 확장 확인 중..."
EXTENSIONS_COUNT=$(docker exec wkms-postgres psql -U wkms -d wkms -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname IN ('kor_search', 'pg_trgm', 'pgvector');" | tr -d ' ')

if [ "$EXTENSIONS_COUNT" -eq "3" ]; then
    echo "✅ 한국어 검색 확장 모두 설치됨"
else
    echo "⚠️  한국어 검색 확장이 부분적으로만 설치됨 ($EXTENSIONS_COUNT/3)"
    echo "   PostgreSQL 컨테이너 재시작을 권장합니다."
fi

# 8. 최종 상태 확인
echo "📊 8단계: 시스템 상태 최종 확인..."
echo "   데이터베이스 테이블 수:"
TABLE_COUNT=$(docker exec wkms-postgres psql -U wkms -d wkms -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
echo "      테이블: ${TABLE_COUNT}개"

echo "   주요 테이블 레코드 수:"
for table in "tb_user" "tb_sap_hr_info" "tb_cmns_cd_grp_item" "tb_knowledge_categories" "tb_knowledge_containers" "tb_user_permissions" "tb_user_roles"; do
    if docker exec wkms-postgres psql -U wkms -d wkms -t -c "SELECT 1 FROM information_schema.tables WHERE table_name = '$table';" | grep -q 1; then
        COUNT=$(docker exec wkms-postgres psql -U wkms -d wkms -t -c "SELECT COUNT(*) FROM $table;" | tr -d ' ')
        echo "      $table: ${COUNT}개"
    else
        echo "      $table: 테이블 없음"
    fi
done

# 9. 완료 메시지
echo "=============================================="
echo "🎉 WKMS 시스템 초기화 완료!"
echo "=============================================="
echo ""
echo "📋 다음 단계:"
echo "   1. 백엔드 서버 시작: uvicorn app.main:app --reload"
echo "   2. 프론트엔드 서버 시작: cd ../frontend && npm start"  
echo "   3. 로그인 테스트: ms.staff / password123"
echo ""
echo "🔧 관리자 계정:"
echo "   사번: 10000001"
echo "   사용자명: admin"
echo "   비밀번호: password123"
echo ""
echo "📚 참고 문서:"
echo "   - 데이터 구조: backend/data/README.md"
echo "   - 시드 관리: python -m data.seeds.run_all_seeders"
echo "   - 마이그레이션: alembic upgrade head"
echo ""