"""update_tsvector_for_korean_english_mixed_search

Revision ID: c5aebed798ed
Revises: 4dc5e0610b5c
Create Date: 2025-10-16 04:54:07.510094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5aebed798ed'
down_revision: Union[str, Sequence[str], None] = '4dc5e0610b5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Update tsvector trigger functions for Korean/English mixed search.
    
    Changes:
    1. Combine 'simple' (for English) and 'korean' (for Korean morpheme analysis) configs
    2. Use setweight to prioritize Korean content (A) over English (B)
    3. Update existing data with new tsvector generation
    
    Benefits:
    - English: "leadership" → 'leadership'
    - Korean: "리더십과" → '리더십' (removes particles)
    - Mixed: "Ambidextrous 리더십" → both indexed correctly
    """
    
    # 1. Update trigger function for content_tsvector - HYBRID (simple + korean)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Combine simple (English) and korean (Korean) configurations
            -- Korean gets higher weight (A) for better Korean search results
            NEW.content_tsvector := 
                setweight(to_tsvector('simple', COALESCE(NEW.full_content, '')), 'B') ||
                setweight(to_tsvector('korean', COALESCE(NEW.full_content, '')), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 2. Update trigger function for keyword_tsvector - HYBRID
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_keyword_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Combine title and summary with hybrid configuration
            NEW.keyword_tsvector := 
                setweight(to_tsvector('simple', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'B') ||
                setweight(to_tsvector('korean', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 3. Update existing data with new hybrid tsvector
    # This will trigger the new functions automatically
    op.execute("""
        UPDATE tb_document_search_index
        SET full_content = full_content
        WHERE indexing_status = 'indexed';
    """)


def downgrade() -> None:
    """
    Revert to simple-only configuration.
    """
    
    # 1. Revert content_tsvector function to simple-only
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.content_tsvector := to_tsvector('simple', COALESCE(NEW.full_content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 2. Revert keyword_tsvector function to simple-only
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_keyword_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.keyword_tsvector := to_tsvector('simple', 
                COALESCE(NEW.document_title, '') || ' ' || 
                COALESCE(NEW.content_summary, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 3. Update existing data back to simple-only
    op.execute("""
        UPDATE tb_document_search_index
        SET full_content = full_content
        WHERE indexing_status = 'indexed';
    """)
