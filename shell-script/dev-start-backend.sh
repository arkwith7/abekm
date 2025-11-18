#!/bin/bash

# WKMS 백엔드 개발 서버 시작 스크립트
# 가상환경 활성화, Redis, Celery Worker, FastAPI 서버 실행

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR/backend"

echo "==================================================================="
echo "   WKMS 백엔드 개발 서버 시작 (비동기 업로드 지원)"
echo "==================================================================="
echo ""

# 가상환경이 활성화되어 있는지 확인 (절대경로 사용)
VENV_PATH="$REPO_ROOT_DIR/.venv"
if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
    echo "❌ 가상환경을 찾을 수 없습니다: $VENV_PATH"
    exit 1
fi

if [[ "${VIRTUAL_ENV:-}" != "$VENV_PATH" ]]; then
    echo "🔧 가상환경을 활성화합니다..."
    source "$VENV_PATH/bin/activate"
fi

PYTHON_CMD="$VENV_PATH/bin/python"
PIP_CMD="$VENV_PATH/bin/pip"
CELERY_BIN="$VENV_PATH/bin/celery"

echo "✅ Python 환경: $PYTHON_CMD"
echo ""

# 필수 의존성 설치 확인
echo "📦 필수 의존성을 확인하고 설치합니다..."
"$PIP_CMD" install PyJWT==2.8.0 passlib[bcrypt]==1.7.4 python-multipart==0.0.12 celery==5.3.4 redis==5.0.1 > /dev/null 2>&1 || true
echo ""

# PID 파일 저장 디렉토리 및 로그 디렉토리 생성
PID_DIR="$REPO_ROOT_DIR/tmp/pids"
LOG_DIR="$REPO_ROOT_DIR/logs"
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# 종료 시 자식 프로세스 정리 함수
cleanup() {
    echo ""
    echo "🛑 서버를 종료합니다..."
    
    # Celery Worker 종료
    if [ -f "$PID_DIR/celery.pid" ]; then
        CELERY_PID=$(cat "$PID_DIR/celery.pid")
        if ps -p $CELERY_PID > /dev/null 2>&1; then
            echo "   - Celery Worker 종료 (PID: $CELERY_PID)"
            kill $CELERY_PID 2>/dev/null || true
        fi
        rm -f "$PID_DIR/celery.pid"
    fi
    
    # FastAPI 서버 종료
    if [ -f "$PID_DIR/fastapi.pid" ]; then
        FASTAPI_PID=$(cat "$PID_DIR/fastapi.pid")
        if ps -p $FASTAPI_PID > /dev/null 2>&1; then
            echo "   - FastAPI 서버 종료 (PID: $FASTAPI_PID)"
            kill $FASTAPI_PID 2>/dev/null || true
        fi
        rm -f "$PID_DIR/fastapi.pid"
    fi
    
    echo "✅ 모든 서비스가 종료되었습니다."
    exit 0
}

# SIGINT, SIGTERM 시그널 캐치
trap cleanup SIGINT SIGTERM

# Redis 연결 확인
echo "🔍 Redis 서버 연결 확인..."
# redis-cli 대신 Docker 컨테이너나 Python으로 확인
if docker exec abkms-redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis 서버 연결됨 (Docker 컨테이너: abkms-redis)"
    REDIS_AVAILABLE=true
elif python -c "import redis; r=redis.Redis(host='localhost', port=6379); r.ping()" 2>/dev/null; then
    echo "✅ Redis 서버 연결됨 (localhost:6379)"
    REDIS_AVAILABLE=true
else
    echo "⚠️  Redis 서버가 실행되지 않았습니다."
    echo ""
    echo "Redis를 시작하는 방법:"
    echo "  스크립트: ./shell-script/dev-start-db.sh"
    echo "  Docker:   docker run -d --name redis -p 6379:6379 redis:latest"
    echo ""
    read -p "Redis 없이 계속하시겠습니까? (비동기 업로드 비활성화) [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 종료합니다."
        exit 1
    fi
    REDIS_AVAILABLE=false
fi
echo ""

