-- 0001_multimodal_schema.sql
-- 멀티모달 RAG 확장을 위한 1차 스키마 추가
-- 안전성: 이미 존재하면 생성하지 않는 패턴 + 컬럼 IF NOT EXISTS
-- 롤백은 별도 수동 스크립트에서 처리 (DROP TABLE 순서 주의)

BEGIN;

-- 1. 추출 세션 테이블
CREATE TABLE IF NOT EXISTS doc_extraction_session (
  extraction_session_id BIGSERIAL PRIMARY KEY,
  file_bss_info_sno BIGINT NOT NULL REFERENCES tb_file_bss_info(file_bss_info_sno) ON DELETE CASCADE,
  provider VARCHAR(50) NOT NULL,
  model_profile VARCHAR(50),
  pipeline_type VARCHAR(20) DEFAULT 'azure',
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'running', -- running|success|failed|partial
  page_count_detected INT,
  error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_extraction_session_file ON doc_extraction_session(file_bss_info_sno);
CREATE INDEX IF NOT EXISTS idx_extraction_session_status ON doc_extraction_session(status);

-- 2. 추출 객체 테이블
CREATE TABLE IF NOT EXISTS doc_extracted_object (
  object_id BIGSERIAL PRIMARY KEY,
  extraction_session_id BIGINT NOT NULL REFERENCES doc_extraction_session(extraction_session_id) ON DELETE CASCADE,
  file_bss_info_sno BIGINT NOT NULL,
  page_no INT,
  object_type VARCHAR(20) NOT NULL, -- TEXT_BLOCK|TABLE|IMAGE|FIGURE|HEADER|FOOTER
  sequence_in_page INT,
  bbox INT[], -- [x1,y1,x2,y2]
  content_text TEXT,
  structure_json JSONB,
  lang_code VARCHAR(10) DEFAULT 'ko',
  char_count INT,
  token_estimate INT,
  confidence NUMERIC(5,2),
  hash_sha256 CHAR(64),
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_extracted_object_file_page ON doc_extracted_object(file_bss_info_sno, page_no);
CREATE INDEX IF NOT EXISTS idx_extracted_object_type ON doc_extracted_object(object_type);
CREATE INDEX IF NOT EXISTS idx_extracted_object_hash ON doc_extracted_object(hash_sha256);

-- 3. 청킹 세션 테이블
CREATE TABLE IF NOT EXISTS doc_chunk_session (
  chunk_session_id BIGSERIAL PRIMARY KEY,
  file_bss_info_sno BIGINT NOT NULL REFERENCES tb_file_bss_info(file_bss_info_sno) ON DELETE CASCADE,
  extraction_session_id BIGINT NOT NULL REFERENCES doc_extraction_session(extraction_session_id) ON DELETE CASCADE,
  strategy_name VARCHAR(50) NOT NULL,
  params_json JSONB,
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'running',
  chunk_count INT
);
CREATE INDEX IF NOT EXISTS idx_chunk_session_file ON doc_chunk_session(file_bss_info_sno, strategy_name);
CREATE INDEX IF NOT EXISTS idx_chunk_session_status ON doc_chunk_session(status);

-- 4. 청크 테이블
CREATE TABLE IF NOT EXISTS doc_chunk (
  chunk_id BIGSERIAL PRIMARY KEY,
  chunk_session_id BIGINT NOT NULL REFERENCES doc_chunk_session(chunk_session_id) ON DELETE CASCADE,
  file_bss_info_sno BIGINT NOT NULL,
  chunk_index INT NOT NULL,
  source_object_ids BIGINT[] NOT NULL,
  content_text TEXT NOT NULL,
  token_count INT,
  modality VARCHAR(20) DEFAULT 'text',
  section_heading TEXT,
  page_range INT4RANGE,
  quality_score NUMERIC(5,2),
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_file ON doc_chunk(file_bss_info_sno);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_session ON doc_chunk(chunk_session_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_modality ON doc_chunk(modality);

-- 5. 임베딩 테이블
CREATE TABLE IF NOT EXISTS doc_embedding (
  embedding_id BIGSERIAL PRIMARY KEY,
  chunk_id BIGINT NOT NULL REFERENCES doc_chunk(chunk_id) ON DELETE CASCADE,
  file_bss_info_sno BIGINT NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  modality VARCHAR(20) DEFAULT 'text',
  dimension INT NOT NULL,
  vector VECTOR,
  norm_l2 REAL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(chunk_id, model_name)
);
CREATE INDEX IF NOT EXISTS idx_doc_embedding_model ON doc_embedding(model_name);
CREATE INDEX IF NOT EXISTS idx_doc_embedding_file ON doc_embedding(file_bss_info_sno);
-- (벡터 인덱스는 운영 중 파라미터 결정 후 별도 생성 권장)

-- 6. tb_document_search_index 컬럼 확장
ALTER TABLE tb_document_search_index
  ADD COLUMN IF NOT EXISTS primary_chunk_session_id BIGINT,
  ADD COLUMN IF NOT EXISTS last_embedding_model VARCHAR(100),
  ADD COLUMN IF NOT EXISTS has_table BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS has_image BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS extraction_session_id BIGINT;

COMMIT;
