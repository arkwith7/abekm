#!/usr/bin/env bash
set -euo pipefail

# 전체 Docker 환경 초기화 및 재배포 스크립트
# Usage: ./shell-script/reset-and-deploy.sh [dev|prod]

ENVIRONMENT="${1:-prod}"
REPO_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Docker 환경 전체 초기화 및 재배포"
echo "환경: $ENVIRONMENT"
echo "=========================================="
echo ""

# 환경에 따른 compose 파일 선택
if [ "$ENVIRONMENT" = "dev" ]; then
  COMPOSE_FILE="docker-compose.dev.yml"
else
  COMPOSE_FILE="docker-compose.prod.yml"
fi

# 확인
echo "⚠️  다음 작업이 수행됩니다:"
echo "  1. 모든 컨테이너 중지 및 삭제"
echo "  2. 모든 이미지 삭제"
echo "  3. 모든 볼륨 삭제 (데이터 손실!)"
echo "  4. 네트워크 삭제"
echo "  5. 새로 빌드 및 시작"
echo ""
read -p "계속하시겠습니까? (yes/no): " -r
echo
if [[ ! $REPLY = "yes" ]]; then
  echo "취소되었습니다."
  exit 0
fi

echo ""
echo "=========================================="
echo "Step 1: 모든 컨테이너 중지 및 삭제"
echo "=========================================="
# 모든 실행 중인 컨테이너 중지
if [ "$(docker ps -q)" ]; then
  echo "실행 중인 컨테이너 중지..."
  docker stop $(docker ps -q)
fi

# 모든 컨테이너 삭제
if [ "$(docker ps -aq)" ]; then
  echo "모든 컨테이너 삭제..."
  docker rm -f $(docker ps -aq)
fi
echo "✅ 컨테이너 정리 완료"
echo ""

echo "=========================================="
echo "Step 2: abkms 관련 이미지 삭제"
echo "=========================================="
ABKMS_IMAGES=$(docker images --filter=reference='abkms-*' -q)
if [ -n "$ABKMS_IMAGES" ]; then
  echo "abkms 이미지 삭제..."
  docker rmi -f $ABKMS_IMAGES
else
  echo "삭제할 abkms 이미지 없음"
fi
echo "✅ 이미지 정리 완료"
echo ""

echo "=========================================="
echo "Step 3: 볼륨 삭제"
echo "=========================================="
ABKMS_VOLUMES=$(docker volume ls --filter=name=abkms -q)
if [ -n "$ABKMS_VOLUMES" ]; then
  echo "⚠️  다음 볼륨이 삭제됩니다 (데이터 손실!):"
  docker volume ls --filter=name=abkms
  echo ""
  read -p "볼륨을 삭제하시겠습니까? (yes/no): " -r
  echo
  if [[ $REPLY = "yes" ]]; then
    docker volume rm $ABKMS_VOLUMES
    echo "✅ 볼륨 삭제 완료"
  else
    echo "볼륨은 유지됩니다"
  fi
else
  echo "삭제할 볼륨 없음"
fi
echo ""

echo "=========================================="
echo "Step 4: 네트워크 삭제"
echo "=========================================="
ABKMS_NETWORKS=$(docker network ls --filter=name=abkms -q)
if [ -n "$ABKMS_NETWORKS" ]; then
  echo "abkms 네트워크 삭제..."
  docker network rm $ABKMS_NETWORKS || true
else
  echo "삭제할 네트워크 없음"
fi
echo "✅ 네트워크 정리 완료"
echo ""

echo "=========================================="
echo "Step 5: 빌드 캐시 정리 (선택)"
echo "=========================================="
read -p "Docker 빌드 캐시를 정리하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  docker builder prune -af
  echo "✅ 빌드 캐시 정리 완료"
else
  echo "빌드 캐시 유지"
fi
echo ""

echo "=========================================="
echo "Step 6: 배포 전 체크"
echo "=========================================="
./shell-script/check-deployment.sh "$ENVIRONMENT"
echo ""

echo "=========================================="
echo "Step 7: 새로 빌드 및 시작"
echo "=========================================="
echo "docker compose -f $COMPOSE_FILE up -d --build"
docker compose -f "$COMPOSE_FILE" up -d --build

echo ""
echo "=========================================="
echo "✅ 재배포 완료!"
echo "=========================================="
echo ""
echo "상태 확인:"
docker compose -f "$COMPOSE_FILE" ps
echo ""
echo "로그 확인: docker compose -f $COMPOSE_FILE logs -f [service]"
echo ""
