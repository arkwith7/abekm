# WKMS API 구조 가이드

## 📁 권장 디렉토리 구조

```
backend/app/api/
├── __init__.py
├── main_router.py              # 메인 라우터 집합
├── v1/                         # API 버전 1 (메인 API)
│   ├── __init__.py
│   ├── documents.py            # 📄 문서 관리 (CRUD + 업로드)
│   ├── containers.py           # 📦 컨테이너 관리
│   ├── search.py              # 🔍 검색 및 AI 기능
│   ├── users.py               # 👤 사용자 관리
│   └── analytics.py           # 📊 분석 및 통계
├── services/                   # 특수 목적 서비스
│   ├── __init__.py
│   ├── processing.py          # 🔧 문서 처리 전용
│   ├── batch.py              # 📦 배치 처리
│   └── monitoring.py         # 📈 모니터링
├── legacy/                     # 레거시 API (호환성)
│   ├── __init__.py
│   ├── old_documents.py       # 기존 API 호환
│   └── deprecated.py          # 단계적 폐기 예정
└── external/                   # 외부 연동
    ├── __init__.py
    ├── sap.py                 # SAP 연동
    └── webhooks.py           # 웹훅 처리
```

## 🔄 API URL 구조

### 메인 API (프론트엔드 직접 사용)

- `/api/v1/documents/`          - 문서 CRUD
- `/api/v1/containers/`         - 컨테이너 관리
- `/api/v1/search/`            - 검색 기능
- `/api/v1/users/`             - 사용자 관리
- `/api/v1/analytics/`         - 분석 기능

### 서비스 API (내부/고급 사용)

- `/api/services/processing/`   - 문서 처리
- `/api/services/batch/`       - 배치 작업
- `/api/services/monitoring/`  - 시스템 모니터링

### 레거시 API (호환성 유지)

- `/api/legacy/documents/`     - 기존 API 호환

## 📋 책임 분리 원칙

### v1/documents.py (메인)

- ✅ 문서 CRUD 작업
- ✅ 기본 업로드/다운로드
- ✅ 권한 기반 접근 제어
- ✅ 컨테이너 연동

### services/processing.py (처리)

- ✅ 텍스트 추출
- ✅ NLP 처리
- ✅ 형식 변환
- ✅ 품질 분석

### v1/search.py (검색)

- ✅ 벡터 검색
- ✅ 하이브리드 검색
- ✅ AI 기반 질의응답
- ✅ 검색 분석

## 🔗 의존성 관계

```
v1/documents.py
    ↓ (uses)
services/processing.py
    ↓ (uses)
core/services/
    ↓ (uses)
models/ & schemas/
```

## 🚀 마이그레이션 계획

1. **Phase 1**: v1/documents.py 완성 (현재)
2. **Phase 2**: 기존 API를 legacy/로 이동
3. **Phase 3**: services/ 특화 API 분리
4. **Phase 4**: 레거시 API 단계적 폐기