-- ============================================================================
-- 완전 데이터베이스 초기화 스크립트 (간소화 버전)
-- ============================================================================

BEGIN;

-- 백업 생성
CREATE TABLE IF NOT EXISTS tb_file_bss_info_final_backup AS SELECT * FROM tb_file_bss_info;

-- 삭제 전 통계
SELECT '📊 삭제 전 통계' as status, 
       COUNT(*) as total_files,
       COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_files
FROM tb_file_bss_info WHERE del_yn != 'Y';

-- 완전 초기화
TRUNCATE TABLE doc_embedding CASCADE;
TRUNCATE TABLE doc_chunk CASCADE;
TRUNCATE TABLE doc_chunk_session CASCADE;
TRUNCATE TABLE doc_extracted_object CASCADE;
TRUNCATE TABLE doc_extraction_session CASCADE;
TRUNCATE TABLE vs_doc_contents_chunks CASCADE;
TRUNCATE TABLE tb_document_search_index CASCADE;

-- 파일 메타데이터 완전 삭제
DELETE FROM tb_file_bss_info;

-- 시퀀스 초기화
ALTER SEQUENCE doc_embedding_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_chunk_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_chunk_session_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_extracted_object_id_seq RESTART WITH 1;
ALTER SEQUENCE doc_extraction_session_id_seq RESTART WITH 1;
ALTER SEQUENCE vs_doc_contents_chunks_id_seq RESTART WITH 1;

-- 초기화 후 통계
SELECT '📊 초기화 후 통계' as status;

SELECT 
    'doc_embedding' as table_name, COUNT(*) as count FROM doc_embedding
UNION ALL SELECT 'doc_chunk', COUNT(*) FROM doc_chunk
UNION ALL SELECT 'doc_extraction_session', COUNT(*) FROM doc_extraction_session
UNION ALL SELECT 'tb_file_bss_info', COUNT(*) FROM tb_file_bss_info
ORDER BY table_name;

SELECT '🎉 완전 초기화 완료!' as message;

COMMIT;
