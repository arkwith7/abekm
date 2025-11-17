-- ============================================
-- 문서 유형별 파이프라인 지원을 위한 스키마 확장
-- ============================================

-- 1. document_type 컬럼 추가
ALTER TABLE tb_file_bss_info 
ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) DEFAULT 'general';

-- 2. processing_options 컬럼 추가 (유형별 처리 옵션 저장)
ALTER TABLE tb_file_bss_info 
ADD COLUMN IF NOT EXISTS processing_options JSONB DEFAULT '{}';

-- 3. 문서 유형에 대한 체크 제약 (유효한 값만 허용)
ALTER TABLE tb_file_bss_info 
ADD CONSTRAINT chk_document_type 
CHECK (document_type IN (
    'general',
    'academic_paper',
    'patent',
    'technical_report',
    'business_document',
    'presentation'
));

-- 4. document_type 인덱스 생성 (유형별 조회 최적화)
CREATE INDEX IF NOT EXISTS idx_file_bss_info_document_type 
ON tb_file_bss_info(document_type);

-- 5. 복합 인덱스 (컨테이너 + 유형별 조회)
CREATE INDEX IF NOT EXISTS idx_file_bss_info_container_type 
ON tb_file_bss_info(cntnr_id, document_type);

-- 6. processing_options JSONB 인덱스 (옵션 기반 조회)
CREATE INDEX IF NOT EXISTS idx_file_bss_info_processing_options 
ON tb_file_bss_info USING GIN (processing_options);

-- ============================================
-- 기존 데이터 마이그레이션
-- ============================================

-- 7. 기존 문서의 document_type을 'general'로 설정 (이미 DEFAULT로 설정되어 있음)
-- 특정 파일명 패턴으로 자동 분류 (선택적)
UPDATE tb_file_bss_info
SET document_type = 'academic_paper'
WHERE document_type = 'general'
  AND (
    file_lgc_nm ILIKE '%journal%' OR
    file_lgc_nm ILIKE '%paper%' OR
    file_lgc_nm ILIKE '%conference%' OR
    file_lgc_nm ILIKE '%thesis%'
  );

UPDATE tb_file_bss_info
SET document_type = 'patent'
WHERE document_type = 'general'
  AND (
    file_lgc_nm ILIKE '%patent%' OR
    file_lgc_nm ILIKE '%특허%'
  );

UPDATE tb_file_bss_info
SET document_type = 'presentation'
WHERE document_type = 'general'
  AND file_extsn IN ('pptx', 'ppt');

-- ============================================
-- 검증 쿼리
-- ============================================

-- 8. 문서 유형별 분포 확인
SELECT 
    document_type,
    COUNT(*) as document_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM tb_file_bss_info
GROUP BY document_type
ORDER BY document_count DESC;

-- 9. processing_options 샘플 확인
SELECT 
    file_bss_info_sno,
    file_lgc_nm,
    document_type,
    processing_options
FROM tb_file_bss_info
WHERE processing_options != '{}'
LIMIT 10;

-- ============================================
-- 문서 유형별 통계 뷰 생성
-- ============================================

CREATE OR REPLACE VIEW vw_document_type_stats AS
SELECT 
    document_type,
    COUNT(*) as total_documents,
    COUNT(CASE WHEN del_yn = 'N' THEN 1 END) as active_documents,
    COUNT(CASE WHEN del_yn = 'Y' THEN 1 END) as deleted_documents,
    AVG(file_sz) as avg_file_size,
    MAX(file_sz) as max_file_size,
    MIN(rgst_dtm) as first_uploaded,
    MAX(rgst_dtm) as last_uploaded
FROM tb_file_bss_info
GROUP BY document_type;

-- ============================================
-- 문서 유형별 처리 옵션 예시
-- ============================================

-- 학술 논문 기본 옵션
COMMENT ON COLUMN tb_file_bss_info.processing_options IS 
'문서 유형별 처리 옵션 (JSONB)
예시:
- academic_paper: {"extract_figures": true, "parse_references": true, "extract_equations": false, "priority_sections": ["abstract", "conclusion"]}
- patent: {"extract_claims": true, "parse_citations": true, "technical_field_extraction": true}
- presentation: {"extract_key_slides": true, "slide_importance_ranking": true}
- general: {}';

-- ============================================
-- 롤백 스크립트 (필요 시)
-- ============================================

/*
-- 인덱스 삭제
DROP INDEX IF EXISTS idx_file_bss_info_document_type;
DROP INDEX IF EXISTS idx_file_bss_info_container_type;
DROP INDEX IF EXISTS idx_file_bss_info_processing_options;

-- 뷰 삭제
DROP VIEW IF EXISTS vw_document_type_stats;

-- 제약 조건 삭제
ALTER TABLE tb_file_bss_info DROP CONSTRAINT IF EXISTS chk_document_type;

-- 컬럼 삭제
ALTER TABLE tb_file_bss_info DROP COLUMN IF EXISTS document_type;
ALTER TABLE tb_file_bss_info DROP COLUMN IF EXISTS processing_options;
*/
