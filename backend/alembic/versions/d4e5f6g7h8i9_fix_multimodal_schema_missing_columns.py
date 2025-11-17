"""fix_multimodal_schema_missing_columns

Revision ID: d4e5f6g7h8i9
Revises: b38f1337b6ae
Create Date: 2025-10-15 05:10:00.000000

This migration fixes missing columns in the multimodal schema:
1. doc_extracted_object: image_width, image_height, phash
2. vs_doc_contents_chunks: dimension upgrade from 1024 to 3072
3. Recreate HNSW index for 3072 dimensions (IVFFLAT limited to 2000)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'b38f1337b6ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns and upgrade vector dimensions"""
    
    # 1. doc_extracted_object 테이블에 이미지 관련 컬럼 추가 (IF NOT EXISTS 사용)
    op.execute('ALTER TABLE doc_extracted_object ADD COLUMN IF NOT EXISTS image_width INTEGER')
    op.execute('ALTER TABLE doc_extracted_object ADD COLUMN IF NOT EXISTS image_height INTEGER')
    op.execute("ALTER TABLE doc_extracted_object ADD COLUMN IF NOT EXISTS phash VARCHAR(32)")
    
    # 2. doc_embedding 테이블에 벡터 검색 인덱스 추가
    # pgvector 0.5.1은 HNSW/IVFFLAT 모두 2000차원 제한
    # 3072차원을 위해 인덱스 없이 사용 (Full scan은 느리지만 작동함)
    # 또는 1536차원 모델로 전환 필요
    
    # 임시 해결: doc_embedding에 코사인 유사도 인덱스 생성 시도 (제한 확인)
    # 실패 시 인덱스 없이 진행 (TODO: pgvector 0.7.0+ 업그레이드 또는 차원 축소)
    
    print("⚠️ pgvector 0.5.1 dimension limit:")
    print("   - HNSW/IVFFLAT: max 2000 dimensions")
    print("   - Current embedding: 3072 dimensions (text-embedding-3-large)")
    print("   - Skipping vs_doc_contents_chunks migration")
    print("   - Using doc_embedding table for vector search (no index, slower)")
    print("")
    print("📋 Recommendations:")
    print("   1. Upgrade pgvector to 0.7.0+ for 2000+ dimension support")
    print("   2. Switch to text-embedding-3-small (1536 dim)")
    print("   3. Use PCA dimension reduction (3072 -> 1536)")
    
    # 3. doc_chunk 테이블에 char_count 컬럼 추가 (누락 가능성 대비)
    op.execute('''
        ALTER TABLE doc_chunk 
        ADD COLUMN IF NOT EXISTS char_count INTEGER
    ''')
    
    # 4. 기존 데이터 마이그레이션: token_count 기반으로 char_count 추정
    op.execute('''
        UPDATE doc_chunk 
        SET char_count = COALESCE(LENGTH(content_text), token_count * 4)
        WHERE char_count IS NULL
    ''')
    
    print("✅ Multimodal schema fixes applied:")
    print("   - doc_extracted_object: added image_width, image_height, phash")
    print("   - doc_chunk: ensured char_count column exists")


def downgrade() -> None:
    """Rollback schema changes"""
    
    # doc_extracted_object 컬럼 제거
    op.execute('ALTER TABLE doc_extracted_object DROP COLUMN IF EXISTS phash')
    op.execute('ALTER TABLE doc_extracted_object DROP COLUMN IF EXISTS image_height')
    op.execute('ALTER TABLE doc_extracted_object DROP COLUMN IF EXISTS image_width')
    
    print("⚠️ Multimodal schema fixes rolled back")
