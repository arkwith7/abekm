# ABEKM 환경 변수 파일 전략 및 문제점 분석

**작성일**: 2025-10-27  
**분석 대상**: 환경 변수 파일 구조 및 검증 스크립트

---

## 📊 현재 상황

### 환경 변수 파일 구조

| 파일 경로 | 용도 | 상태 | 라인 수 |
|----------|------|------|--------|
| `backend/.env` | **터미널 직접 실행 개발용** | ✅ 완전 | 197줄 |
| `.env.development` | **Docker Compose 개발용** | ❌ 거의 비어있음 | 8줄 |
| `.env.production` | **Docker Compose 프로덕션용** | ⚠️ 확인 필요 | - |
| `frontend/.env` | 프론트엔드 빌드용 | ✅ 완전 | - |

### 검증 스크립트

| 스크립트 | 원래 목적 | 실제 검증 대상 | 문제점 |
|---------|----------|--------------|--------|
| `validate-env.sh` | 배포 전 검증 | ~~루트 `.env`~~ → `.env.development/production` | ✅ 수정됨 |
| `sync-check-env.sh` | KEY 동기화 확인 | `backend/.env` ↔ `.env.*` | ⚠️ `.env.*` 비어있음 |
| `sync-env-keys.sh` | KEY 자동 동기화 | `backend/.env` → `.env.*` | ⚠️ 실행 필요 |

---

## 🚨 발견된 문제점

### 1. `.env.development` 파일이 거의 비어있음

**현재 상태**:
```bash
$ wc -l .env.development
8 .env.development

$ cat .env.development
# ===========================================
# WKMS 개발 환경 설정 (Docker 로컬 개발)
# 사용: docker compose --env-file .env.development up -d
# ===========================================

(주석만 있고 실제 변수 없음)
```

**영향**:
- Docker Compose로 개발 환경 시작 불가
- 모든 환경 변수가 undefined 상태
- 컨테이너 시작 실패 가능성 100%

---

### 2. `backend/.env`와 `.env.development`의 분리 목적 혼란

**질문**: "터미널 개발 환경에서는 프로젝트 루트에 .env 파일이 필요 없는데 왜 체크하나?"

**답변**: 
- ✅ **맞습니다!** 터미널 직접 실행 시에는 `backend/.env`만 필요합니다
- ✅ **Docker Compose 배포**를 위해서는 `.env.development` / `.env.production` 필요
- ❌ **문제**: `.env.development`가 비어있어 Docker 배포 불가

---

### 3. 환경 변수 동기화 미실행

**`sync-check-env.sh` 실행 결과**:
```bash
$ ./shell-script/sync-check-env.sh
[1/4] backend/.env 분석 완료 (113개 KEY)
[2/4] .env.development 분석 완료 (0개 KEY)  ← 🚨 0개!
[3/4] .env.production 분석 완료 (87개 KEY)

❌ .env.development에 누락된 KEY: 113개  ← 🚨 전부!
```

**해결 방법**: `sync-env-keys.sh` 실행 필요

---

## ✅ 올바른 환경 변수 파일 전략

### 1. 파일 용도 명확화

```
프로젝트 루트/
├─ backend/.env              # 터미널 직접 실행 전용 (Python/uvicorn)
├─ .env.development          # Docker Compose 개발 환경 전용
├─ .env.production           # Docker Compose 프로덕션 환경 전용
└─ frontend/.env             # 프론트엔드 빌드 시 사용
```

### 2. 사용 시나리오

#### 시나리오 A: 터미널에서 직접 개발

```bash
# backend/.env 파일 사용
cd backend
python -m uvicorn app.main:app --reload

# 검증 불필요 (Pydantic Settings가 자동 로드)
```

**파일 요구사항**:
- ✅ `backend/.env` 필요
- ❌ `.env.development` 불필요
- ❌ `.env.production` 불필요

---

#### 시나리오 B: Docker Compose 개발 환경

```bash
# .env.development 파일 사용
docker-compose --env-file .env.development up -d

# 검증 필수!
./shell-script/validate-env.sh .env.development
```

**파일 요구사항**:
- ✅ `.env.development` 필요 (113개 KEY)
- ❌ `backend/.env` 불필요 (컨테이너 내부에서 .env.development 사용)
- ✅ `frontend/.env` 필요 (빌드 시 사용)

---

#### 시나리오 C: Docker Compose 프로덕션 배포

```bash
# .env.production 파일 사용
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d

# 검증 필수!
./shell-script/validate-env.sh .env.production
```

**파일 요구사항**:
- ✅ `.env.production` 필요 (87개 KEY + 추가 필요)
- ❌ `backend/.env` 불필요
- ✅ `frontend/.env` 필요 (API URL 프로덕션으로 변경)

---

## 💡 즉시 조치 사항

### 1단계: `.env.development` 파일 동기화

```bash
# backend/.env의 KEY를 .env.development로 복사
./shell-script/sync-env-keys.sh

# 검증
./shell-script/sync-check-env.sh
```

**예상 결과**:
```bash
✅ .env.development에 113개 KEY 추가됨
✅ 모든 환경 변수 파일이 동기화되어 있습니다!
```

---

### 2단계: `.env.development` 값 조정

`sync-env-keys.sh`는 KEY만 복사하고 VALUE는 `backend/.env`에서 그대로 가져오므로, **Docker 환경에 맞게 값 수정 필요**:

```bash
vi .env.development
```

**주요 수정 항목**:

