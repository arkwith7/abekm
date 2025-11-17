#!/bin/bash
# WKMS 초기 데이터 적재 스크립트

set -e  # 오류 발생 시 즉시 종료

echo "🚀 WKMS 초기 데이터 적재를 시작합니다..."

# 환경 변수 설정
export DATABASE_URL=${DATABASE_URL:-"postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms"}
export REDIS_URL=${REDIS_URL:-"redis://localhost:6379"}

# 기본값 설정
RESET_DATA=${RESET_DATA:-false}
MAX_RETRIES=${MAX_RETRIES:-30}
RETRY_INTERVAL=${RETRY_INTERVAL:-5}

echo "📋 설정 정보:"
echo "  - DATABASE_URL: $DATABASE_URL"
echo "  - REDIS_URL: $REDIS_URL"
echo "  - RESET_DATA: $RESET_DATA"
echo "  - MAX_RETRIES: $MAX_RETRIES"

# 데이터베이스 연결 대기 함수
wait_for_database() {
    echo "🔄 데이터베이스 연결 대기 중..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        echo "  시도 $i/$MAX_RETRIES..."
        
        if python -c "
import asyncio
import asyncpg
import sys
import os

async def test_connection():
    try:
        # DATABASE_URL에서 연결 정보 추출
        db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms')
        # asyncpg 형식으로 변환 (postgresql+asyncpg:// -> postgresql://)
        asyncpg_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        conn = await asyncpg.connect(asyncpg_url)
        await conn.close()
        print('✅ 데이터베이스 연결 성공')
        return True
    except Exception as e:
        print(f'❌ 데이터베이스 연결 실패: {e}')
        return False

result = asyncio.run(test_connection())
sys.exit(0 if result else 1)
        " 2>/dev/null; then
            echo "✅ 데이터베이스 연결 성공!"
            return 0
        fi
        
        if [ $i -lt $MAX_RETRIES ]; then
            echo "  ⏳ ${RETRY_INTERVAL}초 후 재시도..."
            sleep $RETRY_INTERVAL
        fi
    done
    
    echo "❌ 데이터베이스 연결 실패 (최대 재시도 초과)"
    return 1
}

# Redis 연결 대기 함수  
wait_for_redis() {
    echo "🔄 Redis 연결 대기 중..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        echo "  시도 $i/$MAX_RETRIES..."
        
        if python -c "
import redis
import sys
import os
from urllib.parse import urlparse

try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    parsed = urlparse(redis_url)
    
    r = redis.Redis(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 6379,
        db=0,
        socket_connect_timeout=5
    )
    r.ping()
    print('✅ Redis 연결 성공')
    sys.exit(0)
except Exception as e:
    print(f'❌ Redis 연결 실패: {e}')
    sys.exit(1)
        " 2>/dev/null; then
            echo "✅ Redis 연결 성공!"
            return 0
        fi
        
        if [ $i -lt $MAX_RETRIES ]; then
            echo "  ⏳ ${RETRY_INTERVAL}초 후 재시도..."
            sleep $RETRY_INTERVAL
        fi
    done
    
    echo "❌ Redis 연결 실패 (최대 재시도 초과)"
    return 1
}

# 초기 데이터 적재 함수
run_initialization() {
    echo "🎯 초기 데이터 적재 실행 중..."
    
    cd /app
    
    if [ "$RESET_DATA" = "true" ]; then
        echo "⚠️  (구버전 비활성화) 전체 리셋 대신 새 시더 재실행"
    fi
    echo "📦 init_simple_database.py 실행 (역할/권한/카테고리 포함 최신 로직)"
    python init_simple_database.py
    
    if [ $? -eq 0 ]; then
        echo "🎉 초기 데이터 적재가 완료되었습니다!"
        
        echo ""
        echo "🔑 기본 로그인 정보:"
    echo "  🔐 시스템 관리자: admin / admin123!"
    echo "  👥 인사팀장: hr.manager / hr2025!"
    echo "  📋 채용담당: recruit / recruit123"
    echo "  🎓 교육담당: training / train2025"
        echo ""
        echo "🌐 서비스 접속:"
        echo "  📊 API 문서: http://localhost:8000/docs"
        echo "  🎨 프론트엔드: http://localhost:3000"
        echo "  🗄️  PgAdmin: http://localhost:5050"
        
        return 0
    else
        echo "❌ 초기 데이터 적재 실패"
        return 1
    fi
}

# 메인 실행 흐름
main() {
    echo "🏁 WKMS 초기화 프로세스 시작"
    
    # 1. 데이터베이스 연결 대기
    if ! wait_for_database; then
        echo "❌ 데이터베이스 연결 실패로 초기화를 중단합니다."
        exit 1
    fi
    
    # 2. Redis 연결 대기
    if ! wait_for_redis; then
        echo "❌ Redis 연결 실패로 초기화를 중단합니다."
        exit 1
    fi
    
    # 3. 초기 데이터 적재
    if ! run_initialization; then
        echo "❌ 초기 데이터 적재 실패"
        exit 1
    fi
    
    echo "✅ WKMS 초기화가 성공적으로 완료되었습니다!"
}

# 스크립트 실행
main "$@"
