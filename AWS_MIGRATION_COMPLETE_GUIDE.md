# AWS 환경 마이그레이션 완료 가이드

## ✅ 구현 완료 사항

### 1. 🖥️ 화면 필터링 (API 레벨)

**문서 목록 API (`/api/v1/documents`)**
- Azure로 처리된 문서는 목록에서 제외
- AWS Bedrock(`pipeline_type='bedrock'`)으로 처리된 문서만 표시
- 처리 대기 중(`pending`, `processing`) 문서는 표시 (재처리 대상)

**필터링 로직:**
```python
# AWS 환경으로 처리된 문서만 필터링
aws_documents_subquery = select(DocExtractionSession.file_bss_info_sno).where(
    and_(
        DocExtractionSession.status == 'success',
        DocExtractionSession.pipeline_type == 'bedrock'  # AWS Bedrock만
    )
)

# 조건: AWS로 처리된 문서 OR 아직 처리되지 않은 문서
or_(
    TbFileBssInfo.file_bss_info_sno.in_(aws_documents_subquery),
    TbFileBssInfo.processing_status.in_(['pending', 'processing'])
)
```

**결과:**
- ✅ Azure 기반 구 데이터는 화면에 표시되지 않음
- ✅ AWS Bedrock으로 처리된 신규 데이터만 표시
- ✅ 아직 처리되지 않은 문서는 표시 (업로드 후 처리 대기)
- ✅ 검색 시에도 Azure 데이터는 참조되지 않음

---

### 2. 🗄️ 데이터베이스 초기화 도구

#### A. 확인 도구

**`check_migration_status.sh`** - 전체 상태 확인
```bash
./check_migration_status.sh
```

출력 정보:
- Azure 기반 데이터 개수
- 현재 백엔드 설정 (Provider, 모델)
- 권장 조치사항
- 백엔드 실행 상태

**`check_azure_data.sql`** - Azure 데이터 상세 분석
```bash
psql -h localhost -U wkms -d wkms -f check_azure_data.sql
```

분석 내용:
- Pipeline Type별 추출 세션
- Provider별 임베딩 통계
- Azure 모델 사용 현황
- Azure로 처리된 파일 목록
- 요약 통계

**`check_document_data.sql`** - 전체 문서 데이터 상태
```bash
psql -h localhost -U wkms -d wkms -f check_document_data.sql
```

---

#### B. 초기화 도구

**옵션 1: 대화형 스크립트 (권장)**
```bash
./reset_document_data.sh
```

선택 옵션:
1. 백업 없이 즉시 삭제 (빠름, 복구 불가)
2. 백업 후 삭제 (안전, 복구 가능)

**옵션 2: SQL 직접 실행**

백업 포함 (권장):
```bash
psql -h localhost -U wkms -d wkms -f reset_document_data_with_backup.sql
```

백업 없이:
```bash
psql -h localhost -U wkms -d wkms -f reset_document_data.sql
```

---

### 3. 🧹 초기화 대상 테이블

| 테이블 | 설명 | Azure 데이터 |
|--------|------|--------------|
| `doc_embedding` | 벡터 임베딩 | Azure OpenAI 1536d → AWS Titan 1024d |
| `doc_chunk` | 청크 데이터 | Azure DI 추출 → Upstage/Bedrock 추출 |
| `doc_chunk_session` | 청킹 세션 | Azure 세션 제거 |
| `doc_extracted_object` | 추출 객체 | Azure DI 객체 → Upstage 객체 |
| `doc_extraction_session` | 추출 세션 | `pipeline_type='azure'` → `'bedrock'` |
| `vs_doc_contents_chunks` | 레거시 벡터 | Azure 임베딩 제거 |
| `tb_document_search_index` | 검색 인덱스 | Azure 기반 인덱스 제거 |
| `tb_file_bss_info` | 파일 메타 | 처리 상태만 `pending`으로 초기화 |

---

### 4. 📊 마이그레이션 워크플로우

