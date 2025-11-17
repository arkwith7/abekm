-- Migration: populate_english_tsvectors.sql
-- Date: 2025-10-24
-- Purpose: 기존 문서들의 영어 tsvector 생성
-- Description: 이미 존재하는 모든 문서에 대해 영어 tsvector 생성

-- 1. 마이그레이션 시작 로그
DO $$
BEGIN
    RAISE NOTICE '영어 tsvector 마이그레이션 시작...';
    RAISE NOTICE '현재 시간: %', now();
END $$;

-- 2. 마이그레이션 전 상태 확인
SELECT 
    '마이그레이션 전 상태' as status,
    COUNT(*) as total_docs,
    COUNT(content_tsvector) as ko_content_indexed,
    COUNT(keyword_tsvector) as ko_keyword_indexed,
    COUNT(content_tsvector_en) as en_content_indexed,
    COUNT(keyword_tsvector_en) as en_keyword_indexed
FROM tb_document_search_index;

-- 3. 영어 tsvector 생성 (배치 처리)
UPDATE tb_document_search_index
SET 
    content_tsvector_en = to_tsvector('english',
        COALESCE(document_title, '') || ' ' ||
        COALESCE(content_summary, '') || ' ' ||
        COALESCE(substring(full_content, 1, 50000), '')
    ),
    keyword_tsvector_en = to_tsvector('english',
        COALESCE(array_to_string(keywords, ' '), '') || ' ' ||
        COALESCE(array_to_string(proper_nouns, ' '), '') || ' ' ||
        COALESCE(array_to_string(corp_names, ' '), '') || ' ' ||
        COALESCE(array_to_string(main_topics, ' '), '')
    )
WHERE content_tsvector_en IS NULL OR keyword_tsvector_en IS NULL;

-- 4. 마이그레이션 후 상태 확인
SELECT 
    '마이그레이션 후 상태' as status,
    COUNT(*) as total_docs,
    COUNT(content_tsvector) as ko_content_indexed,
    COUNT(keyword_tsvector) as ko_keyword_indexed,
    COUNT(content_tsvector_en) as en_content_indexed,
    COUNT(keyword_tsvector_en) as en_keyword_indexed,
    COUNT(CASE WHEN content_tsvector_en IS NOT NULL AND keyword_tsvector_en IS NOT NULL THEN 1 END) as fully_indexed
FROM tb_document_search_index;

-- 5. 샘플 데이터 확인 (문서 71)
SELECT 
    '문서 71 tsvector 확인' as info,
    search_doc_id,
    file_bss_info_sno,
    -- 한국어 tsvector 토큰 샘플
    array_length(tsvector_to_array(content_tsvector), 1) as ko_content_tokens,
    array_length(tsvector_to_array(keyword_tsvector), 1) as ko_keyword_tokens,
    -- 영어 tsvector 토큰 샘플
    array_length(tsvector_to_array(content_tsvector_en), 1) as en_content_tokens,
    array_length(tsvector_to_array(keyword_tsvector_en), 1) as en_keyword_tokens
FROM tb_document_search_index
WHERE file_bss_info_sno = 71;

-- 6. 영어 tsvector 검색 테스트 (문서 71)
SELECT 
    '영어 검색 테스트' as test,
    search_doc_id,
    file_bss_info_sno,
    -- 'Figure' 검색
    content_tsvector_en @@ to_tsquery('english', 'Figure') as matches_figure,
    ts_rank(content_tsvector_en, to_tsquery('english', 'Figure')) as rank_figure,
    -- 'Research & Model' 검색
    content_tsvector_en @@ to_tsquery('english', 'Research & Model') as matches_research,
    ts_rank(content_tsvector_en, to_tsquery('english', 'Research & Model')) as rank_research
FROM tb_document_search_index
WHERE file_bss_info_sno = 71;

-- 7. 마이그레이션 완료 로그
DO $$
BEGIN
    RAISE NOTICE '영어 tsvector 마이그레이션 완료!';
    RAISE NOTICE '현재 시간: %', now();
END $$;
