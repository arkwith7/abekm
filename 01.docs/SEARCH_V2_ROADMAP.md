## Search V2 전환 로드맵 및 어댑터 가이드

목표: `app/services/search/search_service_v2.py`를 기준으로 파일/청크/멀티모달 컨텍스트 검색을 모듈화하고, 기존 V1 API와 호환되는 어댑터를 제공한다.

### 1) 대상/범위
- 서비스 대상
  - 파일 레벨 검색(file_level_search)
  - 청크 레벨 검색(chunk_level_search, modality: text/table/image)
  - 멀티모달 컨텍스트(multimodal_context: text K, table K, image K 통합)
- API 영향
  - `app/api/v1/search.py` 내 `/search`, `/search/unified`, `/search/context`, `/multimodal`, `/search/clip`
  - RAG 파이프라인(`ai_agent_service.prepare_context_with_documents`)의 내부 검색 호출

### 2) 단계별 전환
- Phase 1: V2 서비스 구현 + V1 어댑터 유지
  - V2 내부 구현: SQL 조인(청크/임베딩/파일/컨테이너), 필터, 재랭킹, 중복제거
  - V1 어댑터: 기존 응답 스키마 유지(프론트 변경 최소화)
- Phase 2: 가중치/튜닝 설정화
  - 환경/설정 파일에서 TopK, 임계값, 재랭킹 여부, 가중치 조정 가능
  - AB테스트 로그 수집(쿼리/선택 문서/최종 유사도 분포)
- Phase 3: API 스키마 업데이트
  - OpenAPI 반영 및 프런트 타입 생성
  - 점진적 마이그레이션(플래그 기반)

### 3) 기술 설계 요점
- 검색 파이프라인
  1. Preprocess(언어/키워드/의도)
  2. Candidate Retrieval(벡터/키워드/FTS)
  3. (옵션) Re-ranking (Cross-encoder/Hybrid score)
  4. Deduplication(파일/페이지/섹션 기준)
  5. Postprocess(미리보기 생성/하이라이트/컨테이너 경로)
- 모듈화
  - Retriever 인터페이스: Vector/Keyword/FTS/CLIP
  - Ranker 인터페이스: BM25/CE
  - Merger/Deduper: 스코어 정규화→병합→중복제거

### 4) 어댑터 가이드
- V2→V1 변환 예
  - UnifiedSearchResponse: 파일 단위 그룹핑 후 `title`, `content_preview`, `container_*` 필드 매핑
  - ContextSearchResponse: 청크 세부 필드(`chunk_id`, `chunk_index`, `page_number`, `modality`) 유지
  - Multimodal: `has_images`, `image_count`, `clip_score` 반영

### 5) 이행 체크리스트
- [ ] V2 구현 파일/청크/멀티모달 함수 본체 작성
- [ ] 설정값(TopK/Threshold/Weights) 외부화
- [ ] V1 어댑터 작성 및 라우터 스위치 가능 옵션 추가
- [ ] 로그/메트릭 수집(검색시간, 후보수, 최종수, 평균유사도)
- [ ] OpenAPI 스키마/프론트 타입 동기화


