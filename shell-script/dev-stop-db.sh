#!/bin/bash

# WKMS 개발용 데이터베이스 서비스 중지 스크립트
# PostgreSQL, Redis, pgAdmin을 중지합니다.

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

main() {
    echo "=== WKMS 개발용 데이터베이스 서비스 중지 ==="
    echo "중지될 서비스:"
    echo "- PostgreSQL"
    echo "- Redis" 
    echo "- pgAdmin"
    echo ""

    # Docker Compose 명령어 확인
    show_docker_compose_cmd

    local targets=(postgres redis pgadmin)
    local container_names=(abkms-postgres abkms-redis abkms-pgadmin)

    # 실행 중인 서비스 확인
    log_info "현재 실행 중인 서비스 확인..."
    mapfile -t running_services < <(docker_compose_run ps --services --filter status=running "${targets[@]}" 2>/dev/null || true)
    mapfile -t running_containers < <(docker ps --filter "name=^/(abkms-postgres|abkms-redis|abkms-pgadmin)$" --format '{{.Names}}' 2>/dev/null || true)

    if ((${#running_services[@]} > 0)); then
        log_info "Compose 기준 실행 중인 서비스: ${running_services[*]}"
    fi

    if ((${#running_containers[@]} > 0)); then
        log_info "Docker 기준 실행 중인 컨테이너: ${running_containers[*]}"
    else
        log_info "실행 중인 데이터베이스 서비스가 없습니다. 그래도 안전하게 중지 명령을 실행합니다."
    fi

    if docker_compose_run stop "${targets[@]}"; then
        log_success "Docker Compose 서비스 중지 완료"
    else
        log_warning "Docker Compose 서비스 중지 중 오류가 발생했습니다."
    fi

    mapfile -t leftover_containers < <(docker ps --filter "name=^/(abkms-postgres|abkms-redis|abkms-pgadmin)$" --format '{{.Names}}' 2>/dev/null || true)
    if ((${#leftover_containers[@]} > 0)); then
        log_info "직접 Docker 컨테이너 중지도 시도합니다..."
        if docker stop "${leftover_containers[@]}" >/dev/null 2>&1; then
            log_success "Docker 컨테이너 중지 완료"
        else
            log_warning "일부 Docker 컨테이너 중지 중 오류가 발생했습니다."
        fi
    fi

    # 잔여 컨테이너 정리 (이름 충돌 방지)
    if ! docker_compose_run rm -f "${targets[@]}" >/dev/null 2>&1; then
        log_warning "Docker Compose 컨테이너 정리 중 일부 오류가 발생했습니다."
    fi
    mapfile -t removable_containers < <(docker ps -a --filter "name=^/(abkms-postgres|abkms-redis|abkms-pgadmin)$" --format '{{.Names}}' 2>/dev/null || true)
    if ((${#removable_containers[@]} > 0)) && ! docker rm -f "${removable_containers[@]}" >/dev/null 2>&1; then
        log_warning "일부 Docker 컨테이너 정리 중 오류가 발생했지만 계속 진행합니다."
    fi

    echo ""
    log_info "현재 서비스 상태:"
    docker_compose_run ps "${targets[@]}"

    echo ""
    log_success "개발용 데이터베이스 서비스 중지 완료!"
    echo ""
    echo "💡 추가 옵션:"
    local compose_cmd
    if compose_cmd=$(get_docker_compose_cmd); then
        echo "   컨테이너 완전 제거: $compose_cmd down"
    else
        echo "   컨테이너 완전 제거: docker compose down"
    fi
    echo "   또는:              ./shell-script/dev-clean-db.sh (전체 정리)"
    echo ""
}

main "$@"
