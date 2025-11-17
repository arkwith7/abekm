"""add_multimodal_schema_v2

Revision ID: b38f1337b6ae
Revises: 9c2a4d9c1b2e
Create Date: 2025-09-30 07:51:38.567890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'b38f1337b6ae'
down_revision: Union[str, Sequence[str], None] = '9c2a4d9c1b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """멀티모달 RAG 확장을 위한 스키마 추가"""
    
    # 1. 추출 세션 테이블
    op.create_table('doc_extraction_session',
        sa.Column('extraction_session_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('file_bss_info_sno', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_profile', sa.String(length=50), nullable=True),
        sa.Column('pipeline_type', sa.String(length=20), nullable=True, server_default='azure'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='running'),
        sa.Column('page_count_detected', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['file_bss_info_sno'], ['tb_file_bss_info.file_bss_info_sno'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('extraction_session_id')
    )
    op.create_index('idx_extraction_session_file', 'doc_extraction_session', ['file_bss_info_sno'])
    op.create_index('idx_extraction_session_status', 'doc_extraction_session', ['status'])

    # 2. 추출 객체 테이블
    op.create_table('doc_extracted_object',
        sa.Column('object_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('extraction_session_id', sa.BigInteger(), nullable=False),
        sa.Column('file_bss_info_sno', sa.BigInteger(), nullable=False),
        sa.Column('page_no', sa.Integer(), nullable=True),
        sa.Column('object_type', sa.String(length=20), nullable=False),
        sa.Column('sequence_in_page', sa.Integer(), nullable=True),
        sa.Column('bbox', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('structure_json', postgresql.JSONB(), nullable=True),
        sa.Column('lang_code', sa.String(length=10), nullable=True, server_default='ko'),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('token_estimate', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['extraction_session_id'], ['doc_extraction_session.extraction_session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('object_id')
    )
    op.create_index('idx_extracted_object_file_page', 'doc_extracted_object', ['file_bss_info_sno', 'page_no'])
    op.create_index('idx_extracted_object_type', 'doc_extracted_object', ['object_type'])
    op.create_index('idx_extracted_object_hash', 'doc_extracted_object', ['hash_sha256'])

    # 3. 청킹 세션 테이블
    op.create_table('doc_chunk_session',
        sa.Column('chunk_session_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('file_bss_info_sno', sa.BigInteger(), nullable=False),
        sa.Column('extraction_session_id', sa.BigInteger(), nullable=False),
        sa.Column('strategy_name', sa.String(length=50), nullable=False),
        sa.Column('params_json', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='running'),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['extraction_session_id'], ['doc_extraction_session.extraction_session_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_bss_info_sno'], ['tb_file_bss_info.file_bss_info_sno'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chunk_session_id')
    )
    op.create_index('idx_chunk_session_file', 'doc_chunk_session', ['file_bss_info_sno', 'strategy_name'])
    op.create_index('idx_chunk_session_status', 'doc_chunk_session', ['status'])

    # 4. 청크 테이블
    op.create_table('doc_chunk',
        sa.Column('chunk_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chunk_session_id', sa.BigInteger(), nullable=False),
        sa.Column('file_bss_info_sno', sa.BigInteger(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('source_object_ids', postgresql.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('modality', sa.String(length=20), nullable=True, server_default='text'),
        sa.Column('section_heading', sa.Text(), nullable=True),
        sa.Column('page_range', postgresql.INT4RANGE(), nullable=True),
        sa.Column('quality_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['chunk_session_id'], ['doc_chunk_session.chunk_session_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chunk_id')
    )
    op.create_index('idx_doc_chunk_file', 'doc_chunk', ['file_bss_info_sno'])
    op.create_index('idx_doc_chunk_session', 'doc_chunk', ['chunk_session_id'])
    op.create_index('idx_doc_chunk_modality', 'doc_chunk', ['modality'])

    # 5. 임베딩 테이블
    op.create_table('doc_embedding',
        sa.Column('embedding_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chunk_id', sa.BigInteger(), nullable=False),
        sa.Column('file_bss_info_sno', sa.BigInteger(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('modality', sa.String(length=20), nullable=True, server_default='text'),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('vector', Vector(), nullable=True),
        sa.Column('norm_l2', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['chunk_id'], ['doc_chunk.chunk_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('embedding_id'),
        sa.UniqueConstraint('chunk_id', 'model_name')
    )
    op.create_index('idx_doc_embedding_model', 'doc_embedding', ['model_name'])
    op.create_index('idx_doc_embedding_file', 'doc_embedding', ['file_bss_info_sno'])

    # 6. tb_document_search_index 컬럼 확장
    op.add_column('tb_document_search_index', sa.Column('primary_chunk_session_id', sa.BigInteger(), nullable=True))
    op.add_column('tb_document_search_index', sa.Column('last_embedding_model', sa.String(length=100), nullable=True))
    op.add_column('tb_document_search_index', sa.Column('has_table', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('tb_document_search_index', sa.Column('has_image', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('tb_document_search_index', sa.Column('extraction_session_id', sa.BigInteger(), nullable=True))

def downgrade() -> None:
    """멀티모달 스키마 롤백"""
    
    # 컬럼 제거 (역순)
    op.drop_column('tb_document_search_index', 'extraction_session_id')
    op.drop_column('tb_document_search_index', 'has_image')
    op.drop_column('tb_document_search_index', 'has_table')
    op.drop_column('tb_document_search_index', 'last_embedding_model')
    op.drop_column('tb_document_search_index', 'primary_chunk_session_id')
    
    # 테이블 제거 (역순 - 외래키 참조 순서 고려)
    op.drop_table('doc_embedding')
    op.drop_table('doc_chunk')
    op.drop_table('doc_chunk_session') 
    op.drop_table('doc_extracted_object')
    op.drop_table('doc_extraction_session')
