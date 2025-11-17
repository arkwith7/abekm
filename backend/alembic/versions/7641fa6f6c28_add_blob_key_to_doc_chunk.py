"""add_blob_key_to_doc_chunk

Revision ID: 7641fa6f6c28
Revises: f7g8h9i0j1k2
Create Date: 2025-10-24 07:55:34.359187

멀티모달 이미지/테이블 청크의 Blob Storage 파일 경로를 저장하기 위한 컬럼 추가
- blob_key: 이미지/테이블의 Azure Blob Storage 경로 (예: multimodal/72/objects/image_1817_5.png)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7641fa6f6c28'
down_revision: Union[str, Sequence[str], None] = 'f7g8h9i0j1k2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # doc_chunk 테이블에 blob_key 컬럼 추가
    op.add_column(
        'doc_chunk',
        sa.Column('blob_key', sa.String(500), nullable=True, comment='Blob Storage 파일 경로 (이미지/테이블 등)')
    )
    
    # 인덱스 추가 (blob_key로 조회 성능 향상)
    op.create_index(
        'ix_doc_chunk_blob_key',
        'doc_chunk',
        ['blob_key'],
        unique=False
    )
    
    print("✅ doc_chunk.blob_key 컬럼 추가 완료")
    print("📝 기존 데이터는 NULL, 신규 문서 업로드 시 자동 입력됩니다")


def downgrade() -> None:
    """Downgrade schema."""
    # 인덱스 삭제
    op.drop_index('ix_doc_chunk_blob_key', table_name='doc_chunk')
    
    # 컬럼 삭제
    op.drop_column('doc_chunk', 'blob_key')
    
    print("✅ doc_chunk.blob_key 컬럼 제거 완료")
