# 📁 Document Services 리팩터링 계획
# VsDocContentsIndex → tb_document_search_index 변경 반영

## 🎯 목표 구조 (models/ 제외)

```
backend/app/services/document/
├── __init__.py
├── extraction/
│   ├── __init__.py
│   ├── text_extractor.py           # TextExtractorService 이전
│   └── format_handlers.py          # 포맷별 핸들러 분리
├── processing/
│   ├── __init__.py
│   ├── preprocessor.py             # DocumentPreprocessingService 이전
│   ├── chunking_strategies.py      # 청킹 전략 모듈화 (선택적)
│   └── korean_nlp.py              # KoreanNLPService 이전
├── storage/
│   ├── __init__.py
│   ├── search_index_store.py      # 새로운 통합검색 저장 서비스
│   └── metadata_store.py          # 메타데이터 저장 서비스
└── pipeline/
    ├── __init__.py
    ├── integrated_pipeline.py     # 통합 파이프라인 서비스
    └── pipeline_validators.py     # 파이프라인 검증 로직
```

## 🚀 Phase별 실행 계획

### Phase 1: 스키마 변경 및 새로운 검색 서비스 (1-2일)
1. ✅ VsDocContentsIndex → tb_document_search_index 스키마 변경
2. 🆕 SearchIndexStoreService 개발 (tb_search_documents 대체)
3. 🔧 기존 벡터 저장 서비스들 정리

### Phase 2: 서비스 이전 및 구조화 (2-3일)
1. `/document/extraction/` 구조 생성 및 이전
   - text_extractor_service.py → text_extractor.py
   - 포맷별 핸들러 분리
   
2. `/document/processing/` 구조 생성 및 이전
   - document_preprocessing_service.py → preprocessor.py
   - core/korean_nlp_service.py → korean_nlp.py
   
3. `/document/storage/` 구조 생성 및 이전
   - 새로운 search_index_store.py 개발
   - metadata_store.py 개발

### Phase 3: 파이프라인 통합 및 최적화 (2-3일)
1. `/document/pipeline/` 구조 생성
   - integrated_document_pipeline_service.py → integrated_pipeline.py
   - 검증 로직 추가
   
2. 기존 서비스들과의 의존성 업데이트
3. 테스트 및 성능 최적화

## 📋 주요 변경사항

### 1. 테이블 용도 변경
- **기존**: 청크 단위 벡터 저장 (vs_doc_contents_index)
- **신규**: 문서 전문 통합검색 (tb_document_search_index)

### 2. 서비스 통합
- **통합 대상**: tb_search_documents + vs_doc_contents_index
- **새로운 서비스**: SearchIndexStoreService
- **제거 대상**: embedding 필드, 중복 벡터 저장

### 3. 검색 기능 강화
- **키워드 검색**: GIN 인덱스 + tsvector 최적화
- **하이브리드 검색**: 가중치 기반 점수 통합
- **성능 최적화**: 전문검색 + 배열 검색 인덱스

## 🔧 즉시 필요한 작업

### 1. 스키마 마이그레이션
```sql
-- 기존 테이블 백업
CREATE TABLE vs_doc_contents_index_backup AS 
SELECT * FROM vs_doc_contents_index;

-- 새로운 테이블 생성
-- (proposed_search_schema.sql 참조)

-- 데이터 마이그레이션 스크립트 개발 필요
```

### 2. 서비스 개발 우선순위
1. 🔥 **SearchIndexStoreService** (가장 중요)
2. 📋 integrated_pipeline.py 수정 
3. 🔧 기존 vector_storage_service 정리

### 3. API 연동 확인
- `/api/v1/search/` 엔드포인트들
- hybrid_search_service.py 
- 기존 검색 관련 서비스들

## 💡 추가 고려사항

### 1. 벡터 검색 분리
- **문서 전문 검색**: tb_document_search_index (키워드 중심)
- **의미적 유사도 검색**: 별도 벡터 테이블 유지 (필요시)

### 2. 성능 최적화
- **전문검색**: PostgreSQL FTS 엔진 활용
- **키워드 매칭**: GIN 인덱스 + 배열 검색
- **하이브리드**: 가중치 기반 점수 통합

### 3. 호환성 유지
- 기존 API 인터페이스 유지
- 점진적 마이그레이션 지원
- 롤백 계획 수립

이 계획으로 진행하시겠습니까? 어떤 Phase부터 시작하시겠습니까?