```bash
# 🔴 수정 필요: 호스트 이름
DATABASE_URL=postgresql+asyncpg://wkms:wkms123@postgres:5432/wkms
                                              # ↑ localhost → postgres

REDIS_HOST=redis  # localhost → redis
REDIS_URL=redis://redis:6379/0

# ✅ 유지 가능
POSTGRES_DB=wkms
POSTGRES_USER=wkms
POSTGRES_PASSWORD=wkms123

# ✅ 개발 환경이므로 localhost CORS 허용
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

---

### 3단계: 검증 후 Docker 시작

```bash
# 검증
./shell-script/validate-env.sh .env.development

# Docker Compose 시작
docker-compose --env-file .env.development up -d
```

---

## 📋 검증 스크립트 사용법 정리

### `validate-env.sh` - Docker Compose 배포 전 검증

**목적**: Docker Compose 환경 파일 (.env.development, .env.production) 검증

**사용법**:
```bash
# 개발 환경 검증 (기본값)
./shell-script/validate-env.sh .env.development

# 프로덕션 환경 검증
./shell-script/validate-env.sh .env.production
```

**검증 항목**:
1. Docker Compose 환경 파일 존재 확인
2. 필수 환경 변수 8개 확인 (POSTGRES_DB, DATABASE_URL, REDIS_URL, SECRET_KEY, CORS_ORIGINS, STORAGE_BACKEND)
3. 보안 설정 (프로덕션: 엄격, 개발: 경고만)
4. frontend/.env 확인
5. docker-compose.yml / docker-compose.prod.yml 확인

**적용 대상**:
- ✅ Docker Compose 배포
- ❌ 터미널 직접 실행 개발

---

### `sync-check-env.sh` - 환경 변수 동기화 확인

**목적**: `backend/.env` ↔ `.env.development` ↔ `.env.production` KEY 동기화 상태 확인

**사용법**:
```bash
./shell-script/sync-check-env.sh
```

**출력 예시**:
```bash
[1/4] backend/.env 분석 완료 (113개 KEY)
[2/4] .env.development 분석 완료 (113개 KEY)
[3/4] .env.production 분석 완료 (87개 KEY)

❌ .env.production에 누락된 KEY: 26개
   AZURE_BLOB_ACCOUNT_NAME
   AZURE_OPENAI_ENDPOINT
   ...
```

---

### `sync-env-keys.sh` - 환경 변수 자동 동기화

**목적**: `backend/.env`의 KEY를 `.env.development`, `.env.production`에 자동 추가

**사용법**:
```bash
./shell-script/sync-env-keys.sh
```

**주의사항**:
- ⚠️ VALUE는 `backend/.env`에서 그대로 복사됨
- ⚠️ Docker 환경에 맞게 **호스트명 수정 필수** (localhost → postgres, redis)
- ⚠️ 프로덕션 환경은 **보안 값 변경 필수**

---

## 🎯 최종 권장 워크플로우

### 개발자가 새 환경 변수 추가 시

```bash
# 1. backend/.env에 새 변수 추가
vi backend/.env
# 예: NEW_FEATURE_ENABLED=true

# 2. Docker 환경 파일로 동기화
./shell-script/sync-env-keys.sh

# 3. Docker 환경에 맞게 값 조정
vi .env.development
# DATABASE_URL의 localhost → postgres 확인

# 4. 동기화 확인
./shell-script/sync-check-env.sh

# 5. Docker 재시작
docker-compose --env-file .env.development restart backend
```

---

### 새 서버 배포 시

```bash
# 1. .env.production 동기화
./shell-script/sync-env-keys.sh

# 2. 프로덕션 값 설정
vi .env.production
# - 비밀번호 변경
# - 도메인 설정
# - 호스트명 확인 (postgres, redis)

# 3. frontend/.env 수정
vi frontend/.env
# REACT_APP_API_URL=https://api.yourdomain.com

# 4. 검증
./shell-script/validate-env.sh .env.production

# 5. 배포
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d
```

---

## 📝 문서 업데이트 사항

**`별첨07_컨테이너_배포_체크리스트.md` 수정 완료**:

1. ✅ `validate-env.sh` 설명 수정:
   - "루트 .env 검증" → "Docker Compose 환경 파일 검증"
   - 파라미터 추가: `.env.development` / `.env.production` 선택 가능

2. ✅ 사용법 명확화:
   - 개발 환경: `./shell-script/validate-env.sh .env.development`
   - 프로덕션: `./shell-script/validate-env.sh .env.production`

3. ✅ 중요 안내 추가:
   - "이 스크립트는 Docker Compose 배포 전용입니다"
   - "터미널 직접 실행 개발 환경(`backend/.env`)은 별도 검증 불필요"

---

## ⚠️ 향후 개선 사항

### 1. `.env.development.example` 파일 생성

현재 `.env.development`가 비어있으므로, 템플릿 파일 필요:

```bash
cp backend/.env .env.development.example

# Docker 환경에 맞게 수정
sed -i 's/localhost/postgres/g' .env.development.example
sed -i 's/REDIS_HOST=redis/REDIS_HOST=redis/g' .env.development.example
```

### 2. Git Hook 자동화

```bash
# .git/hooks/pre-commit
#!/bin/bash
if [ -f backend/.env ]; then
  ./shell-script/sync-check-env.sh || {
    echo "❌ 환경 변수 동기화 필요!"
    echo "💡 ./shell-script/sync-env-keys.sh 실행"
    exit 1
  }
fi
```

### 3. CI/CD 파이프라인 검증

GitHub Actions / GitLab CI에서 배포 전 자동 검증:

```yaml
- name: Validate production environment
  run: |
    chmod +x shell-script/validate-env.sh
    ./shell-script/validate-env.sh .env.production
```

---

**작성자**: GitHub Copilot  
**분석 도구**: 파일 구조 분석, 스크립트 실행 결과, 사용자 질문 분석  
**해결 방법**: validate-env.sh 스크립트 수정, 문서 업데이트, 워크플로우 정의
