-- =====================================================================
-- 채팅 히스토리 완전 초기화 스크립트
-- =====================================================================
-- 실행 날짜: 2025-11-17
-- 목적: Azure OpenAI 모델로 생성된 기존 채팅 데이터 삭제
-- 대상 테이블: tb_chat_sessions, tb_chat_history, tb_chat_feedback
-- =====================================================================

BEGIN;

-- 1. 백업 테이블 생성
CREATE TABLE IF NOT EXISTS tb_chat_sessions_backup AS 
SELECT * FROM tb_chat_sessions;

CREATE TABLE IF NOT EXISTS tb_chat_history_backup AS 
SELECT * FROM tb_chat_history;

CREATE TABLE IF NOT EXISTS tb_chat_feedback_backup AS 
SELECT * FROM tb_chat_feedback;

-- 2. 채팅 관련 테이블 초기화
TRUNCATE TABLE tb_chat_feedback CASCADE;
TRUNCATE TABLE tb_chat_history CASCADE;
TRUNCATE TABLE tb_chat_sessions CASCADE;

-- 3. 시퀀스 초기화 (있는 경우)
DO $$
BEGIN
    -- tb_chat_history의 chat_id 시퀀스 초기화
    IF EXISTS (SELECT 1 FROM pg_sequences WHERE schemaname = 'public' AND sequencename = 'tb_chat_history_chat_id_seq') THEN
        ALTER SEQUENCE tb_chat_history_chat_id_seq RESTART WITH 1;
    END IF;
END $$;

COMMIT;

-- 4. 결과 확인
SELECT '🎉 채팅 데이터 초기화 완료!' as message;
SELECT 
    '📦 백업' as category,
    'tb_chat_sessions_backup' as table_name,
    COUNT(*) as count
FROM tb_chat_sessions_backup
UNION ALL
SELECT '📦 백업', 'tb_chat_history_backup', COUNT(*) FROM tb_chat_history_backup
UNION ALL
SELECT '📦 백업', 'tb_chat_feedback_backup', COUNT(*) FROM tb_chat_feedback_backup
UNION ALL
SELECT '📊 최종 상태', 'tb_chat_sessions', COUNT(*) FROM tb_chat_sessions
UNION ALL
SELECT '📊 최종 상태', 'tb_chat_history', COUNT(*) FROM tb_chat_history
UNION ALL
SELECT '📊 최종 상태', 'tb_chat_feedback', COUNT(*) FROM tb_chat_feedback
ORDER BY category DESC, table_name;
