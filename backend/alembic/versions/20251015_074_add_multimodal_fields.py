"""멀티모달 검색 지원 - 이미지 메타데이터 필드 추가

Revision ID: 20251015_074
Revises: 72342a21e7bc
Create Date: 2025-10-15 07:43:26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251015_074'
down_revision: Union[str, None] = '72342a21e7bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tb_document_search_index에 멀티모달 필드 추가
    op.add_column('tb_document_search_index', 
                  sa.Column('has_images', sa.Boolean(), nullable=False, server_default='false', 
                           comment='이미지 포함 여부 (멀티모달)'))
    op.add_column('tb_document_search_index', 
                  sa.Column('has_tables', sa.Boolean(), nullable=False, server_default='false', 
                           comment='테이블 포함 여부'))
    op.add_column('tb_document_search_index', 
                  sa.Column('image_count', sa.Integer(), nullable=False, server_default='0', 
                           comment='이미지 개수 (멀티모달)'))
    op.add_column('tb_document_search_index', 
                  sa.Column('table_count', sa.Integer(), nullable=False, server_default='0', 
                           comment='테이블 개수'))
    op.add_column('tb_document_search_index', 
                  sa.Column('images_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, 
                           comment='이미지 메타데이터 (JSON, 멀티모달 검색용)'))
    
    # 멀티모달 검색을 위한 인덱스 추가
    op.create_index('idx_search_has_images', 'tb_document_search_index', ['has_images'], unique=False)
    op.create_index('idx_search_multimodal', 'tb_document_search_index', ['has_images', 'image_count'], unique=False)
    op.create_index('idx_search_images_metadata', 'tb_document_search_index', ['images_metadata'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    # 인덱스 삭제
    op.drop_index('idx_search_images_metadata', table_name='tb_document_search_index')
    op.drop_index('idx_search_multimodal', table_name='tb_document_search_index')
    op.drop_index('idx_search_has_images', table_name='tb_document_search_index')
    
    # 컬럼 삭제
    op.drop_column('tb_document_search_index', 'images_metadata')
    op.drop_column('tb_document_search_index', 'table_count')
    op.drop_column('tb_document_search_index', 'image_count')
    op.drop_column('tb_document_search_index', 'has_tables')
    op.drop_column('tb_document_search_index', 'has_images')
