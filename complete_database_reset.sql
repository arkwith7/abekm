-- ============================================================================
-- 완전 데이터베이스 초기화 스크립트 (옵션 1: 완전 삭제)
-- ============================================================================
-- 목적: Azure 환경 데이터를 완전히 삭제하고 깨끗한 AWS 전용 환경 구축
-- 실행 시점: AWS 마이그레이션 완료 후
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1단계: 최종 백업 생성 (안전장치)
-- ============================================================================

DO $$
DECLARE
    backup_suffix TEXT := to_char(now(), 'YYYYMMDD_HH24MISS');
BEGIN
    -- tb_file_bss_info 백업 (파일 메타데이터)
    EXECUTE format('CREATE TABLE IF NOT EXISTS tb_file_bss_info_final_backup_%s AS SELECT * FROM tb_file_bss_info', backup_suffix);
    RAISE NOTICE '✅ tb_file_bss_info 최종 백업 완료: tb_file_bss_info_final_backup_%', backup_suffix;
END $$;

-- ============================================================================
-- 2단계: 통계 정보 수집 (삭제 전)
-- ============================================================================

SELECT '📊 삭제 전 통계' as status, now() as timestamp;

SELECT 
    '📄 파일 메타데이터' as category,
    COUNT(*) as total_files,
    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_files,
    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_files,
    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_files
FROM tb_file_bss_info
WHERE del_yn != 'Y';

SELECT 
    'knowledge_container_id' as dimension,
    knowledge_container_id,
    COUNT(*) as file_count
FROM tb_file_bss_info
WHERE del_yn != 'Y'
GROUP BY knowledge_container_id
ORDER BY file_count DESC;

-- ============================================================================
-- 3단계: 완전 초기화 실행
-- ============================================================================

-- 3-1. 문서 처리 관련 테이블 완전 삭제 (CASCADE)
TRUNCATE TABLE doc_embedding CASCADE;
TRUNCATE TABLE doc_chunk CASCADE;
TRUNCATE TABLE doc_chunk_session CASCADE;
TRUNCATE TABLE doc_extracted_object CASCADE;
TRUNCATE TABLE doc_extraction_session CASCADE;
TRUNCATE TABLE vs_doc_contents_chunks CASCADE;
TRUNCATE TABLE tb_document_search_index CASCADE;

RAISE NOTICE '✅ 문서 처리 테이블 완전 초기화 완료';

-- 3-2. 파일 메타데이터 완전 삭제 (논리 삭제 → 물리 삭제)
DELETE FROM tb_file_bss_info;

RAISE NOTICE '✅ 파일 메타데이터 완전 삭제 완료';

-- 3-3. 시퀀스 초기화
ALTER SEQUENCE doc_embedding_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_chunk_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_chunk_session_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_extracted_object_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_extraction_session_id_seq RESTART WITH 1;
ALTER SEQUENCE vs_doc_contents_chunks_id_seq RESTART WITH 1;

RAISE NOTICE '✅ 모든 시퀀스 초기화 완료';

-- ============================================================================
-- 4단계: 초기화 후 통계 확인
-- ============================================================================

SELECT '📊 초기화 후 통계' as status, now() as timestamp;

SELECT 
    'doc_embedding' as table_name, COUNT(*) as record_count FROM doc_embedding
UNION ALL
SELECT 'doc_chunk', COUNT(*) FROM doc_chunk
UNION ALL
SELECT 'doc_chunk_session', COUNT(*) FROM doc_chunk_session
UNION ALL
SELECT 'doc_extracted_object', COUNT(*) FROM doc_extracted_object
UNION ALL
SELECT 'doc_extraction_session', COUNT(*) FROM doc_extraction_session
UNION ALL
SELECT 'vs_doc_contents_chunks', COUNT(*) FROM vs_doc_contents_chunks
UNION ALL
SELECT 'tb_document_search_index', COUNT(*) FROM tb_document_search_index
UNION ALL
SELECT 'tb_file_bss_info (active)', COUNT(*) FROM tb_file_bss_info WHERE del_yn != 'Y'
ORDER BY table_name;

-- ============================================================================
-- 5단계: 백업 테이블 목록
-- ============================================================================

SELECT 
    '📦 백업 테이블 정보' as info,
    tablename as backup_table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as backup_size
FROM pg_tables
WHERE tablename LIKE '%backup%'
  AND schemaname = 'public'
ORDER BY tablename DESC
LIMIT 10;

-- ============================================================================
-- 최종 확인 메시지
-- ============================================================================

SELECT 
    '🎉 데이터베이스 완전 초기화 완료!' as message,
    '모든 문서 데이터가 삭제되었습니다.' as status,
    '백업 테이블에서 복구 가능' as recovery_info;

COMMIT;

-- ============================================================================
-- 복구 방법 (필요 시)
-- ============================================================================
-- 
-- 1. 최종 백업에서 복구:
--    INSERT INTO tb_file_bss_info SELECT * FROM tb_file_bss_info_final_backup_YYYYMMDD_HHMMSS;
--
-- 2. 이전 백업에서 복구:
--    INSERT INTO doc_embedding SELECT * FROM doc_embedding_backup_YYYYMMDD_HHMMSS;
--    INSERT INTO doc_chunk SELECT * FROM doc_chunk_backup_YYYYMMDD_HHMMSS;
--    ... (필요한 테이블 반복)
--
-- 3. 시퀀스 재조정:
--    SELECT setval('doc_embedding_id_seq', (SELECT MAX(id) FROM doc_embedding));
--
-- ============================================================================
