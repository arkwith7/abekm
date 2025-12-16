#!/bin/bash
set -e

echo "=========================================="
echo "🚀 ABEKM Backend Starting..."
echo "=========================================="

# 환경 변수 확인
echo "📊 Environment:"
echo "  - DATABASE_URL: ${DATABASE_URL:0:30}..."
echo "  - POSTGRES_DB: ${POSTGRES_DB}"
echo "  - FORCE_DB_SEED: ${FORCE_DB_SEED:-false}"
echo ""

# PostgreSQL 준비 대기
echo "⏳ Waiting for PostgreSQL..."
max_retries=30
counter=0

while ! python3 -c "
import asyncpg
import asyncio
async def check():
    try:
        conn = await asyncpg.connect('$DATABASE_URL')
        await conn.close()
        return True
    except:
        return False
result = asyncio.run(check())
exit(0 if result else 1)
" 2>/dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $max_retries ]; then
        echo "❌ PostgreSQL 연결 실패 (타임아웃)"
        exit 1
    fi
    echo "  Attempt $counter/$max_retries..."
    sleep 2
done

echo "✅ PostgreSQL 연결 성공"
echo ""

# Alembic 마이그레이션 실행
echo "🔄 Running Alembic migrations..."
if alembic upgrade head 2>&1 | tee /tmp/alembic.log; then
    echo "✅ Alembic migrations 완료"
else
    echo "⚠️  Alembic migrations 실패 (계속 진행)"
    cat /tmp/alembic.log
fi
echo ""

# 데이터베이스 초기화 여부 확인
NEED_SEED=false

# FORCE_DB_SEED가 true면 무조건 시딩
if [ "$FORCE_DB_SEED" = "true" ]; then
    echo "🔧 FORCE_DB_SEED=true, 강제 시딩 수행"
    NEED_SEED=true
else
    # 필수 테이블이 비어있는지 확인
    echo "🔍 Checking if database needs seeding..."
    
    CHECK_RESULT=$(python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from app.core.database import get_async_engine
from sqlalchemy import text

async def check_empty():
    engine = get_async_engine()
    try:
        async with engine.begin() as conn:
            # 테이블 존재 여부 확인
            tables = ['tb_user', 'tb_user_roles', 'tb_user_permissions', 'tb_knowledge_categories']
            for table in tables:
                result = await conn.execute(text(f\"\"\"
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                    )
                \"\"\"))
                exists = result.scalar()
                if not exists:
                    print('NEED_SEED')
                    return
                
                # 테이블이 비어있는지 확인
                count_result = await conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = count_result.scalar()
                if count == 0:
                    print('NEED_SEED')
                    return
            
            print('NO_SEED')
    finally:
        await engine.dispose()

asyncio.run(check_empty())
" 2>/dev/null)
    
    if [ "$CHECK_RESULT" = "NEED_SEED" ]; then
        echo "  → 초기 데이터 필요"
        NEED_SEED=true
    else
        echo "  → 데이터 이미 존재"
    fi
fi
echo ""

# 데이터 시딩 실행
if [ "$NEED_SEED" = "true" ]; then
    echo "📦 Seeding database..."
    if python3 init_simple_database.py 2>&1 | tee /tmp/seed.log; then
        echo "✅ Database seeding 완료"
    else
        echo "❌ Database seeding 실패"
        cat /tmp/seed.log
        exit 1
    fi
else
    echo "⏭️  Database seeding 건너뛰기"
fi
echo ""

# FastAPI 서버 시작
echo "🚀 Starting FastAPI server..."
echo "=========================================="
# --loop asyncio: Celery kombu와의 충돌 방지 (uvloop 대신 asyncio 사용)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio --reload

