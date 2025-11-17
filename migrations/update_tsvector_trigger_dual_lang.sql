-- Migration: update_tsvector_trigger_dual_lang.sql
-- Date: 2025-10-24
-- Purpose: 한국어 + 영어 dual configuration tsvector 트리거 함수 생성
-- Description: 기존 한국어 tsvector에 영어 tsvector 추가 생성

-- 1. Content tsvector 업데이트 함수 (한국어 + 영어)
CREATE OR REPLACE FUNCTION public.update_search_index_content_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    -- 한국어 content_tsvector (기존 로직 유지)
    NEW.content_tsvector := to_tsvector('korean',
        COALESCE(NEW.document_title, '') || ' ' ||
        COALESCE(NEW.content_summary, '') || ' ' ||
        COALESCE(substring(NEW.full_content, 1, 50000), '')
    );
    
    -- 영어 content_tsvector (새로 추가)
    -- English configuration은 stemming, stopword 제거 등 영어 최적화 적용
    NEW.content_tsvector_en := to_tsvector('english',
        COALESCE(NEW.document_title, '') || ' ' ||
        COALESCE(NEW.content_summary, '') || ' ' ||
        COALESCE(substring(NEW.full_content, 1, 50000), '')
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Keyword tsvector 업데이트 함수 (한국어 + 영어)
CREATE OR REPLACE FUNCTION public.update_search_index_keyword_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    -- 한국어 keyword_tsvector (기존 로직)
    NEW.keyword_tsvector := to_tsvector('korean', 
        COALESCE(array_to_string(NEW.keywords, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.proper_nouns, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.corp_names, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.main_topics, ' '), '')
    );
    
    -- 영어 keyword_tsvector (새로 추가)
    NEW.keyword_tsvector_en := to_tsvector('english',
        COALESCE(array_to_string(NEW.keywords, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.proper_nouns, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.corp_names, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.main_topics, ' '), '')
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. 기존 트리거 삭제
DROP TRIGGER IF EXISTS tsvector_update_content ON tb_document_search_index;
DROP TRIGGER IF EXISTS tsvector_update_keyword ON tb_document_search_index;

-- 4. 새로운 트리거 생성 (content)
CREATE TRIGGER tsvector_update_content
BEFORE INSERT OR UPDATE OF full_content, document_title, content_summary
ON tb_document_search_index
FOR EACH ROW
EXECUTE FUNCTION update_search_index_content_tsvector();

-- 5. 새로운 트리거 생성 (keyword)
CREATE TRIGGER tsvector_update_keyword
BEFORE INSERT OR UPDATE OF document_title, content_summary
ON tb_document_search_index
FOR EACH ROW
EXECUTE FUNCTION update_search_index_keyword_tsvector();

-- 6. 트리거 확인
SELECT 
    trigger_name, 
    event_manipulation, 
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE event_object_table = 'tb_document_search_index'
AND trigger_name LIKE '%tsvector%'
ORDER BY trigger_name;

-- 7. 함수 확인
SELECT 
    routine_name,
    routine_type,
    data_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name LIKE '%search_index%tsvector%'
ORDER BY routine_name;
