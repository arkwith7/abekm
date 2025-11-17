-- ===============================================
-- 통합검색 메인 테이블 스키마 제안
-- 기존: vs_doc_contents_index → 새로운: tb_document_search_index
-- ===============================================

CREATE TABLE tb_document_search_index (
    -- 기본 식별자
    search_doc_id SERIAL PRIMARY KEY COMMENT '검색 문서 ID',
    file_bss_info_sno INTEGER NOT NULL COMMENT '파일 기본 정보 일련번호',
    knowledge_container_id VARCHAR(50) NOT NULL COMMENT '지식 컨테이너 ID',
    
    -- 문서 전문 내용 (기존 chunk_text 대체)
    document_title VARCHAR(500) COMMENT '문서 제목',
    full_content TEXT NOT NULL COMMENT '문서 전체 내용 또는 주요 섹션',
    content_summary TEXT COMMENT '내용 요약 (최대 1000자)',
    
    -- 검색 최적화 필드
    keywords TEXT[] COMMENT '추출된 키워드 배열',
    proper_nouns TEXT[] COMMENT '고유명사 배열', 
    corp_names TEXT[] COMMENT '회사명/기관명 배열',
    main_topics TEXT[] COMMENT '주요 주제/카테고리 배열',
    
    -- 문서 메타데이터 (기존 chunk_index, chunk_size 대체)
    document_type VARCHAR(50) COMMENT '문서 유형 (PDF, DOCX, etc)',
    page_count INTEGER COMMENT '페이지 수',
    content_length INTEGER COMMENT '전체 내용 길이',
    language_code VARCHAR(10) DEFAULT 'ko' COMMENT '언어 코드',
    
    -- 검색 성능 최적화 필드 (embedding 제거)
    keyword_tsvector TSVECTOR COMMENT '키워드 전문검색 벡터',
    content_tsvector TSVECTOR COMMENT '내용 전문검색 벡터',
    search_weight INTEGER DEFAULT 1 COMMENT '검색 가중치',
    
    -- 권한 및 접근성
    access_level VARCHAR(20) DEFAULT 'normal' COMMENT '접근 권한 레벨',
    is_public BOOLEAN DEFAULT false COMMENT '공개 문서 여부',
    
    -- 시스템 관리
    indexing_status VARCHAR(20) DEFAULT 'indexed' COMMENT '색인 상태',
    last_searched_at TIMESTAMP COMMENT '마지막 검색 일시',
    search_count INTEGER DEFAULT 0 COMMENT '검색 횟수',
    
    -- 공통 필드
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 외래키 제약조건
    FOREIGN KEY (file_bss_info_sno) REFERENCES tb_file_bss_info(file_bss_info_sno),
    FOREIGN KEY (knowledge_container_id) REFERENCES tb_knowledge_containers(container_id)
);

-- ===============================================
-- 검색 최적화 인덱스
-- ===============================================

-- 1. 전문검색 인덱스 (GIN)
CREATE INDEX idx_search_content_tsvector ON tb_document_search_index USING GIN(content_tsvector);
CREATE INDEX idx_search_keyword_tsvector ON tb_document_search_index USING GIN(keyword_tsvector);

-- 2. 키워드 배열 검색 인덱스 (GIN)
CREATE INDEX idx_search_keywords ON tb_document_search_index USING GIN(keywords);
CREATE INDEX idx_search_proper_nouns ON tb_document_search_index USING GIN(proper_nouns);
CREATE INDEX idx_search_topics ON tb_document_search_index USING GIN(main_topics);

-- 3. 복합 인덱스 (검색 성능)
CREATE INDEX idx_search_container_type ON tb_document_search_index(knowledge_container_id, document_type);
CREATE INDEX idx_search_file_access ON tb_document_search_index(file_bss_info_sno, access_level);

-- 4. 일반 인덱스
CREATE INDEX idx_search_updated ON tb_document_search_index(last_updated);
CREATE INDEX idx_search_status ON tb_document_search_index(indexing_status);

-- ===============================================
-- 자동 tsvector 업데이트 트리거
-- ===============================================

CREATE OR REPLACE FUNCTION update_search_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    -- 내용 기반 tsvector 업데이트
    NEW.content_tsvector := to_tsvector('korean', 
        COALESCE(NEW.document_title, '') || ' ' || 
        COALESCE(NEW.full_content, '') || ' ' ||
        COALESCE(NEW.content_summary, '')
    );
    
    -- 키워드 기반 tsvector 업데이트  
    NEW.keyword_tsvector := to_tsvector('korean',
        array_to_string(COALESCE(NEW.keywords, ARRAY[]::text[]), ' ') || ' ' ||
        array_to_string(COALESCE(NEW.proper_nouns, ARRAY[]::text[]), ' ') || ' ' ||
        array_to_string(COALESCE(NEW.main_topics, ARRAY[]::text[]), ' ')
    );
    
    -- 마지막 업데이트 시간 갱신
    NEW.last_updated := NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거 생성
CREATE TRIGGER trigger_update_search_tsvector
    BEFORE INSERT OR UPDATE ON tb_document_search_index
    FOR EACH ROW EXECUTE FUNCTION update_search_tsvector();

-- ===============================================
-- 샘플 데이터 및 검색 쿼리 예시
-- ===============================================

-- 1. 키워드 검색 쿼리 예시
/*
SELECT 
    search_doc_id,
    document_title,
    content_summary,
    keywords,
    ts_rank(content_tsvector, plainto_tsquery('korean', '검색어')) as relevance_score
FROM tb_document_search_index 
WHERE content_tsvector @@ plainto_tsquery('korean', '검색어')
  AND knowledge_container_id = ANY(ARRAY['container1', 'container2'])
ORDER BY relevance_score DESC
LIMIT 20;
*/

-- 2. 하이브리드 검색 쿼리 예시  
/*
SELECT 
    search_doc_id,
    document_title,
    full_content,
    keywords,
    -- 키워드 점수 (40%)
    ts_rank(keyword_tsvector, plainto_tsquery('korean', '검색어')) * 0.4 +
    -- 내용 점수 (60%)  
    ts_rank(content_tsvector, plainto_tsquery('korean', '검색어')) * 0.6 
    as hybrid_score
FROM tb_document_search_index
WHERE (keyword_tsvector @@ plainto_tsquery('korean', '검색어') 
       OR content_tsvector @@ plainto_tsquery('korean', '검색어'))
  AND access_level IN ('public', 'normal')
ORDER BY hybrid_score DESC
LIMIT 20;
*/
