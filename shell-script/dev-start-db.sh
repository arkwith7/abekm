#!/bin/bash

# WKMS 개발용 데이터베이스 서비스 시작 스크립트
# PostgreSQL, Redis, pgAdmin만 실행합니다.

set -euo pipefail

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR"

# Docker Compose 호환성 유틸리티 로드
source "$(dirname "$0")/docker-compose-utils.sh"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

handle_error() {
    log_error "오류가 발생했습니다: $1"
    echo "📋 문제 해결 방법:"
    echo "   1. Docker가 실행 중인지 확인"
    echo "   2. 포트가 사용 중인지 확인"
    echo "   3. docker-compose.yml 파일 확인"
    exit 1
}

check_port() {
    local port=$1
    local service=$2
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_error "포트 $port가 이미 사용 중입니다. ($service)"
        echo "   다른 프로세스가 포트를 사용하고 있는지 확인하세요."
        exit 1
    fi
}

wait_for_postgres() {
    log_info "PostgreSQL 연결 확인 중..."
    local max_attempts=30
    local attempt=1

    while [ "$attempt" -le "$max_attempts" ]; do
        if docker_compose_run exec -T postgres pg_isready -U wkms -d wkms >/dev/null 2>&1; then
            log_success "PostgreSQL 연결 성공!"
            return 0
        fi

        echo "⏳ PostgreSQL 연결 대기 중... ($attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL 연결 실패"
    return 1
}

restart_services_if_needed() {
    # 기존 컨테이너가 있는지 확인 (실행 중이거나 중지된 상태 모두 포함)
    if docker ps -a --format '{{.Names}}' | grep -qE '^(abkms-postgres|abkms-redis|abkms-pgadmin)$'; then
        log_warning "기존 데이터베이스 컨테이너가 감지되었습니다."
        log_info "기존 컨테이너를 정리합니다..."
        
        # 컨테이너 중지 및 제거
        docker rm -f abkms-postgres abkms-redis abkms-pgadmin 2>/dev/null || true
        
        log_success "기존 컨테이너 정리 완료"
        sleep 2
    fi
}

main() {
    echo "=== WKMS 개발용 데이터베이스 서비스 시작 ==="
    echo "실행될 서비스:"
    echo "- PostgreSQL (포트: 5432)"
    echo "- Redis (포트: 6379)"
    echo "- pgAdmin (포트: 5050)"
    echo ""

    show_docker_compose_cmd

    log_info "포트 충돌 체크 중..."
    check_port 5432 "PostgreSQL"
    check_port 6379 "Redis"
    check_port 5050 "pgAdmin"
    log_success "포트 충돌 없음"

    restart_services_if_needed

    log_info "데이터베이스 서비스를 시작합니다..."
    docker_compose_run up -d postgres redis pgadmin || handle_error "서비스 시작 실패"

    wait_for_postgres || handle_error "PostgreSQL 연결 실패"

    log_info "서비스 상태 확인 중..."
    docker_compose_run ps postgres redis pgadmin

    log_success "개발용 데이터베이스 서비스가 성공적으로 시작되었습니다!"

    echo ""
    echo "📋 접속 정보:"
    echo "- PostgreSQL: localhost:5432"
    echo "  - 데이터베이스: wkms"
    echo "  - 사용자: wkms"
    echo "  - 비밀번호: wkms123"
    echo ""
    echo "- Redis: localhost:6379"
    echo ""
    echo "- pgAdmin: http://localhost:5050"
    echo "  - 이메일: admin@wkms.com"
    echo "  - 비밀번호: admin123"
    echo ""
}

main "$@"
