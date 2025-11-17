"""add azure_clip_vector column to doc_embedding

Revision ID: 20251114_002
Revises: 20251114_001
Create Date: 2025-11-14 10:00:00.000000

목적:
- doc_embedding 테이블에 azure_clip_vector 컬럼 추가 (누락된 컬럼)
- 모델 정의와 DB 스키마 일관성 확보

변경 사항:
- azure_clip_vector: Azure CLIP multimodal (512d)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '20251114_002'
down_revision: Union[str, None] = '20251114_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    azure_clip_vector 컬럼 추가
    """
    print("\n" + "="*80)
    print("🚀 [azure_clip_vector 컬럼 추가 마이그레이션]")
    print("="*80 + "\n")
    
    connection = op.get_bind()
    
    # azure_clip_vector 컬럼 추가
    print("1️⃣ doc_embedding 테이블에 azure_clip_vector 컬럼 추가...")
    
    op.add_column('doc_embedding',
        sa.Column('azure_clip_vector', Vector(512), nullable=True,
                  comment='Azure CLIP multimodal (512d)')
    )
    
    print("   ✅ azure_clip_vector 컬럼 추가 완료")
    
    # 기존 clip_vector 데이터를 azure_clip_vector로 복사
    print("\n2️⃣ 기존 clip_vector 데이터를 azure_clip_vector로 복사...")
    
    connection.execute(text("""
        UPDATE doc_embedding
        SET azure_clip_vector = clip_vector
        WHERE clip_vector IS NOT NULL
          AND provider = 'azure'
    """))
    
    print("   ✅ 데이터 복사 완료")
    
    # 인덱스 생성
    print("\n3️⃣ azure_clip_vector 인덱스 생성...")
    
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_azure_clip_ivfflat
        ON doc_embedding 
        USING ivfflat (azure_clip_vector vector_cosine_ops)
        WITH (lists = 100)
        WHERE azure_clip_vector IS NOT NULL
    """))
    
    print("   ✅ 인덱스 생성 완료")
    
    # 통계
    print("\n4️⃣ 마이그레이션 통계...")
    
    result = connection.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE azure_clip_vector IS NOT NULL) as clip_count,
            COUNT(*) as total_count
        FROM doc_embedding
        WHERE provider = 'azure'
    """))
    
    row = result.fetchone()
    if row:
        print(f"   📊 Azure CLIP 벡터: {row[0]}개 / 전체: {row[1]}개")
    
    print("\n" + "="*80)
    print("✅ [azure_clip_vector 컬럼 추가 완료]")
    print("="*80)


def downgrade() -> None:
    """
    롤백: azure_clip_vector 컬럼 제거
    """
    print("\n🔄 azure_clip_vector 컬럼 제거 중...")
    
    connection = op.get_bind()
    
    # 인덱스 삭제
    connection.execute(text("""
        DROP INDEX IF EXISTS idx_doc_embedding_azure_clip_ivfflat
    """))
    
    # 컬럼 삭제
    op.drop_column('doc_embedding', 'azure_clip_vector')
    
    print("✅ 롤백 완료")
