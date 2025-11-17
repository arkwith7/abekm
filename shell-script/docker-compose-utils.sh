#!/bin/bash

# Docker Compose 호환성 유틸리티 함수들
# 다양한 Docker Compose 버전(docker compose vs docker-compose)을 지원합니다.

# 명령어 캐시 (반복 감지 방지)
DOCKER_COMPOSE_CMD_CACHE="${DOCKER_COMPOSE_CMD_CACHE:-}"

# Docker Compose 명령어 자동 감지 및 설정
get_docker_compose_cmd() {
    if [[ -n "$DOCKER_COMPOSE_CMD_CACHE" ]]; then
        echo "$DOCKER_COMPOSE_CMD_CACHE"
        return 0
    fi

    # docker compose (Docker CLI plugin) 우선 확인
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD_CACHE="docker compose"
        echo "$DOCKER_COMPOSE_CMD_CACHE"
        return 0
    fi
    
    # docker-compose (standalone) 확인
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD_CACHE="docker-compose"
        echo "$DOCKER_COMPOSE_CMD_CACHE"
        return 0
    fi
    
    # 둘 다 없는 경우 오류
    echo "❌ Docker Compose를 찾을 수 없습니다. Docker 또는 docker-compose를 설치해주세요." >&2
    return 1
}

# Docker Compose 명령어 실행 래퍼 함수
docker_compose_run() {
    local compose_cmd
    if ! compose_cmd=$(get_docker_compose_cmd); then
        return 1
    fi

    # 명령어 실행
    $compose_cmd "$@"
}

# Docker Compose 명령어 출력 (디버깅용)
show_docker_compose_cmd() {
    local compose_cmd
    if ! compose_cmd=$(get_docker_compose_cmd); then
        return 1
    fi
    echo "ℹ️  Docker Compose 명령어: $compose_cmd"
}

# 사용 예시:
# source "$(dirname "$0")/docker-compose-utils.sh"
# show_docker_compose_cmd
# docker_compose_run up -d
# docker_compose_run ps
# docker_compose_run down