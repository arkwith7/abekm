-- =============================================================================
-- 문서 처리 관련 데이터 초기화 스크립트
-- =============================================================================
-- 목적: Azure 데이터로 오염된 AWS 환경 데이터를 완전히 초기화
-- 실행일: 2025-11-17
-- 주의: 이 스크립트는 모든 문서 임베딩, 청킹, 추출 데이터를 삭제합니다!
-- =============================================================================

BEGIN;

-- 1. 임베딩 데이터 삭제 (가장 하위 테이블부터)
TRUNCATE TABLE doc_embedding CASCADE;
ALTER SEQUENCE doc_embedding_embedding_id_seq RESTART WITH 1;
SELECT '✅ doc_embedding 테이블 초기화 완료' as status;

-- 2. 청크 데이터 삭제
TRUNCATE TABLE doc_chunk CASCADE;
ALTER SEQUENCE doc_chunk_chunk_id_seq RESTART WITH 1;
SELECT '✅ doc_chunk 테이블 초기화 완료' as status;

-- 3. 청킹 세션 삭제
TRUNCATE TABLE doc_chunk_session CASCADE;
ALTER SEQUENCE doc_chunk_session_chunk_session_id_seq RESTART WITH 1;
SELECT '✅ doc_chunk_session 테이블 초기화 완료' as status;

-- 4. 추출된 객체 삭제
TRUNCATE TABLE doc_extracted_object CASCADE;
ALTER SEQUENCE doc_extracted_object_object_id_seq RESTART WITH 1;
SELECT '✅ doc_extracted_object 테이블 초기화 완료' as status;

-- 5. 추출 세션 삭제
TRUNCATE TABLE doc_extraction_session CASCADE;
ALTER SEQUENCE doc_extraction_session_extraction_session_id_seq RESTART WITH 1;
SELECT '✅ doc_extraction_session 테이블 초기화 완료' as status;

-- 6. 레거시 벡터 청크 테이블 초기화
TRUNCATE TABLE vs_doc_contents_chunks CASCADE;
ALTER SEQUENCE vs_doc_contents_chunks_chunk_sno_seq RESTART WITH 1;
SELECT '✅ vs_doc_contents_chunks 테이블 초기화 완료' as status;

-- 7. 검색 인덱스 테이블 초기화
TRUNCATE TABLE tb_document_search_index CASCADE;
-- tb_document_search_index에 시퀀스가 있다면 재시작
-- ALTER SEQUENCE tb_document_search_index_id_seq RESTART WITH 1;
SELECT '✅ tb_document_search_index 테이블 초기화 완료' as status;

-- 8. 파일 메타정보 테이블의 처리 상태 초기화 (파일 자체는 유지)
UPDATE tb_file_bss_info 
SET 
    processing_status = 'pending',
    processing_started_at = NULL,
    processing_completed_at = NULL,
    processing_error = NULL,
    chunk_count = 0
WHERE processing_status IS NOT NULL;
SELECT '✅ tb_file_bss_info 처리 상태 초기화 완료' as status;

-- 9. 통계 정보 확인
SELECT 
    '📊 초기화 후 통계' as category,
    'doc_embedding' as table_name,
    COUNT(*) as record_count
FROM doc_embedding
UNION ALL
SELECT '📊 초기화 후 통계', 'doc_chunk', COUNT(*) FROM doc_chunk
UNION ALL
SELECT '📊 초기화 후 통계', 'doc_chunk_session', COUNT(*) FROM doc_chunk_session
UNION ALL
SELECT '📊 초기화 후 통계', 'doc_extracted_object', COUNT(*) FROM doc_extracted_object
UNION ALL
SELECT '📊 초기화 후 통계', 'doc_extraction_session', COUNT(*) FROM doc_extraction_session
UNION ALL
SELECT '📊 초기화 후 통계', 'vs_doc_contents_chunks', COUNT(*) FROM vs_doc_contents_chunks
UNION ALL
SELECT '📊 초기화 후 통계', 'tb_document_search_index', COUNT(*) FROM tb_document_search_index
UNION ALL
SELECT '📊 파일 상태', 'pending 파일 수', COUNT(*) 
FROM tb_file_bss_info 
WHERE processing_status = 'pending';

COMMIT;

-- =============================================================================
-- 실행 결과 요약
-- =============================================================================
SELECT 
    '🎉 데이터베이스 초기화 완료!' as message,
    '모든 문서 처리 데이터가 삭제되었습니다.' as detail,
    '새로운 문서를 업로드하면 AWS 환경으로 처리됩니다.' as next_step;
