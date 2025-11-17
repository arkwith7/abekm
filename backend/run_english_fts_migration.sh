#!/bin/bash
# 영어 FTS 마이그레이션 실행 스크립트

set -e  # 오류 발생 시 중단

echo "🚀 영어 전문검색(FTS) 마이그레이션 시작"
echo "========================================"
echo ""

# 현재 디렉토리를 backend로 변경
cd "$(dirname "$0")"

echo "📍 현재 디렉토리: $(pwd)"
echo ""

# 가상환경 활성화
VENV_PATH="../.venv"
if [ -d "$VENV_PATH" ]; then
    echo "✅ Python 가상환경 활성화: $VENV_PATH"
    source "$VENV_PATH/bin/activate"
    echo "   - Python: $(which python)"
    echo "   - Alembic: $(which alembic)"
else
    echo "⚠️  가상환경 없음 - 시스템 Python 사용"
fi
echo ""

# 환경변수 로드 (backend/.env 사용)
if [ -f .env ]; then
    echo "✅ backend/.env 파일에서 설정 로드"
    export DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d '=' -f2)
    
    # DATABASE_URL에서 DB 정보 추출 (alembic/env.py가 사용)
    if [ -n "$DATABASE_URL" ]; then
        echo "   - DATABASE_URL: ${DATABASE_URL}"
    else
        echo "⚠️  DATABASE_URL이 설정되지 않았습니다!"
    fi
else
    echo "⚠️  backend/.env 파일 없음"
    exit 1
fi

echo ""
echo "📊 데이터베이스 연결:"
echo "  - URL: ${DATABASE_URL}"
echo ""

# Alembic 버전 확인
echo "🔍 현재 Alembic 마이그레이션 상태 확인..."
alembic current
echo ""

# Alembic 히스토리 확인 (최근 5개)
echo "📜 최근 마이그레이션 히스토리:"
alembic history -r -5: 2>/dev/null || alembic history | tail -10
echo ""

# 마이그레이션 실행 확인
read -p "⚡ doc_chunk 테이블에 영어 FTS를 추가하시겠습니까? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 마이그레이션 취소됨"
    exit 0
fi

echo ""
echo "🔧 마이그레이션 실행 중..."
echo "  - Revision: 20251106_001_add_english_fts_to_doc_chunk"
echo "  - 작업: doc_chunk 테이블에 content_tsvector 컬럼 추가"
echo ""

# Alembic 마이그레이션 실행 (가상환경의 alembic 사용)
alembic upgrade head

echo ""
echo "✅ 마이그레이션 완료!"
echo ""

# 마이그레이션 후 상태 확인
echo "🔍 마이그레이션 후 상태 확인..."
alembic current
echo ""

# DB 검증 쿼리 실행 (가상환경의 python 사용)
echo "🔍 데이터베이스 검증 중..."
python <<EOF
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def verify_migration():
    # DB 연결
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'wkms')
    db_password = os.getenv('DB_PASSWORD', 'wkms123')
    db_name = os.getenv('DB_NAME', 'wkms')
    db_port = os.getenv('DB_PORT', '5432')
    
    database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_async_engine(database_url, echo=False)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. content_tsvector 컬럼 존재 확인
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'doc_chunk' 
            AND column_name = 'content_tsvector'
        """))
        row = result.fetchone()
        
        if row:
            print(f"✅ content_tsvector 컬럼 확인: {row[0]} ({row[1]})")
        else:
            print("❌ content_tsvector 컬럼이 없습니다!")
            return False
        
        # 2. 인덱스 확인
        result = await session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'doc_chunk' 
            AND indexname = 'idx_doc_chunk_content_tsvector'
        """))
        row = result.fetchone()
        
        if row:
            print(f"✅ GIN 인덱스 확인: {row[0]}")
        else:
            print("❌ GIN 인덱스가 없습니다!")
            return False
        
        # 3. 트리거 함수 확인
        result = await session.execute(text("""
            SELECT proname 
            FROM pg_proc 
            WHERE proname = 'update_doc_chunk_content_tsvector'
        """))
        row = result.fetchone()
        
        if row:
            print(f"✅ 트리거 함수 확인: {row[0]}()")
        else:
            print("❌ 트리거 함수가 없습니다!")
            return False
        
        # 4. 트리거 확인
        result = await session.execute(text("""
            SELECT tgname 
            FROM pg_trigger 
            WHERE tgname = 'trig_update_doc_chunk_content_tsvector'
        """))
        row = result.fetchone()
        
        if row:
            print(f"✅ 트리거 확인: {row[0]}")
        else:
            print("❌ 트리거가 없습니다!")
            return False
        
        # 5. 데이터 마이그레이션 확인
        result = await session.execute(text("""
            SELECT 
                COUNT(*) as total_chunks,
                COUNT(content_tsvector) as indexed_chunks,
                ROUND(COUNT(content_tsvector)::numeric / NULLIF(COUNT(*), 0) * 100, 2) as completion_pct
            FROM doc_chunk
        """))
        row = result.fetchone()
        
        print(f"✅ 데이터 마이그레이션 확인:")
        print(f"   - 전체 청크: {row[0]:,}개")
        print(f"   - 인덱싱된 청크: {row[1]:,}개")
        print(f"   - 완료율: {row[2]}%")
        
        # 6. 샘플 검색 테스트 (영어)
        result = await session.execute(text("""
            SELECT 
                chunk_id,
                LEFT(content_text, 100) as preview,
                content_tsvector @@ to_tsquery('english', 'leadership') as matches_en,
                content_tsvector @@ to_tsquery('korean', '리더십') as matches_ko
            FROM doc_chunk
            WHERE content_tsvector IS NOT NULL
            AND (
                content_tsvector @@ to_tsquery('english', 'leadership')
                OR content_tsvector @@ to_tsquery('korean', '리더십')
            )
            LIMIT 3
        """))
        rows = result.fetchall()
        
        if rows:
            print(f"✅ 샘플 검색 테스트 (영어 'leadership' / 한국어 '리더십'):")
            for i, row in enumerate(rows, 1):
                print(f"   {i}. Chunk ID {row[0]}: EN={row[2]}, KO={row[3]}")
                print(f"      Preview: {row[1]}...")
        else:
            print("⚠️  샘플 검색 결과 없음 (데이터가 없거나 매칭되는 내용 없음)")
        
        print("")
        print("🎉 모든 검증 통과!")
        return True
    
    await engine.dispose()

# 실행
asyncio.run(verify_migration())
EOF

echo ""
echo "✅ 영어 FTS 마이그레이션 및 검증 완료!"
echo ""
echo "📝 다음 단계:"
echo "  1. 백엔드 서버 재시작"
echo "  2. 영어 논문으로 RAG 검색 테스트"
echo "  3. 로그에서 '🌐 쿼리 언어 감지' 확인"
echo ""
