"""remove_kiwipiepy_fields_from_search_index

Revision ID: 230f87313231
Revises: ecce18675a2b
Create Date: 2025-10-16 04:26:15.801648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '230f87313231'
down_revision: Union[str, Sequence[str], None] = 'ecce18675a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove kiwipiepy-related fields from tb_document_search_index."""
    # 0. Drop triggers that depend on these columns
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_trigger ON tb_document_search_index CASCADE")
    
    # 1. Drop GIN indexes on kiwipiepy fields
    op.drop_index('idx_search_keywords', table_name='tb_document_search_index', postgresql_using='gin', if_exists=True)
    op.drop_index('idx_search_proper_nouns', table_name='tb_document_search_index', postgresql_using='gin', if_exists=True)
    
    # 2. Drop columns
    op.drop_column('tb_document_search_index', 'keywords', if_exists=True)
    op.drop_column('tb_document_search_index', 'proper_nouns', if_exists=True)
    op.drop_column('tb_document_search_index', 'corp_names', if_exists=True)


def downgrade() -> None:
    """Re-add kiwipiepy-related fields to tb_document_search_index."""
    # Import needed for ARRAY type
    from sqlalchemy.dialects import postgresql
    
    # 1. Re-create columns
    op.add_column('tb_document_search_index', 
                  sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True, comment='추출된 키워드 배열'))
    op.add_column('tb_document_search_index', 
                  sa.Column('proper_nouns', postgresql.ARRAY(sa.Text()), nullable=True, comment='고유명사 배열'))
    op.add_column('tb_document_search_index', 
                  sa.Column('corp_names', postgresql.ARRAY(sa.Text()), nullable=True, comment='회사명/기관명 배열'))
    
    # 2. Re-create GIN indexes
    op.create_index('idx_search_keywords', 'tb_document_search_index', ['keywords'], unique=False, postgresql_using='gin')
    op.create_index('idx_search_proper_nouns', 'tb_document_search_index', ['proper_nouns'], unique=False, postgresql_using='gin')
