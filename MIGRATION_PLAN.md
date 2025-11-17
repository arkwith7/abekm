# TB_DOCUMENT_CHUNKS → VS_DOC_CONTENTS_CHUNKS 마이그레이션 계획

## 🎯 목표
테이블명 일관성 확보 및 RAG 아키텍처 개선
- `tb_document_chunks` → `vs_doc_contents_chunks` (벡터 테이블 명명 규칙 적용)
- 청크 단위 RAG 검색 구조 확립

## 📋 단계별 작업 계획

### 1단계: 새로운 모델 정의 📝
```python
# /backend/app/models/korean_nlp_models.py
class VsDocContentsChunks(Base):
    """문서 청킹 결과 + 벡터 저장 (통합 테이블)"""
    __tablename__ = "vs_doc_contents_chunks"
    
    # 기존 tb_document_chunks 컬럼들 + 벡터 기능
```

### 2단계: 데이터베이스 마이그레이션 생성 🗄️
```bash
# Alembic 마이그레이션 생성
cd backend
alembic revision -m "rename_tb_document_chunks_to_vs_doc_contents_chunks"
```

### 3단계: 서비스 레이어 업데이트 🔧
#### A. 문서 처리 파이프라인
- ✅ `integrated_document_pipeline_service.py`
  - DocumentChunk → VsDocContentsChunks
  - 테이블명 변경

#### B. RAG 검색 서비스  
- ✅ `rag_search_service.py` (이미 tb_document_chunks 사용하도록 수정됨)
  - 테이블명만 vs_doc_contents_chunks로 변경

#### C. 벡터 저장 서비스
- ✅ `vector_storage_service.py`
- ✅ `vector_storage_service_real_schema.py`

### 4단계: 테스트 및 검증 🧪
#### A. 단위 테스트 업데이트
- 모든 테스트 파일의 테이블명 참조 변경

#### B. 통합 테스트
- 문서 업로드 → 청킹 → 벡터화 → 검색 파이프라인 검증

#### C. 데이터 마이그레이션 검증
- 기존 데이터 손실 없이 이전되었는지 확인

## 🚨 주의사항

### 데이터 무결성
- 기존 tb_document_chunks 데이터를 vs_doc_contents_chunks로 안전하게 이전
- 벡터 인덱스 재생성 시간 고려
- 롤백 전략 수립

### 서비스 중단 최소화
- Blue-Green 배포 방식 고려
- 마이그레이션 중 읽기 전용 모드 운영

### 성능 고려사항
- 벡터 인덱스 크기에 따른 마이그레이션 시간
- ivfflat 인덱스 재생성 최적화

## 📊 영향을 받는 파일 목록

### 모델 정의
- `/backend/app/models/korean_nlp_models.py` ⭐ 핵심
- `/backend/app/models/__init__.py`

### 서비스 레이어  
- `/backend/app/services/integrated_document_pipeline_service.py` ⭐ 핵심
- `/backend/app/services/rag_search_service.py` ⭐ 핵심
- `/backend/app/services/vector_storage_service.py`
- `/backend/app/services/vector_storage_service_real_schema.py`

### 마이그레이션
- `/backend/alembic/versions/004_korean_nlp_support.py`
- `/backend/alembic/versions/008_add_knowledge_container_support.py`
- 새로운 마이그레이션 파일

### 테스트 파일
- 여러 테스트 파일들의 테이블명 참조

## 🔄 롤백 계획
1. 새 테이블 제거
2. 기존 테이블 복원  
3. 서비스 코드 원복
4. 인덱스 재생성

## ⏰ 예상 작업 시간
- 1단계: 30분 (모델 정의)
- 2단계: 1시간 (마이그레이션 스크립트)
- 3단계: 2시간 (서비스 레이어 업데이트)
- 4단계: 1시간 (테스트 및 검증)
- **총 예상 시간: 4.5시간**

## 📝 체크리스트
- [ ] 새로운 VsDocContentsChunks 모델 정의
- [ ] Alembic 마이그레이션 스크립트 작성
- [ ] integrated_document_pipeline_service.py 업데이트
- [ ] rag_search_service.py 테이블명 변경
- [ ] vector_storage_service.py 업데이트  
- [ ] 테스트 파일들 업데이트
- [ ] 데이터 마이그레이션 실행 및 검증
- [ ] 성능 테스트
- [ ] 배포 및 모니터링
