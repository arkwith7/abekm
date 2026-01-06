# KIPRIS 데이터셋 적재 가이드

## 📋 개요

`backend/data/processed/` 아래의 KIPRIS 특허 데이터셋(JSONL + PDF)을 시스템의 정식 파이프라인으로 적재하는 스크립트입니다.

### 처리 흐름

```
JSONL + PDF (로컬 파일)
    ↓
TbFileBssInfo 레코드 생성 (document_type='patent')
    ↓
PipelineRouter → PatentPipeline
    ↓
PDF 파싱 (Azure DI / Textract / PyMuPDF)
    ↓
섹션 청킹 (청구항, 명세서, 도면 등)
    ↓
벡터 임베딩 (Bedrock Titan / Azure OpenAI)
    ↓
검색 인덱스 저장 (tb_document_search_index)
    ↓
DB 레코드 업데이트 (processing_status='completed')
```

## 🚀 사용법

### 1. 컨테이너 내부에서 실행 (권장)

```bash
# 먼저 컨테이너가 실행 중인지 확인
docker ps | grep abkms-backend

# Dry-run으로 시뮬레이션 (실제 적재 없음)
docker exec -it abkms-backend python -m app.scripts.load_kipris_dataset --limit 5 --dry-run

# 실제 적재 (100건 샘플)
docker exec -it abkms-backend python -m app.scripts.load_kipris_dataset --limit 100

# 전체 적재 (1,500건)
docker exec -it abkms-backend python -m app.scripts.load_kipris_dataset
```

### 2. 로컬 venv에서 실행

```bash
# venv 활성화
source /home/arkwith/Dev/abekm/.venv/bin/activate

# 환경 변수 설정 (필요시)
export DATABASE_URL="postgresql+asyncpg://wkms:wkms123@localhost:5432/wkms"
export REDIS_URL="redis://localhost:6379/0"

# Dry-run
python -m app.scripts.load_kipris_dataset --limit 5 --dry-run

# 실제 적재
python -m app.scripts.load_kipris_dataset --limit 100
```

## ⚙️ 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--limit N` | 처리할 최대 건수 | 전체 (1,500건) |
| `--container-id ID` | 특허를 저장할 컨테이너 ID | `KIPRIS_EVAL` |
| `--user USER` | 사용자 사번 | `system` |
| `--skip-existing` | 이미 DB에 있는 특허는 스킵 | True (기본 활성화) |
| `--dry-run` | 실제 적재 없이 시뮬레이션만 | False |

## 📊 예상 처리 시간

- **100건**: 약 30분 ~ 1시간 (PDF 파싱 + 임베딩 생성)
- **1,500건**: 약 8~12시간 (백그라운드 실행 권장)

## 🔍 적재 확인

```sql
-- 적재된 특허 문서 확인
SELECT 
    file_bss_info_sno,
    file_lgc_nm,
    processing_status,
    chunk_count,
    created_date
FROM tb_file_bss_info
WHERE document_type = 'patent'
  AND knowledge_container_id = 'KIPRIS_EVAL'
ORDER BY created_date DESC
LIMIT 10;

-- 청크 및 임베딩 확인
SELECT 
    f.file_lgc_nm,
    COUNT(DISTINCT c.chunk_id) as chunks,
    COUNT(DISTINCT e.embedding_id) as embeddings
FROM tb_file_bss_info f
LEFT JOIN doc_chunk c ON f.file_bss_info_sno = c.file_bss_info_sno
LEFT JOIN doc_embedding e ON c.chunk_id = e.chunk_id
WHERE f.document_type = 'patent'
  AND f.knowledge_container_id = 'KIPRIS_EVAL'
GROUP BY f.file_bss_info_sno, f.file_lgc_nm
ORDER BY f.created_date DESC
LIMIT 10;
```

## 🐛 트러블슈팅

### PDF 파일을 찾을 수 없음
- `backend/data/processed/fulltext_pdfs/` 경로 확인
- 파일명이 출원번호 또는 공개번호와 일치하는지 확인

### 파이프라인 실패 (Azure DI / Bedrock)
- `.env` 파일의 API 키 및 설정 확인
- `DEFAULT_LLM_PROVIDER` 설정 확인 (bedrock/azure)
- AWS/Azure 자격증명 확인

### DB 연결 실패
- PostgreSQL 컨테이너 실행 확인: `docker ps | grep postgres`
- DATABASE_URL 환경변수 확인
- 컨테이너 네트워크: `abkms-network` 확인

### 메모리 부족
- 배치 크기 조정: `--limit 50`으로 소량씩 처리
- Celery worker 재시작: `docker restart abkms-celery-worker`

## 📝 로그 확인

```bash
# 백엔드 컨테이너 로그
docker logs -f abkms-backend

# Celery worker 로그
docker logs -f abkms-celery-worker
```

## 🔗 관련 파일

- **데이터**: `backend/data/processed/kipris_semiconductor_ai_dataset_paper.jsonl`
- **PDF**: `backend/data/processed/fulltext_pdfs/*.pdf`
- **파이프라인**: `backend/app/services/document/pipelines/patent_pipeline.py`
- **라우터**: `backend/app/services/document/pipeline_router.py`