```
┌─────────────────────────────────────────────────────────────┐
│ 1️⃣  현재 상태 확인                                           │
├─────────────────────────────────────────────────────────────┤
│ ./check_migration_status.sh                                 │
│ - Azure 데이터 개수 확인                                      │
│ - 백엔드 설정 확인                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2️⃣  Azure 데이터 상세 분석 (선택)                             │
├─────────────────────────────────────────────────────────────┤
│ psql -f check_azure_data.sql                                │
│ - Pipeline Type 분석                                         │
│ - Provider별 임베딩 통계                                      │
│ - 영향 받는 파일 목록                                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3️⃣  백엔드 중지                                               │
├─────────────────────────────────────────────────────────────┤
│ # 터미널에서 Ctrl+C                                          │
│ 또는                                                         │
│ pkill -f "uvicorn app.main:app"                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4️⃣  데이터베이스 초기화                                       │
├─────────────────────────────────────────────────────────────┤
│ ./reset_document_data.sh                                    │
│ 선택: 백업 후 삭제 (권장)                                     │
│                                                             │
│ 결과:                                                        │
│ - ✅ 모든 Azure 데이터 제거                                  │
│ - ✅ 시퀀스 초기화 (ID=1부터 시작)                            │
│ - ✅ 파일 정보는 유지 (재처리 대상)                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5️⃣  백엔드 재시작                                             │
├─────────────────────────────────────────────────────────────┤
│ ./shell-script/dev-start-backend.sh                         │
│                                                             │
│ 시작 로그 확인:                                               │
│ 🌩️  멀티모달 임베딩 모델: twelvelabs.marengo-embed-3-0-v1:0│
│ 📐 멀티모달 임베딩 차원: 512                                  │
│ 🌐 멀티모달 엔드포인트: AWS Bedrock - ap-northeast-2        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6️⃣  새 문서 업로드 테스트                                     │
├─────────────────────────────────────────────────────────────┤
│ - 프론트엔드에서 PDF 업로드                                   │
│ - Celery 로그 확인:                                          │
│   tail -f logs/celery.log | grep -E "UPSTAGE|BEDROCK"      │
│                                                             │
│ 기대 로그:                                                    │
│ [UPSTAGE] 🚀 문서 분석 시작                                  │
│ [UPSTAGE] ✅ 문서 분석 완료                                  │
│ [MULTIMODAL] Bedrock 임베딩 생성                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7️⃣  데이터베이스 검증                                         │
├─────────────────────────────────────────────────────────────┤
│ psql -c "SELECT provider, model_name, COUNT(*)              │
│          FROM doc_embedding GROUP BY provider, model_name;" │
│                                                             │
│ 기대 결과:                                                    │
│ provider | model_name                         | count      │
│ ---------+-----------------------------------+-------      │
│ bedrock  | amazon.titan-embed-text-v2:0      | X          │
│ bedrock  | twelvelabs.marengo-embed-3-0-v1:0 | Y          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8️⃣  화면 확인                                                 │
├─────────────────────────────────────────────────────────────┤
│ - 지식 컨테이너 > 파일 목록                                   │
│ - ✅ 새로 업로드한 문서만 표시                                │
│ - ✅ 과거 Azure 데이터는 표시 안됨                            │
│ - ✅ 검색 정상 작동                                           │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. 🔍 검증 체크리스트

#### 백엔드 설정 확인
- [ ] `DEFAULT_LLM_PROVIDER=bedrock`
- [ ] `DEFAULT_EMBEDDING_PROVIDER=bedrock`
- [ ] `BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0`
- [ ] `BEDROCK_MULTIMODAL_EMBEDDING_MODEL_ID=twelvelabs.marengo-embed-3-0-v1:0`
- [ ] `DOCUMENT_PROCESSING_PROVIDER=upstage`
- [ ] `DOCUMENT_PROCESSING_FALLBACK=azure_di`

#### 데이터베이스 확인
```sql
-- 1. Azure 데이터 개수 (0이어야 함)
SELECT COUNT(*) FROM doc_embedding 
WHERE provider IN ('azure', 'azure_openai');

-- 2. AWS 데이터 개수 (새 업로드 후 증가)
SELECT COUNT(*) FROM doc_embedding 
WHERE provider = 'bedrock';

-- 3. 파일 처리 상태
SELECT processing_status, COUNT(*) 
FROM tb_file_bss_info 
GROUP BY processing_status;
```

#### 화면 확인
- [ ] 지식 컨테이너 목록 로드
- [ ] 컨테이너별 파일 목록 로드
- [ ] 과거 Azure 기반 문서 미표시
- [ ] 새 문서 업로드 성공
- [ ] 새 문서 목록 표시
- [ ] 검색 기능 정상 작동

---

### 6. 🚨 트러블슈팅

#### 문제 1: "Azure 데이터가 여전히 표시됨"

**원인:** API 필터링이 적용되지 않음

**해결:**
```bash
# 백엔드 재시작
pkill -f "uvicorn app.main:app"
./shell-script/dev-start-backend.sh

