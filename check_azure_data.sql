-- =============================================================================
-- Azure 기반 데이터 확인 및 제거 스크립트
-- =============================================================================
-- 목적: Azure 환경으로 처리된 문서를 식별하고 제거
-- =============================================================================

\echo '================================================================================'
\echo '🔍 Azure 기반 데이터 분석'
\echo '================================================================================'
\echo ''

-- 1. 추출 세션별 pipeline_type 분석
\echo '📊 1. Extraction Session Pipeline Type 분석'
\echo '--------------------------------------------------------------------------------'
SELECT 
    pipeline_type,
    status,
    COUNT(*) as session_count,
    COUNT(DISTINCT file_bss_info_sno) as unique_files,
    MIN(started_at) as first_session,
    MAX(started_at) as last_session
FROM doc_extraction_session
GROUP BY pipeline_type, status
ORDER BY pipeline_type, status;

\echo ''
\echo '📊 2. 임베딩 Provider 분석'
\echo '--------------------------------------------------------------------------------'
SELECT 
    provider,
    model_name,
    COUNT(*) as embedding_count,
    dimension,
    CASE 
        WHEN provider = 'azure' OR provider = 'azure_openai' THEN '⚠️  Azure 데이터'
        WHEN provider = 'aws' OR provider = 'bedrock' THEN '✅ AWS 데이터'
        ELSE '❓ 알 수 없음'
    END as classification
FROM doc_embedding
GROUP BY provider, model_name, dimension
ORDER BY embedding_count DESC;

\echo ''
\echo '📊 3. Azure 모델을 사용한 임베딩 상세'
\echo '--------------------------------------------------------------------------------'
SELECT 
    de.provider,
    de.model_name,
    de.dimension,
    COUNT(DISTINCT de.file_bss_info_sno) as affected_files,
    COUNT(*) as embedding_count,
    COUNT(de.azure_vector_1536) as azure_1536_count,
    COUNT(de.azure_vector_3072) as azure_3072_count,
    COUNT(de.azure_clip_vector) as azure_clip_count
FROM doc_embedding de
WHERE de.model_name LIKE '%azure%' 
   OR de.model_name LIKE '%text-embedding-3%'
   OR de.model_name LIKE '%ada%'
   OR de.provider IN ('azure', 'azure_openai')
GROUP BY de.provider, de.model_name, de.dimension;

\echo ''
\echo '📊 4. Azure로 처리된 파일 목록 (처리 완료)'
\echo '--------------------------------------------------------------------------------'
SELECT 
    f.file_bss_info_sno,
    f.file_lgc_nm as filename,
    f.knowledge_container_id,
    des.pipeline_type,
    des.provider,
    des.started_at,
    f.processing_status,
    f.chunk_count,
    COUNT(DISTINCT de.embedding_id) as embedding_count
FROM tb_file_bss_info f
JOIN doc_extraction_session des ON f.file_bss_info_sno = des.file_bss_info_sno
LEFT JOIN doc_embedding de ON f.file_bss_info_sno = de.file_bss_info_sno
WHERE des.pipeline_type != 'bedrock'
  AND des.status = 'success'
  AND f.processing_status = 'completed'
GROUP BY f.file_bss_info_sno, f.file_lgc_nm, f.knowledge_container_id, 
         des.pipeline_type, des.provider, des.started_at, f.processing_status, f.chunk_count
ORDER BY des.started_at DESC;

\echo ''
\echo '📊 5. 요약 통계'
\echo '--------------------------------------------------------------------------------'
WITH azure_files AS (
    SELECT DISTINCT des.file_bss_info_sno
    FROM doc_extraction_session des
    WHERE des.pipeline_type != 'bedrock'
      AND des.status = 'success'
),
aws_files AS (
    SELECT DISTINCT des.file_bss_info_sno
    FROM doc_extraction_session des
    WHERE des.pipeline_type = 'bedrock'
      AND des.status = 'success'
)
SELECT 
    '전체 파일' as category,
    COUNT(*) as count
FROM tb_file_bss_info
WHERE processing_status = 'completed'
UNION ALL
SELECT 
    'Azure 처리 파일',
    COUNT(*)
FROM azure_files
UNION ALL
SELECT 
    'AWS 처리 파일',
    COUNT(*)
FROM aws_files
UNION ALL
SELECT 
    'Azure 임베딩',
    COUNT(*)
FROM doc_embedding
WHERE provider IN ('azure', 'azure_openai')
   OR model_name LIKE '%azure%'
   OR model_name LIKE '%text-embedding-3%'
UNION ALL
SELECT 
    'AWS 임베딩',
    COUNT(*)
FROM doc_embedding
WHERE provider IN ('aws', 'bedrock')
   OR model_name LIKE '%titan%'
   OR model_name LIKE '%amazon%';

\echo ''
\echo '================================================================================'
\echo '⚠️  Azure 데이터 제거 권장 사항'
\echo '================================================================================'
\echo ''
\echo '다음 명령으로 Azure 데이터만 선택적으로 제거할 수 있습니다:'
\echo ''
\echo '-- Azure로 처리된 문서의 임베딩 삭제'
\echo 'DELETE FROM doc_embedding WHERE provider IN (''azure'', ''azure_openai'');'
\echo ''
\echo '-- Azure로 처리된 문서의 파일 상태 초기화'
\echo 'UPDATE tb_file_bss_info SET processing_status = ''pending'' WHERE file_bss_info_sno IN ('
\echo '    SELECT DISTINCT file_bss_info_sno FROM doc_extraction_session WHERE pipeline_type != ''bedrock'''
\echo ');'
\echo ''
\echo '또는 reset_document_data.sh 스크립트를 사용하여 전체 초기화를 수행하세요.'
\echo ''
\echo '================================================================================'
