#!/bin/bash

# WKMS 프론트엔드 개발 서버 시작 스크립트
# React 개발 서버 실행

REPO_ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_ROOT_DIR/frontend"

echo "=== WKMS 프론트엔드 개발 서버 시작 ==="
echo ""

# Node.js 환경 확인
echo "Node.js 버전: $(node --version)"
echo "npm 버전: $(npm --version)"
echo ""

# 의존성이 설치되어 있는지 확인
if [ ! -d "node_modules" ]; then
    echo "의존성을 설치합니다..."
    npm install
    echo ""
fi

echo "React 개발 서버를 시작합니다..."
echo "접속 주소: http://localhost:3000"
echo ""
echo "서버를 중지하려면 Ctrl+C를 누르세요."
echo ""

# React 개발 서버 실행
npm start
