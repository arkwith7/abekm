"""add academic metadata tables

Revision ID: b9e25ab62141
Revises: 47e3c2b8ea1d
Create Date: 2025-10-20 07:27:06.943773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b9e25ab62141'
down_revision: Union[str, Sequence[str], None] = '47e3c2b8ea1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 학술논문 서지 메타데이터 테이블
    op.create_table(
        'tb_academic_document_metadata',
        sa.Column('file_bss_info_sno', sa.Integer(), nullable=False),
        sa.Column('title', sa.VARCHAR(1000), nullable=True),
        sa.Column('abstract', sa.Text(), nullable=True),
        sa.Column('doi', sa.VARCHAR(200), nullable=True),
        sa.Column('journal', sa.VARCHAR(300), nullable=True),
        sa.Column('volume', sa.VARCHAR(50), nullable=True),
        sa.Column('issue', sa.VARCHAR(50), nullable=True),
        sa.Column('year', sa.VARCHAR(4), nullable=True),
        sa.Column('pages', sa.VARCHAR(50), nullable=True),
        sa.Column('publisher', sa.VARCHAR(200), nullable=True),
        sa.Column('issn', sa.VARCHAR(50), nullable=True),
        sa.Column('isbn', sa.VARCHAR(50), nullable=True),
        sa.Column('language_code', sa.VARCHAR(10), nullable=True),
        sa.Column('keywords', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('publication_date', sa.Date(), nullable=True),
        sa.Column('accepted_date', sa.Date(), nullable=True),
        sa.Column('created_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['file_bss_info_sno'], ['tb_file_bss_info.file_bss_info_sno'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('file_bss_info_sno')
    )
    op.create_index('idx_acad_doc_doi', 'tb_academic_document_metadata', ['doi'], unique=True)
    op.create_index('idx_acad_doc_year_journal', 'tb_academic_document_metadata', ['year', 'journal'])
    op.execute("CREATE INDEX idx_acad_doc_keywords ON tb_academic_document_metadata USING GIN (keywords)")

    # 2. 저자 정보 테이블
    op.create_table(
        'tb_academic_authors',
        sa.Column('author_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.VARCHAR(300), nullable=False),
        sa.Column('given_name', sa.VARCHAR(150), nullable=True),
        sa.Column('family_name', sa.VARCHAR(150), nullable=True),
        sa.Column('orcid', sa.VARCHAR(50), nullable=True),
        sa.Column('email', sa.VARCHAR(200), nullable=True),
        sa.Column('created_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('author_id')
    )
    op.create_index('idx_author_full_name', 'tb_academic_authors', ['full_name'])
    op.create_index('idx_author_orcid', 'tb_academic_authors', ['orcid'], unique=True)

    # 3. 소속기관 테이블
    op.create_table(
        'tb_academic_affiliations',
        sa.Column('affiliation_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('institution', sa.VARCHAR(300), nullable=True),
        sa.Column('department', sa.VARCHAR(300), nullable=True),
        sa.Column('country', sa.VARCHAR(100), nullable=True),
        sa.Column('created_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('affiliation_id')
    )
    op.create_index('idx_affiliation_institution', 'tb_academic_affiliations', ['institution'])

    # 4. 문서-저자 매핑 테이블
    op.create_table(
        'tb_academic_document_authors',
        sa.Column('file_bss_info_sno', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.BigInteger(), nullable=False),
        sa.Column('author_order', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.BigInteger(), nullable=True),
        sa.Column('corresponding_author', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['file_bss_info_sno'], ['tb_file_bss_info.file_bss_info_sno'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['tb_academic_authors.author_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['affiliation_id'], ['tb_academic_affiliations.affiliation_id']),
        sa.PrimaryKeyConstraint('file_bss_info_sno', 'author_id')
    )
    op.create_index('idx_doc_authors_order', 'tb_academic_document_authors', ['file_bss_info_sno', 'author_order'])

    # 5. 참고문헌 테이블
    op.create_table(
        'tb_academic_references',
        sa.Column('reference_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('file_bss_info_sno', sa.Integer(), nullable=False),
        sa.Column('ref_index', sa.Integer(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('parsed', postgresql.JSONB(), nullable=True),
        sa.Column('created_date', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['file_bss_info_sno'], ['tb_file_bss_info.file_bss_info_sno'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('reference_id')
    )
    op.create_index('idx_doc_ref_index', 'tb_academic_references', ['file_bss_info_sno', 'ref_index'])
    op.execute("CREATE INDEX idx_acad_refs_parsed ON tb_academic_references USING GIN (parsed)")


def downgrade() -> None:
    """Downgrade schema."""
    # 역순으로 테이블 삭제
    op.drop_table('tb_academic_references')
    op.drop_table('tb_academic_document_authors')
    op.drop_table('tb_academic_affiliations')
    op.drop_table('tb_academic_authors')
    op.drop_table('tb_academic_document_metadata')
