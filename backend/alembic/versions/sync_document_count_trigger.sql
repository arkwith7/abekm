-- ================================================================
-- 컨테이너 문서 개수 자동 동기화 트리거
-- ================================================================
-- 목적: tb_file_bss_info의 변경 시 tb_knowledge_containers.document_count 자동 업데이트
-- 사용: 필요시 수동 실행 (Alembic 마이그레이션 대신 직접 실행 가능)
-- ================================================================

-- 1. 트리거 함수 생성
CREATE OR REPLACE FUNCTION sync_container_document_count()
RETURNS TRIGGER AS $$
BEGIN
    -- INSERT 또는 UPDATE로 del_yn이 'N'이 된 경우
    IF (TG_OP = 'INSERT' AND NEW.del_yn != 'Y') OR 
       (TG_OP = 'UPDATE' AND OLD.del_yn = 'Y' AND NEW.del_yn != 'Y') THEN
        
        UPDATE tb_knowledge_containers
        SET document_count = (
            SELECT COUNT(*)
            FROM tb_file_bss_info
            WHERE knowledge_container_id = NEW.knowledge_container_id
              AND del_yn != 'Y'
        ),
        last_modified_date = CURRENT_TIMESTAMP
        WHERE container_id = NEW.knowledge_container_id;
        
    -- DELETE 또는 UPDATE로 del_yn이 'Y'가 된 경우
    ELSIF (TG_OP = 'DELETE') OR 
          (TG_OP = 'UPDATE' AND OLD.del_yn != 'Y' AND NEW.del_yn = 'Y') THEN
        
        UPDATE tb_knowledge_containers
        SET document_count = (
            SELECT COUNT(*)
            FROM tb_file_bss_info
            WHERE knowledge_container_id = COALESCE(NEW.knowledge_container_id, OLD.knowledge_container_id)
              AND del_yn != 'Y'
        ),
        last_modified_date = CURRENT_TIMESTAMP
        WHERE container_id = COALESCE(NEW.knowledge_container_id, OLD.knowledge_container_id);
        
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 2. 트리거 생성 (기존 트리거가 있으면 삭제 후 재생성)
DROP TRIGGER IF EXISTS trigger_sync_document_count ON tb_file_bss_info;

CREATE TRIGGER trigger_sync_document_count
AFTER INSERT OR UPDATE OR DELETE ON tb_file_bss_info
FOR EACH ROW
EXECUTE FUNCTION sync_container_document_count();

-- 3. 초기 동기화 (현재 데이터 일괄 업데이트)
UPDATE tb_knowledge_containers kc
SET document_count = (
    SELECT COUNT(*)
    FROM tb_file_bss_info f
    WHERE f.knowledge_container_id = kc.container_id
      AND f.del_yn != 'Y'
),
last_modified_date = CURRENT_TIMESTAMP;

-- 4. 결과 확인
SELECT 
    container_id,
    container_name,
    document_count,
    last_modified_date
FROM tb_knowledge_containers
WHERE document_count > 0
ORDER BY container_id;

-- ================================================================
-- 트리거 제거 (필요시 사용)
-- ================================================================
-- DROP TRIGGER IF EXISTS trigger_sync_document_count ON tb_file_bss_info;
-- DROP FUNCTION IF EXISTS sync_container_document_count();
