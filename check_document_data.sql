-- =============================================================================
-- 현재 데이터베이스 상태 확인 스크립트
-- =============================================================================
-- 목적: 초기화 전후 데이터 상태 확인
-- =============================================================================

\echo '================================================================================'
\echo '📊 문서 처리 데이터 통계'
\echo '================================================================================'
\echo ''

-- 테이블별 레코드 수 및 크기
SELECT 
    '📋 테이블 현황' as category,
    table_name,
    record_count,
    table_size,
    CASE 
        WHEN record_count = 0 THEN '✅ 비어있음'
        ELSE '⚠️  데이터 존재'
    END as status
FROM (
    SELECT 
        'doc_embedding' as table_name,
        COUNT(*) as record_count,
        pg_size_pretty(pg_total_relation_size('doc_embedding')) as table_size
    FROM doc_embedding
    UNION ALL
    SELECT 
        'doc_chunk',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('doc_chunk'))
    FROM doc_chunk
    UNION ALL
    SELECT 
        'doc_chunk_session',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('doc_chunk_session'))
    FROM doc_chunk_session
    UNION ALL
    SELECT 
        'doc_extracted_object',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('doc_extracted_object'))
    FROM doc_extracted_object
    UNION ALL
    SELECT 
        'doc_extraction_session',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('doc_extraction_session'))
    FROM doc_extraction_session
    UNION ALL
    SELECT 
        'vs_doc_contents_chunks',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('vs_doc_contents_chunks'))
    FROM vs_doc_contents_chunks
    UNION ALL
    SELECT 
        'tb_document_search_index',
        COUNT(*),
        pg_size_pretty(pg_total_relation_size('tb_document_search_index'))
    FROM tb_document_search_index
) stats
ORDER BY table_name;

\echo ''
\echo '================================================================================'
\echo '📄 파일 처리 상태'
\echo '================================================================================'
\echo ''

-- 파일 처리 상태별 통계
SELECT 
    processing_status,
    COUNT(*) as file_count,
    ROUND(AVG(chunk_count), 2) as avg_chunks,
    MAX(chunk_count) as max_chunks
FROM tb_file_bss_info
WHERE processing_status IS NOT NULL
GROUP BY processing_status
ORDER BY 
    CASE processing_status
        WHEN 'completed' THEN 1
        WHEN 'processing' THEN 2
        WHEN 'failed' THEN 3
        WHEN 'pending' THEN 4
        ELSE 5
    END;

\echo ''
\echo '================================================================================'
\echo '🔍 임베딩 Provider 분석'
\echo '================================================================================'
\echo ''

-- Provider별 임베딩 통계
SELECT 
    '🏷️  Provider별 분포' as category,
    COALESCE(provider, 'unknown') as provider,
    model_name,
    COUNT(*) as embedding_count,
    dimension,
    ROUND(AVG(norm_l2), 2) as avg_norm
FROM doc_embedding
GROUP BY provider, model_name, dimension
ORDER BY embedding_count DESC;

\echo ''
\echo '================================================================================'
\echo '🎨 멀티모달 데이터 분석'
\echo '================================================================================'
\echo ''

-- 모달리티별 통계
SELECT 
    modality,
    COUNT(*) as count,
    ROUND(AVG(token_count), 2) as avg_tokens
FROM doc_chunk
GROUP BY modality
ORDER BY count DESC;

\echo ''
\echo '================================================================================'
\echo '📦 백업 테이블 목록'
\echo '================================================================================'
\echo ''

-- 백업 테이블 확인
SELECT 
    tablename as backup_table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename LIKE '%_backup_%'
ORDER BY tablename;

\echo ''
\echo '================================================================================'
\echo '✅ 상태 확인 완료'
\echo '================================================================================'