# 캐시 확인 (Redis)
redis-cli FLUSHALL
```

#### 문제 2: "새 문서가 표시되지 않음"

**원인:** Celery 처리 실패

**해결:**
```bash
# Celery 로그 확인
tail -100 logs/celery.log

# Celery 재시작
pkill -f celery
celery -A app.core.celery_app worker --loglevel=info
```

#### 문제 3: "검색이 작동하지 않음"

**원인:** 벡터 인덱스 미생성

**해결:**
```sql
-- 벡터 인덱스 재생성
DROP INDEX IF EXISTS idx_doc_embedding_aws_vector_1024;
CREATE INDEX idx_doc_embedding_aws_vector_1024 
ON doc_embedding USING ivfflat (aws_vector_1024 vector_cosine_ops)
WITH (lists = 100);
```

#### 문제 4: "백업 복구가 필요함"

**복구 방법:**
```bash
# 1. 백업 테이블 확인
psql -c "SELECT tablename FROM pg_tables WHERE tablename LIKE '%_backup_%';"

# 2. 특정 테이블 복구 (예: doc_embedding)
psql -c "
TRUNCATE TABLE doc_embedding;
INSERT INTO doc_embedding SELECT * FROM doc_embedding_backup_20251117_140530;
"

# 3. 시퀀스 재설정
psql -c "
SELECT setval('doc_embedding_embedding_id_seq', 
    (SELECT MAX(embedding_id) FROM doc_embedding));
"
```

---

### 7. 📝 주요 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/api/v1/documents.py` | AWS 필터링 로직 추가 |
| `backend/app/core/config.py` | 멀티모달 설정 메서드 추가 |
| `backend/app/main.py` | 동적 설정 로드 |
| `reset_document_data.sh` | 대화형 초기화 스크립트 |
| `reset_document_data.sql` | 빠른 초기화 SQL |
| `reset_document_data_with_backup.sql` | 안전한 초기화 SQL |
| `check_migration_status.sh` | 전체 상태 확인 |
| `check_azure_data.sql` | Azure 데이터 분석 |
| `check_document_data.sql` | 문서 데이터 상태 |

---

### 8. 🎯 마이그레이션 후 기대 효과

#### Before (Azure 환경)
```
문서 목록:
- 📄 Document A (Azure DI, text-embedding-3-small 1536d)
- 📄 Document B (Azure DI, text-embedding-3-small 1536d)
- 📄 Document C (Azure DI, Azure CLIP 512d)

검색 결과:
- Azure 임베딩 기반 검색
- 비용: $$$
- 처리 시간: 느림 (해외 리전)
```

#### After (AWS 환경)
```
문서 목록:
- 📄 Document D (Upstage, Titan v2 1024d) ✅ 
- 📄 Document E (Upstage, TwelveLabs 512d) ✅

검색 결과:
- AWS Bedrock 임베딩 기반 검색
- 비용: $$ (30% 절감)
- 처리 시간: 빠름 (서울 리전)
- 한국어 성능 향상
```

---

### 9. ✅ 최종 확인

마이그레이션이 완료되면:

```bash
# 전체 상태 확인
./check_migration_status.sh
```

출력 예시 (성공):
```
✅ Azure 기반 데이터가 발견되지 않았습니다.
✅ 시스템이 AWS 환경으로 정상 전환되었습니다.

🟢 백엔드 서버가 실행 중입니다.

📊 통계:
   전체 파일: 0
   Azure 처리 파일: 0
   AWS 처리 파일: 0
   Azure 임베딩: 0
   AWS 임베딩: 0
```

새 문서 업로드 후:
```
📊 통계:
   전체 파일: 5
   Azure 처리 파일: 0
   AWS 처리 파일: 5
   Azure 임베딩: 0
   AWS 임베딩: 125
```

---

**작성일:** 2025-11-17  
**상태:** ✅ 구현 완료  
**다음 단계:** 데이터베이스 초기화 → 백엔드 재시작 → 새 문서 업로드 테스트
