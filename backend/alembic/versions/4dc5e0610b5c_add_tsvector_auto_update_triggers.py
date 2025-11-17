"""add_tsvector_auto_update_triggers

Revision ID: 4dc5e0610b5c
Revises: 230f87313231
Create Date: 2025-10-16 04:45:36.301730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dc5e0610b5c'
down_revision: Union[str, Sequence[str], None] = '230f87313231'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add tsvector auto-update triggers for tb_document_search_index.
    
    This migration:
    1. Creates trigger functions to automatically update tsvector columns
    2. Creates triggers on INSERT/UPDATE
    3. Updates existing data to populate tsvector columns
    """
    
    # 1. Create trigger function for content_tsvector
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- full_content를 simple 구성으로 tsvector 생성
            -- simple 구성: 영어 단어를 소문자로 변환, 불용어 제거 없음
            NEW.content_tsvector := to_tsvector('simple', COALESCE(NEW.full_content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 2. Create trigger function for keyword_tsvector
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_keyword_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- document_title과 content_summary를 결합하여 tsvector 생성
            NEW.keyword_tsvector := to_tsvector('simple', 
                COALESCE(NEW.document_title, '') || ' ' || 
                COALESCE(NEW.content_summary, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 3. Create trigger for content_tsvector (fires on INSERT or UPDATE of full_content)
    op.execute("""
        CREATE TRIGGER tsvector_update_content
            BEFORE INSERT OR UPDATE OF full_content
            ON tb_document_search_index
            FOR EACH ROW
            EXECUTE FUNCTION update_search_index_content_tsvector();
    """)
    
    # 4. Create trigger for keyword_tsvector (fires on INSERT or UPDATE of title/summary)
    op.execute("""
        CREATE TRIGGER tsvector_update_keyword
            BEFORE INSERT OR UPDATE OF document_title, content_summary
            ON tb_document_search_index
            FOR EACH ROW
            EXECUTE FUNCTION update_search_index_keyword_tsvector();
    """)
    
    # 5. Update existing data - Batch update to avoid long-running transaction
    # Note: This may take a while depending on the number of records
    op.execute("""
        UPDATE tb_document_search_index
        SET 
            content_tsvector = to_tsvector('simple', COALESCE(full_content, '')),
            keyword_tsvector = to_tsvector('simple', 
                COALESCE(document_title, '') || ' ' || 
                COALESCE(content_summary, '')
            )
        WHERE indexing_status = 'indexed'
          AND (content_tsvector IS NULL OR keyword_tsvector IS NULL);
    """)


def downgrade() -> None:
    """
    Remove tsvector auto-update triggers.
    
    This will:
    1. Drop triggers
    2. Drop trigger functions
    Note: Does not clear existing tsvector data
    """
    
    # 1. Drop triggers
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_content ON tb_document_search_index;")
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_keyword ON tb_document_search_index;")
    
    # 2. Drop trigger functions
    op.execute("DROP FUNCTION IF EXISTS update_search_index_content_tsvector();")
    op.execute("DROP FUNCTION IF EXISTS update_search_index_keyword_tsvector();")
