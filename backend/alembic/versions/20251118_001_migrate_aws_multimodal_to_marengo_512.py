"""migrate aws multimodal to marengo 512d

Revision ID: 20251118_001
Revises: 20251114_003
Create Date: 2025-11-18 00:00:00.000000

목적:
- AWS 멀티모달 임베딩 컬럼을 Cohere(1024d)에서 TwelveLabs Marengo(512d)로 마이그레이션
- 이미지/테이블 멀티모달 임베딩을 위한 512d 컬럼 추가

변경 사항:
1. doc_embedding 테이블:
   - aws_marengo_vector_512 추가: TwelveLabs Marengo Embed 3.0 (512d)
   - aws_multimodal_vector_1024를 deprecated로 표시 (데이터는 유지)
   
2. vs_doc_contents_chunks 테이블:
   - multimodal_embedding 추가: 일반 RAG용 멀티모달 임베딩 (512d)
   
3. 인덱스 생성:
   - AWS Marengo 벡터 전용 IVFFlat 인덱스
   - vs_doc_contents_chunks multimodal_embedding 인덱스

배경:
- 이전: Cohere Embed v4 (1024d, 텍스트 중심)
- 현재: TwelveLabs Marengo (512d, 이미지+텍스트 멀티모달)
- 논문 처리: 텍스트(Titan 1024d) + 그림/테이블(Marengo 512d)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '20251118_001'
down_revision: Union[str, None] = '20251114_003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    AWS 멀티모달 임베딩을 Marengo 512d로 마이그레이션
    """
    print("\n" + "="*80)
    print("🚀 [AWS 멀티모달 → TwelveLabs Marengo 512d 마이그레이션]")
    print("="*80 + "\n")
    
    connection = op.get_bind()
    
    # =========================================================================
    # 1. doc_embedding 테이블: AWS Marengo 512d 컬럼 추가
    # =========================================================================
    print("1️⃣ doc_embedding 테이블에 aws_marengo_vector_512 컬럼 추가...")
    
    # 컬럼 존재 여부 확인
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'doc_embedding' 
            AND column_name = 'aws_marengo_vector_512'
        );
    """))
    column_exists = result.scalar()
    
    if not column_exists:
        op.add_column('doc_embedding',
            sa.Column('aws_marengo_vector_512', Vector(512), nullable=True,
                      comment='AWS TwelveLabs Marengo Embed 3.0 multimodal (512d)')
        )
        print("   ✅ aws_marengo_vector_512 컬럼 추가 완료")
        
        # 인덱스 생성
        print("   📊 aws_marengo_vector_512 인덱스 생성 중...")
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_doc_embedding_aws_marengo_vector_512 
            ON doc_embedding 
            USING ivfflat (aws_marengo_vector_512 vector_cosine_ops)
            WITH (lists = 100);
        """))
        print("   ✅ 인덱스 생성 완료")
    else:
        print("   ⏭️  aws_marengo_vector_512 컬럼 이미 존재")
    
    # =========================================================================
    # 2. doc_embedding 테이블: aws_multimodal_vector_1024 코멘트 업데이트
    # =========================================================================
    print("\n2️⃣ aws_multimodal_vector_1024 컬럼을 deprecated로 표시...")
    connection.execute(text("""
        COMMENT ON COLUMN doc_embedding.aws_multimodal_vector_1024 
        IS '[DEPRECATED] AWS Cohere Embed v4 멀티모달 (1024d) - Use aws_marengo_vector_512 instead';
    """))
    print("   ✅ deprecated 표시 완료")
    
    # =========================================================================
    # 3. vs_doc_contents_chunks 테이블: multimodal_embedding 컬럼 추가
    # =========================================================================
    print("\n3️⃣ vs_doc_contents_chunks 테이블에 multimodal_embedding 컬럼 추가...")
    
    # 컬럼 존재 여부 확인
    result = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'vs_doc_contents_chunks' 
            AND column_name = 'multimodal_embedding'
        );
    """))
    column_exists = result.scalar()
    
    if not column_exists:
        op.add_column('vs_doc_contents_chunks',
            sa.Column('multimodal_embedding', Vector(512), nullable=True,
                      comment='Twelvelabs Marengo 이미지 임베딩 (512d)')
        )
        print("   ✅ multimodal_embedding 컬럼 추가 완료")
        
        # 인덱스 생성
        print("   📊 multimodal_embedding 인덱스 생성 중...")
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vs_doc_chunks_multimodal_embedding 
            ON vs_doc_contents_chunks 
            USING ivfflat (multimodal_embedding vector_cosine_ops)
            WITH (lists = 100);
        """))
        print("   ✅ 인덱스 생성 완료")
    else:
        print("   ⏭️  multimodal_embedding 컬럼 이미 존재")
    
    # =========================================================================
    # 4. 결과 확인
    # =========================================================================
    print("\n4️⃣ 마이그레이션 결과 확인...")
    
    # doc_embedding 테이블 벡터 컬럼 확인
    result = connection.execute(text("""
        SELECT 
            column_name,
            CASE 
                WHEN data_type = 'USER-DEFINED' AND udt_name = 'vector' THEN
                    (SELECT pg_catalog.format_type(atttypid, atttypmod) 
                     FROM pg_attribute 
                     WHERE attrelid = 'doc_embedding'::regclass 
                     AND attname = column_name)
                ELSE udt_name
            END as type_detail
        FROM information_schema.columns 
        WHERE table_name = 'doc_embedding'
        AND (column_name LIKE '%marengo%' OR column_name LIKE '%multimodal%')
        ORDER BY ordinal_position;
    """))
    
    print("\n   📊 doc_embedding 테이블 멀티모달 컬럼:")
    for row in result:
        print(f"      - {row[0]:35s} | {row[1]}")
    
    # vs_doc_contents_chunks 테이블 벡터 컬럼 확인
    result = connection.execute(text("""
        SELECT 
            column_name,
            CASE 
                WHEN data_type = 'USER-DEFINED' AND udt_name = 'vector' THEN
                    (SELECT pg_catalog.format_type(atttypid, atttypmod) 
                     FROM pg_attribute 
                     WHERE attrelid = 'vs_doc_contents_chunks'::regclass 
                     AND attname = column_name)
                ELSE udt_name
            END as type_detail
        FROM information_schema.columns 
        WHERE table_name = 'vs_doc_contents_chunks'
        AND column_name LIKE '%embedding%'
        ORDER BY ordinal_position;
    """))
    
    print("\n   📊 vs_doc_contents_chunks 테이블 임베딩 컬럼:")
    for row in result:
        print(f"      - {row[0]:35s} | {row[1]}")
    
    print("\n" + "="*80)
    print("✅ 마이그레이션 완료!")
    print("="*80 + "\n")


