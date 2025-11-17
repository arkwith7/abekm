-- ========================================
-- Migration: Remove kiwipiepy-related fields
-- Date: 2025-10-16
-- Reason: kiwipiepy not working, replaced by textsearch_ko
-- ========================================

BEGIN;

-- 1. 백업 테이블 생성 (롤백용)
DROP TABLE IF EXISTS tb_document_search_index_backup_20251016;
CREATE TABLE tb_document_search_index_backup_20251016 AS 
SELECT * FROM tb_document_search_index;

SELECT '✅ 백업 테이블 생성 완료: ' || COUNT(*) || '개 레코드' FROM tb_document_search_index_backup_20251016;

-- 2. 불필요한 컬럼 제거
SELECT '🔧 keywords, proper_nouns, corp_names 컬럼 제거 중...';

ALTER TABLE tb_document_search_index 
DROP COLUMN IF EXISTS keywords CASCADE,
DROP COLUMN IF EXISTS proper_nouns CASCADE,
DROP COLUMN IF EXISTS corp_names CASCADE;

SELECT '✅ 컬럼 제거 완료';

-- 3. 관련 인덱스 제거
SELECT '🔧 관련 인덱스 제거 중...';

DROP INDEX IF EXISTS idx_search_keywords;
DROP INDEX IF EXISTS idx_search_proper_nouns;
DROP INDEX IF EXISTS idx_search_corp_names;

SELECT '✅ 인덱스 제거 완료';

-- 4. 테이블 주석 업데이트
COMMENT ON TABLE tb_document_search_index IS 
'문서 검색 인덱스 (textsearch_ko 중심, kiwipiepy 제거됨 2025-10-16)';

SELECT '✅ 테이블 주석 업데이트 완료';

-- 5. 변경 사항 커밋
COMMIT;

-- 6. 테이블 구조 확인
SELECT '📋 변경 후 테이블 구조:';
SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'tb_document_search_index'
ORDER BY ordinal_position;

-- 7. 통계 업데이트
ANALYZE tb_document_search_index;

SELECT '✅ 마이그레이션 완료!';
SELECT '백업 테이블: tb_document_search_index_backup_20251016';
SELECT '롤백 방법: DROP TABLE tb_document_search_index; ALTER TABLE tb_document_search_index_backup_20251016 RENAME TO tb_document_search_index;';
