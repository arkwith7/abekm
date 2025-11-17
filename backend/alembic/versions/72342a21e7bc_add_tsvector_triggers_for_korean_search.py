"""add_tsvector_triggers_for_korean_search

Revision ID: 72342a21e7bc
Revises: k3l4m5n6o7p8
Create Date: 2025-10-15 05:49:45.289662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72342a21e7bc'
down_revision: Union[str, Sequence[str], None] = 'k3l4m5n6o7p8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    tb_document_search_index 테이블에 
    'korean' configuration을 사용한 tsvector 자동 생성 트리거 추가
    
    주의: vs_doc_contents_chunks는 벡터 검색 전용이므로 tsvector 미사용
    """
    
    # 1. tb_document_search_index tsvector 업데이트 함수 생성
    op.execute("""
    CREATE OR REPLACE FUNCTION update_search_index_tsvector() 
    RETURNS trigger AS $$
    BEGIN
        -- keyword_tsvector: 키워드 배열을 공백으로 합쳐서 korean 파서로 처리
        NEW.keyword_tsvector := to_tsvector('korean', 
            COALESCE(array_to_string(NEW.keywords, ' '), '') || ' ' ||
            COALESCE(array_to_string(NEW.proper_nouns, ' '), '') || ' ' ||
            COALESCE(array_to_string(NEW.corp_names, ' '), '') || ' ' ||
            COALESCE(array_to_string(NEW.main_topics, ' '), '')
        );
        
        -- content_tsvector: 제목 + 요약 + 전체 내용을 korean 파서로 처리
        NEW.content_tsvector := to_tsvector('korean',
            COALESCE(NEW.document_title, '') || ' ' ||
            COALESCE(NEW.content_summary, '') || ' ' ||
            COALESCE(substring(NEW.full_content, 1, 50000), '')  -- 최대 50,000자만 색인
        );
        
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    # 2. tb_document_search_index INSERT/UPDATE 트리거 생성
    op.execute("""
    CREATE TRIGGER tsvector_update_trigger 
    BEFORE INSERT OR UPDATE OF document_title, content_summary, full_content, keywords, proper_nouns, corp_names, main_topics
    ON tb_document_search_index
    FOR EACH ROW 
    EXECUTE FUNCTION update_search_index_tsvector();
    """)
    
    # 3. 기존 데이터의 tsvector 업데이트 (tb_document_search_index)
    # 주의: 현재 데이터가 없어도 안전하게 실행됨
    op.execute("""
    UPDATE tb_document_search_index
    SET keyword_tsvector = to_tsvector('korean', 
            COALESCE(array_to_string(keywords, ' '), '') || ' ' ||
            COALESCE(array_to_string(proper_nouns, ' '), '') || ' ' ||
            COALESCE(array_to_string(corp_names, ' '), '') || ' ' ||
            COALESCE(array_to_string(main_topics, ' '), '')
        ),
        content_tsvector = to_tsvector('korean',
            COALESCE(document_title, '') || ' ' ||
            COALESCE(content_summary, '') || ' ' ||
            COALESCE(substring(full_content, 1, 50000), '')
        )
    WHERE keyword_tsvector IS NULL OR content_tsvector IS NULL;
    """)


def downgrade() -> None:
    """트리거 및 함수 제거"""
    
    # 1. 트리거 삭제
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_trigger ON tb_document_search_index;")
    
    # 2. 함수 삭제
    op.execute("DROP FUNCTION IF EXISTS update_search_index_tsvector();")
    
    # 3. tsvector 컬럼 NULL로 초기화
    op.execute("UPDATE tb_document_search_index SET keyword_tsvector = NULL, content_tsvector = NULL;")
