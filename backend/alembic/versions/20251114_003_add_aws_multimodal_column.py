"""add aws multimodal embedding column (Cohere Embed v4)

Revision ID: 20251114_003
Revises: 20251114_002
Create Date: 2025-11-14 16:45:00.000000

목적:
- AWS 멀티모달 임베딩 컬럼 추가 (Cohere Embed v4)
- Azure CLIP 대응 AWS 버전 구현

변경 사항:
1. doc_embedding 테이블:
   - aws_multimodal_vector_1024: Cohere Embed v4 (1024d)
   
2. 인덱스 생성:
   - AWS 멀티모달 벡터 전용 IVFFlat 인덱스
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '20251114_003'
down_revision: Union[str, None] = '20251114_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    AWS 멀티모달 임베딩 컬럼 추가 (Cohere Embed v4)
    """
    print("\n" + "="*80)
    print("🚀 [AWS 멀티모달 임베딩 컬럼 추가 - Cohere Embed v4]")
    print("="*80 + "\n")
    
    connection = op.get_bind()
    
    # =========================================================================
    # 1. doc_embedding 테이블: AWS 멀티모달 컬럼 추가
    # =========================================================================
    print("1️⃣ doc_embedding 테이블에 AWS 멀티모달 컬럼 추가...")
    
    # AWS 멀티모달 임베딩 컬럼 (Cohere Embed v4)
    op.add_column('doc_embedding',
        sa.Column('aws_multimodal_vector_1024', Vector(1024), nullable=True,
                  comment='AWS Cohere Embed v4 multimodal (1024d)')
    )
    
    print("   ✅ AWS 멀티모달 벡터 컬럼 추가 완료")
    
    # =========================================================================
    # 2. 인덱스 생성
    # =========================================================================
    print("\n2️⃣ AWS 멀티모달 전용 인덱스 생성...")
    
    # AWS 멀티모달 1024d 벡터 인덱스
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_aws_multimodal_1024_ivfflat
        ON doc_embedding 
        USING ivfflat (aws_multimodal_vector_1024 vector_cosine_ops)
        WITH (lists = 100)
        WHERE aws_multimodal_vector_1024 IS NOT NULL
    """))
    
    print("   ✅ AWS 멀티모달 인덱스 생성 완료")
    
    # =========================================================================
    # 3. 통계 정보 출력
    # =========================================================================
    print("\n3️⃣ 마이그레이션 완료 통계...")
    
    result = connection.execute(text("""
        SELECT 
            COUNT(*) as total_embeddings,
            COUNT(CASE WHEN azure_clip_vector IS NOT NULL THEN 1 END) as azure_clip_count,
            COUNT(CASE WHEN aws_multimodal_vector_1024 IS NOT NULL THEN 1 END) as aws_multimodal_count
        FROM doc_embedding
    """))
    
    row = result.fetchone()
    print(f"   📊 총 임베딩: {row[0]}개")
    print(f"   📊 Azure CLIP: {row[1]}개")
    print(f"   📊 AWS Cohere v4: {row[2]}개")
    
    print("\n" + "="*80)
    print("✅ [AWS 멀티모달 임베딩 컬럼 추가 완료]")
    print("="*80)


def downgrade() -> None:
    """
    롤백: AWS 멀티모달 컬럼 제거
    """
    print("\n롤백: AWS 멀티모달 컬럼 제거 중...")
    
    connection = op.get_bind()
    
    # 인덱스 삭제
    connection.execute(text("""
        DROP INDEX IF EXISTS idx_doc_embedding_aws_multimodal_1024_ivfflat
    """))
    
    # 컬럼 삭제
    op.drop_column('doc_embedding', 'aws_multimodal_vector_1024')
    
    print("✅ 롤백 완료")
