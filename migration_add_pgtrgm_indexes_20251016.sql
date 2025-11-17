-- ========================================
-- Optimized Indexes for textsearch_ko
-- Date: 2025-10-16
-- Purpose: 검색 성능 향상 (pg_trgm 추가)
-- ========================================

BEGIN;

-- 1. pg_trgm 확장 설치 (이미 설치되어 있을 수 있음)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SELECT '✅ pg_trgm 확장 설치 완료';

-- 2. 기존 textsearch_ko 인덱스 확인
SELECT '📋 기존 FTS 인덱스:';
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tb_document_search_index'
    AND indexname LIKE '%tsvector%';

-- 3. full_content에 대한 pg_trgm GIN 인덱스 생성
SELECT '🔧 full_content pg_trgm 인덱스 생성 중...';

DROP INDEX IF EXISTS idx_search_full_content_trgm;
CREATE INDEX idx_search_full_content_trgm 
ON tb_document_search_index 
USING gin(full_content gin_trgm_ops);

SELECT '✅ full_content 인덱스 생성 완료';

-- 4. document_title에 대한 pg_trgm GIN 인덱스 생성
SELECT '🔧 document_title pg_trgm 인덱스 생성 중...';

DROP INDEX IF EXISTS idx_search_document_title_trgm;
CREATE INDEX idx_search_document_title_trgm 
ON tb_document_search_index 
USING gin(document_title gin_trgm_ops);

SELECT '✅ document_title 인덱스 생성 완료';

-- 5. 복합 인덱스 추가 (검색 성능 향상)
SELECT '🔧 복합 인덱스 생성 중...';

DROP INDEX IF EXISTS idx_search_container_status_fts;
CREATE INDEX idx_search_container_status_fts 
ON tb_document_search_index (
    knowledge_container_id, 
    indexing_status
) 
WHERE indexing_status = 'indexed';

SELECT '✅ 복합 인덱스 생성 완료';

-- 6. 통계 업데이트
ANALYZE tb_document_search_index;

-- 7. 변경 사항 커밋
COMMIT;

-- 8. 생성된 인덱스 확인
SELECT '📋 생성된 모든 인덱스:';
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tb_document_search_index'
ORDER BY indexname;

-- 9. 인덱스 크기 확인
SELECT '📊 인덱스 크기:';
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE tablename = 'tb_document_search_index'
ORDER BY pg_relation_size(indexname::regclass) DESC;

SELECT '✅ 인덱스 최적화 완료!';