def downgrade() -> None:
    """
    마이그레이션 롤백
    """
    print("\n" + "="*80)
    print("⏪ [마이그레이션 롤백]")
    print("="*80 + "\n")
    
    connection = op.get_bind()
    
    # 인덱스 삭제
    print("1️⃣ 인덱스 삭제 중...")
    connection.execute(text("DROP INDEX IF EXISTS idx_doc_embedding_aws_marengo_vector_512;"))
    connection.execute(text("DROP INDEX IF EXISTS idx_vs_doc_chunks_multimodal_embedding;"))
    print("   ✅ 인덱스 삭제 완료")
    
    # 컬럼 삭제
    print("\n2️⃣ 컬럼 삭제 중...")
    op.drop_column('doc_embedding', 'aws_marengo_vector_512')
    op.drop_column('vs_doc_contents_chunks', 'multimodal_embedding')
    print("   ✅ 컬럼 삭제 완료")
    
    # aws_multimodal_vector_1024 코멘트 복원
    print("\n3️⃣ aws_multimodal_vector_1024 코멘트 복원...")
    connection.execute(text("""
        COMMENT ON COLUMN doc_embedding.aws_multimodal_vector_1024 
        IS 'AWS Cohere Embed v4 멀티모달 (1024d)';
    """))
    print("   ✅ 코멘트 복원 완료")
    
    print("\n" + "="*80)
    print("✅ 롤백 완료!")
    print("="*80 + "\n")
