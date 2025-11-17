-- Migration: add_english_tsvector_columns.sql
-- Date: 2025-10-24
-- Purpose: tb_document_search_index 테이블에 영어 전용 tsvector 추가
-- Description: 한국어 + 영어 dual configuration 검색을 위한 컬럼 추가

-- 1. 영어 tsvector 컬럼 추가
ALTER TABLE tb_document_search_index
ADD COLUMN IF NOT EXISTS content_tsvector_en tsvector,
ADD COLUMN IF NOT EXISTS keyword_tsvector_en tsvector;

-- 2. 인덱스 생성 (GIN 인덱스로 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_search_content_tsvector_en 
ON tb_document_search_index USING gin (content_tsvector_en);

CREATE INDEX IF NOT EXISTS idx_search_keyword_tsvector_en 
ON tb_document_search_index USING gin (keyword_tsvector_en);

-- 3. 컬럼 설명 추가
COMMENT ON COLUMN tb_document_search_index.content_tsvector_en IS '영어 전문검색 벡터 (English configuration)';
COMMENT ON COLUMN tb_document_search_index.keyword_tsvector_en IS '영어 키워드 검색 벡터 (English configuration)';

-- 4. 확인
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'tb_document_search_index'
AND column_name LIKE '%tsvector%'
ORDER BY column_name;

-- 5. 인덱스 확인
SELECT 
    indexname, 
    indexdef
FROM pg_indexes
WHERE tablename = 'tb_document_search_index'
AND indexname LIKE '%tsvector%'
ORDER BY indexname;
