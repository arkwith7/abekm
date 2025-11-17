-- kor_search 대안 함수들 (Azure/AWS RDS 호환)
-- 이 파일은 kor_search 확장을 사용할 수 없는 클라우드 RDS 환경에서 사용합니다.

-- pg_trgm 확장 설치 (Azure/AWS RDS에서 지원)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 한국어-영어 매핑 테이블 생성
CREATE TABLE IF NOT EXISTS korean_english_mapping (
    id SERIAL PRIMARY KEY,
    korean_term TEXT NOT NULL,
    english_term TEXT NOT NULL,
    category VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(korean_term, english_term)
);

-- 매핑 테이블에 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_ke_mapping_korean ON korean_english_mapping USING gin(korean_term gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ke_mapping_english ON korean_english_mapping USING gin(english_term gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ke_mapping_category ON korean_english_mapping(category);

-- 기본 매핑 데이터 삽입
INSERT INTO korean_english_mapping (korean_term, english_term, category) VALUES
-- AI/기술 관련
('인공지능', 'ai', 'technology'),
('에이아이', 'ai', 'technology'),
('머신러닝', 'ml', 'technology'),
('기계학습', 'ml', 'technology'),
('딥러닝', 'deep learning', 'technology'),
('데이터', 'data', 'technology'),
('과학', 'science', 'technology'),
-- 프로그래밍 언어
('파이썬', 'python', 'programming'),
('자바', 'java', 'programming'),
('자바스크립트', 'javascript', 'programming'),
('리액트', 'react', 'programming'),
('뷰', 'vue', 'programming'),
('앵귤러', 'angular', 'programming'),
-- 기업명
('삼성', 'samsung', 'company'),
('삼성전자', 'samsung', 'company'),
('엘지', 'lg', 'company'),
('LG전자', 'lg', 'company'),
('애플', 'apple', 'company'),
('마이크로소프트', 'microsoft', 'company'),
('구글', 'google', 'company'),
('아마존', 'amazon', 'company'),
('메타', 'meta', 'company'),
('페이스북', 'meta', 'company'),
-- 클라우드/인프라
('도커', 'docker', 'infrastructure'),
('쿠버네티스', 'kubernetes', 'infrastructure'),
('k8s', 'kubernetes', 'infrastructure'),
('애저', 'azure', 'infrastructure'),
('AWS', 'amazon', 'infrastructure')
ON CONFLICT (korean_term, english_term) DO NOTHING;

-- kor_search_like 대안 함수
CREATE OR REPLACE FUNCTION rds_kor_search_like(
    input_text TEXT,
    search_text TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    expanded_terms TEXT[];
    term TEXT;
    normalized_input TEXT;
    normalized_search TEXT;
BEGIN
    -- NULL 체크
    IF input_text IS NULL OR search_text IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- 텍스트 정규화 (소문자, 공백 제거)
    normalized_input := LOWER(TRIM(input_text));
    normalized_search := LOWER(TRIM(search_text));
    
    -- 직접 매치 확인
    IF normalized_input LIKE '%' || normalized_search || '%' THEN
        RETURN TRUE;
    END IF;
    
    -- 매핑 테이블에서 관련 용어 찾기
    SELECT ARRAY_AGG(DISTINCT term_variant) INTO expanded_terms
    FROM (
        -- 검색어가 한국어인 경우 -> 영어 찾기
        SELECT english_term as term_variant
        FROM korean_english_mapping 
        WHERE LOWER(korean_term) LIKE '%' || normalized_search || '%'
        
        UNION
        
        -- 검색어가 영어인 경우 -> 한국어 찾기  
        SELECT korean_term as term_variant
        FROM korean_english_mapping 
        WHERE LOWER(english_term) LIKE '%' || normalized_search || '%'
        
        UNION
        
        -- 원본 검색어도 포함
        SELECT normalized_search as term_variant
    ) t
    WHERE term_variant IS NOT NULL;
    
    -- 확장된 용어들로 검색
    IF expanded_terms IS NOT NULL THEN
        FOREACH term IN ARRAY expanded_terms LOOP
            IF normalized_input LIKE '%' || LOWER(term) || '%' THEN
                RETURN TRUE;
            END IF;
        END LOOP;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- kor_search_tsvector 대안 함수
CREATE OR REPLACE FUNCTION rds_kor_search_tsvector(
    input_text TEXT,
    search_text TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    input_tsvector TSVECTOR;
    search_tsquery TSQUERY;
    expanded_terms TEXT[];
    term TEXT;
    query_parts TEXT[] := '{}';
BEGIN
    -- NULL 체크
    IF input_text IS NULL OR search_text IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- 매핑 테이블에서 관련 용어 찾기
    SELECT ARRAY_AGG(DISTINCT term_variant) INTO expanded_terms
    FROM (
        SELECT english_term as term_variant
        FROM korean_english_mapping 
        WHERE LOWER(korean_term) LIKE '%' || LOWER(search_text) || '%'
        
        UNION
        
        SELECT korean_term as term_variant
        FROM korean_english_mapping 
        WHERE LOWER(english_term) LIKE '%' || LOWER(search_text) || '%'
        
        UNION
        
        SELECT search_text as term_variant
    ) t
    WHERE term_variant IS NOT NULL;
    
    -- tsvector 생성
    input_tsvector := to_tsvector('simple', input_text);
    
    -- 확장된 용어들로 OR 쿼리 생성
    IF expanded_terms IS NOT NULL THEN
        FOREACH term IN ARRAY expanded_terms LOOP
            query_parts := array_append(query_parts, term);
        END LOOP;
        
        -- OR 쿼리 생성 및 실행
        IF array_length(query_parts, 1) > 0 THEN
            search_tsquery := to_tsquery('simple', array_to_string(query_parts, ' | '));
            RETURN input_tsvector @@ search_tsquery;
        END IF;
    END IF;
    
    RETURN FALSE;
EXCEPTION
    WHEN OTHERS THEN
        -- tsquery 생성 실패 시 fallback to LIKE
        RETURN rds_kor_search_like(input_text, search_text);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- kor_search_similar 대안 함수
CREATE OR REPLACE FUNCTION rds_kor_search_similar(
    input_text TEXT,
    search_text TEXT,
    similarity_threshold FLOAT DEFAULT 0.3
) RETURNS BOOLEAN AS $$
DECLARE
    expanded_terms TEXT[];
    term TEXT;
    max_similarity FLOAT := 0.0;
    current_similarity FLOAT;
BEGIN
    -- NULL 체크
    IF input_text IS NULL OR search_text IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- 매핑 테이블에서 관련 용어 찾기
    SELECT ARRAY_AGG(DISTINCT term_variant) INTO expanded_terms
    FROM (
        SELECT english_term as term_variant
        FROM korean_english_mapping 
        WHERE similarity(korean_term, search_text) > similarity_threshold
        
        UNION
        
        SELECT korean_term as term_variant
        FROM korean_english_mapping 
        WHERE similarity(english_term, search_text) > similarity_threshold
        
        UNION
        
        SELECT search_text as term_variant
    ) t
    WHERE term_variant IS NOT NULL;
    
    -- 각 확장된 용어와의 유사도 계산
    IF expanded_terms IS NOT NULL THEN
        FOREACH term IN ARRAY expanded_terms LOOP
            current_similarity := similarity(input_text, term);
            IF current_similarity > max_similarity THEN
                max_similarity := current_similarity;
            END IF;
        END LOOP;
    END IF;
    
    RETURN max_similarity > similarity_threshold;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- kor_search_regex 대안 함수 (정규식 검색)
CREATE OR REPLACE FUNCTION rds_kor_search_regex(
    input_text TEXT,
    pattern TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    expanded_patterns TEXT[];
    single_pattern TEXT;
    expanded_pattern TEXT := '';
BEGIN
    -- NULL 체크
    IF input_text IS NULL OR pattern IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- 패턴에서 개별 용어 추출 (| 로 분할)
    expanded_patterns := string_to_array(pattern, '|');
    
    -- 각 패턴을 확장
    FOREACH single_pattern IN ARRAY expanded_patterns LOOP
        -- 매핑 테이블에서 관련 용어 찾기
        SELECT string_agg(term_variant, '|') INTO expanded_pattern
        FROM (
            SELECT DISTINCT term_variant
            FROM (
                SELECT english_term as term_variant
                FROM korean_english_mapping 
                WHERE LOWER(korean_term) = LOWER(TRIM(single_pattern))
                
                UNION
                
                SELECT korean_term as term_variant
                FROM korean_english_mapping 
                WHERE LOWER(english_term) = LOWER(TRIM(single_pattern))
                
                UNION
                
                SELECT TRIM(single_pattern) as term_variant
            ) t
            WHERE term_variant IS NOT NULL AND length(term_variant) > 0
        ) expanded;
        
        -- 확장된 패턴으로 정규식 매치 수행
        IF expanded_pattern IS NOT NULL AND input_text ~* expanded_pattern THEN
            RETURN TRUE;
        END IF;
    END LOOP;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 매핑 데이터 관리 함수들
CREATE OR REPLACE FUNCTION add_korean_english_mapping(
    korean_term TEXT,
    english_term TEXT,
    category TEXT DEFAULT 'general'
) RETURNS VOID AS $$
BEGIN
    INSERT INTO korean_english_mapping (korean_term, english_term, category)
    VALUES (korean_term, english_term, category)
    ON CONFLICT (korean_term, english_term) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- 매핑 데이터 조회 함수
CREATE OR REPLACE FUNCTION get_mapping_terms(search_term TEXT)
RETURNS TABLE(korean_term TEXT, english_term TEXT, category TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT m.korean_term, m.english_term, m.category
    FROM korean_english_mapping m
    WHERE LOWER(m.korean_term) LIKE '%' || LOWER(search_term) || '%'
       OR LOWER(m.english_term) LIKE '%' || LOWER(search_term) || '%';
END;
$$ LANGUAGE plpgsql;

-- 함수 사용 권한 부여 (필요 시)
-- GRANT EXECUTE ON FUNCTION rds_kor_search_like(TEXT, TEXT) TO PUBLIC;
-- GRANT EXECUTE ON FUNCTION rds_kor_search_tsvector(TEXT, TEXT) TO PUBLIC;
-- GRANT EXECUTE ON FUNCTION rds_kor_search_similar(TEXT, TEXT, FLOAT) TO PUBLIC;
-- GRANT EXECUTE ON FUNCTION rds_kor_search_regex(TEXT, TEXT) TO PUBLIC;

-- 테스트 쿼리 예시
/*
-- 테스트 실행
SELECT 'LG Test:', rds_kor_search_like('엘지 제품입니다', 'lg');
SELECT 'AI Test:', rds_kor_search_like('인공지능 기술', 'ai');
SELECT 'Samsung Test:', rds_kor_search_like('Samsung Galaxy', '삼성');
SELECT 'Data Science Test:', rds_kor_search_tsvector('데이터 과학은 미래 기술', 'data science');
SELECT 'Python Test:', rds_kor_search_similar('파이썬 프로그래밍 언어', 'python');
SELECT 'Multi Test:', rds_kor_search_regex('자바와 파이썬 개발', '자바|파이썬');
*/