# Celery Worker 시작 (Redis가 있을 때만)
if [ "$REDIS_AVAILABLE" = true ]; then
    echo "🚀 Celery Worker를 시작합니다..."
    
    # Celery가 설치되어 있는지 확인
    if [ ! -x "$CELERY_BIN" ]; then
        echo "⚠️  Celery가 설치되어 있지 않습니다."
        echo "   비동기 업로드 기능을 사용하려면 설치하세요: pip install celery"
        echo "   계속 진행합니다 (Celery 없이)..."
        REDIS_AVAILABLE=false
    else
        # 절대 경로로 명확하게 지정
        CELERY_LOG="$LOG_DIR/celery.log"
        CELERY_PID="$PID_DIR/celery.pid"
        
        # 기존 PID 파일이 남아 있으면 삭제
        rm -f "$CELERY_PID"

        "$CELERY_BIN" -A app.core.celery_app worker \
            --loglevel=info \
            --logfile="$CELERY_LOG" \
            --detach \
            --pidfile="$CELERY_PID" 2>/dev/null || {
            echo "⚠️  Celery Worker 시작 실패 (계속 진행)"
            REDIS_AVAILABLE=false
        }
        
        # PID 파일 생성 대기 (최대 5초)
        if [ "$REDIS_AVAILABLE" = true ]; then
            for i in {1..10}; do
                if [ -f "$CELERY_PID" ]; then
                    CELERY_PID_VALUE=$(cat "$CELERY_PID")
                    # 프로세스가 실제로 실행 중인지 확인
                    if ps -p $CELERY_PID_VALUE > /dev/null 2>&1; then
                        echo "✅ Celery Worker 시작됨 (PID: $CELERY_PID_VALUE)"
                        echo "   로그: logs/celery.log"
                        break
                    fi
                fi
                sleep 0.5
            done
            
            # 최종 확인
            if [ ! -f "$CELERY_PID" ] || ! ps -p $(cat "$CELERY_PID") > /dev/null 2>&1; then
                echo "⚠️  Celery Worker 시작 실패 (계속 진행)"
                echo "   수동 확인: tail -f $CELERY_LOG"
            fi
        fi
    fi
    echo ""
fi

# FastAPI 개발 서버 시작
echo "🚀 FastAPI 개발 서버를 시작합니다..."
echo "-------------------------------------------------------------------"
echo "   📍 API 서버:     http://localhost:8000"
echo "   📚 API 문서:     http://localhost:8000/docs"
echo "   🔄 Swagger UI:   http://localhost:8000/docs"
echo "   📖 ReDoc:        http://localhost:8000/redoc"
if [ "$REDIS_AVAILABLE" = true ]; then
    echo "   🌸 Flower:       http://localhost:5555 (선택: celery -A app.core.celery_app flower)"
    echo "   ✅ 비동기 업로드: 활성화"
else
    echo "   ❌ 비동기 업로드: 비활성화 (Redis 필요)"
fi
echo "-------------------------------------------------------------------"
echo ""
echo "💡 서버를 중지하려면 Ctrl+C를 누르세요."
echo ""

# FastAPI 서버 실행 (백그라운드, nest_asyncio 호환을 위해 asyncio loop 사용)
"$PYTHON_CMD" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio &
FASTAPI_PID=$!
echo $FASTAPI_PID > "$PID_DIR/fastapi.pid"

echo "✅ FastAPI 서버 시작됨 (PID: $FASTAPI_PID)"
echo ""

# 서버가 실행 중인지 확인
sleep 2
if ps -p $FASTAPI_PID > /dev/null 2>&1; then
    echo "🎉 모든 서비스가 정상적으로 시작되었습니다!"
    echo ""
    
    # 로그 출력 (실시간)
    echo "📋 FastAPI 로그를 표시합니다 (Ctrl+C로 종료):"
    echo "==================================================================="
    
    # FastAPI 프로세스가 종료될 때까지 대기
    wait $FASTAPI_PID
else
    echo "❌ FastAPI 서버 시작 실패"
    cleanup
fi
