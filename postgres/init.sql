-- 데이터베이스 초기화 시 확장 설치
-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- Mecab 기반 한국어 형태소 분석 (textsearch_ko)
CREATE EXTENSION IF NOT EXISTS textsearch_ko;

-- 기본 텍스트 검색 구성을 Mecab 기반 'public.korean'으로 설정
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_ts_config WHERE cfgname = 'korean') THEN
        EXECUTE format(
            'ALTER DATABASE %I SET default_text_search_config = %L',
            current_database(),
            'public.korean'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- pg_trgm 확장 활성화 (kor_search 의존성)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- kor_search 확장 활성화
CREATE EXTENSION IF NOT EXISTS kor_search;

-- 기본 단어 데이터 추가
INSERT INTO kor_search_word_transform (keyword) 
SELECT keyword FROM (VALUES 
    ('ai'), ('ml'), ('data'), ('science'), ('python'), ('java'), ('javascript'),
    ('react'), ('vue'), ('angular'), ('node'), ('express'), ('spring'), ('django'),
    ('flask'), ('fastapi'), ('docker'), ('kubernetes'), ('aws'), ('azure'), ('gcp'),
    ('lg'), ('apple'), ('samsung'), ('microsoft'), ('google'), ('meta'), ('tesla'),
    ('nvidia'), ('amd'), ('intel'), ('ibm'), ('oracle'), ('salesforce'), ('netflix')
) AS new_keywords(keyword)
WHERE NOT EXISTS (
    SELECT 1 FROM kor_search_word_transform 
    WHERE kor_search_word_transform.keyword = new_keywords.keyword
);

-- 유사어 추가
WITH keyword_synonyms AS (
    SELECT 'ai' as keyword, '인공지능' as synonym
    UNION ALL SELECT 'ai', 'AI'
    UNION ALL SELECT 'ai', '에이아이'
    UNION ALL SELECT 'ml', '머신러닝'
    UNION ALL SELECT 'ml', '기계학습'
    UNION ALL SELECT 'ml', 'ML'
    UNION ALL SELECT 'data', '데이터'
    UNION ALL SELECT 'science', '과학'
    UNION ALL SELECT 'python', '파이썬'
    UNION ALL SELECT 'java', '자바'
    UNION ALL SELECT 'javascript', '자바스크립트'
    UNION ALL SELECT 'javascript', 'JS'
    UNION ALL SELECT 'react', '리액트'
    UNION ALL SELECT 'vue', '뷰'
    UNION ALL SELECT 'angular', '앵귤러'
    UNION ALL SELECT 'docker', '도커'
    UNION ALL SELECT 'kubernetes', '쿠버네티스'
    UNION ALL SELECT 'kubernetes', 'k8s'
    UNION ALL SELECT 'aws', '아마존'
    UNION ALL SELECT 'aws', 'Amazon'
    UNION ALL SELECT 'aws', 'AWS'
    UNION ALL SELECT 'azure', '애저'
    UNION ALL SELECT 'azure', 'Microsoft Azure'
    UNION ALL SELECT 'gcp', '구글'
    UNION ALL SELECT 'gcp', 'Google Cloud'
    UNION ALL SELECT 'lg', '엘지'
    UNION ALL SELECT 'lg', 'LG전자'
    UNION ALL SELECT 'apple', '애플'
    UNION ALL SELECT 'apple', '사과'
    UNION ALL SELECT 'samsung', '삼성'
    UNION ALL SELECT 'samsung', '삼성전자'
    UNION ALL SELECT 'microsoft', '마이크로소프트'
    UNION ALL SELECT 'microsoft', 'MS'
    UNION ALL SELECT 'google', '구글'
    UNION ALL SELECT 'google', 'Google'
    UNION ALL SELECT 'meta', '메타'
    UNION ALL SELECT 'meta', 'Meta'
    UNION ALL SELECT 'meta', '페이스북'
    UNION ALL SELECT 'tesla', '테슬라'
    UNION ALL SELECT 'tesla', 'Tesla'
    UNION ALL SELECT 'nvidia', '엔비디아'
    UNION ALL SELECT 'nvidia', 'NVIDIA'
    UNION ALL SELECT 'amd', 'AMD'
    UNION ALL SELECT 'intel', '인텔'
    UNION ALL SELECT 'intel', 'Intel'
    UNION ALL SELECT 'ibm', 'IBM'
    UNION ALL SELECT 'oracle', '오라클'
    UNION ALL SELECT 'oracle', 'Oracle'
    UNION ALL SELECT 'salesforce', '세일즈포스'
    UNION ALL SELECT 'netflix', '넷플릭스'
)
INSERT INTO kor_search_word_synonyms (keyword_id, synonym)
SELECT 
    (SELECT id FROM kor_search_word_transform WHERE keyword = ks.keyword),
    ks.synonym
FROM keyword_synonyms ks
WHERE EXISTS (SELECT 1 FROM kor_search_word_transform WHERE keyword = ks.keyword)
AND NOT EXISTS (
    SELECT 1 FROM kor_search_word_synonyms wss
    JOIN kor_search_word_transform wst ON wss.keyword_id = wst.id
    WHERE wst.keyword = ks.keyword AND wss.synonym = ks.synonym
);