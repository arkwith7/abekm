"""add vendor-specific vector columns for Azure and AWS

Revision ID: 20251114_001
Revises: 20251106_001
Create Date: 2025-11-14 00:00:00.000000

목적:
- 벤더별 전용 벡터 컬럼 추가 (Azure/AWS 분리)
- 기존 공용 vector 컬럼 유지 (하위 호환성)
- 고정 차원 인덱스로 검색 성능 최적화

변경 사항:
1. doc_embedding 테이블:
   - azure_vector_1536: Azure text-embedding-3-small (1536d)
   - azure_vector_3072: Azure text-embedding-3-large (3072d)
   - aws_vector_1024: AWS Titan v2 (1024d)
   - aws_vector_256: AWS Titan v2 small (256d)
   - provider: 벤더 구분 컬럼 ('azure' | 'aws')

2. vs_doc_contents_chunks 테이블:
   - azure_embedding_1536: Azure 전용 (1536d)
   - aws_embedding_1024: AWS 전용 (1024d)
   - embedding_provider: 벤더 구분

3. 인덱스 생성:
   - 벤더별 전용 IVFFlat 인덱스 (CONCURRENTLY)
   - Provider별 부분 인덱스

마이그레이션 전략:
- 기존 vector 컬럼 유지 (점진적 마이그레이션)
- NULL 허용으로 무중단 배포
- 기존 데이터는 provider 값으로 자동 분류
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '20251114_001'
down_revision: Union[str, None] = '20251106_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    벤더별 전용 벡터 컬럼 추가
    """
    print("\n" + "="*80)
    print("🚀 [벤더별 벡터 컬럼 분리 마이그레이션 시작]")
    print("="*80 + "\n")
    
    connection = op.get_bind()
    
    # =========================================================================
    # 1. doc_embedding 테이블: 벤더별 컬럼 추가
    # =========================================================================
    print("\n1️⃣ doc_embedding 테이블에 벤더별 컬럼 추가...")
    
    # Provider 컬럼 추가
    op.add_column('doc_embedding',
        sa.Column('provider', sa.String(20), nullable=True, comment='벤더 구분 (azure | aws)')
    )
    
    # Azure 전용 컬럼
    op.add_column('doc_embedding',
        sa.Column('azure_vector_1536', Vector(1536), nullable=True, 
                  comment='Azure text-embedding-3-small (1536d)')
    )
    op.add_column('doc_embedding',
        sa.Column('azure_vector_3072', Vector(3072), nullable=True,
                  comment='Azure text-embedding-3-large (3072d)')
    )
    
    # AWS 전용 컬럼
    op.add_column('doc_embedding',
        sa.Column('aws_vector_1024', Vector(1024), nullable=True,
                  comment='AWS Titan v2 / Cohere v4 (1024d)')
    )
    op.add_column('doc_embedding',
        sa.Column('aws_vector_256', Vector(256), nullable=True,
                  comment='AWS Titan v2 small (256d)')
    )
    
    print("   ✅ 벤더별 벡터 컬럼 추가 완료")
    
    # =========================================================================
    # 2. 기존 데이터 마이그레이션 (provider 값 설정)
    # =========================================================================
    print("\n2️⃣ 기존 데이터 provider 값 설정...")
    
    # Azure 모델 분류
    connection.execute(text("""
        UPDATE doc_embedding 
        SET provider = 'azure'
        WHERE model_name LIKE 'text-embedding%'
           OR model_name LIKE 'ada%'
           OR model_name LIKE '%openai%'
    """))
    
    # AWS 모델 분류
    connection.execute(text("""
        UPDATE doc_embedding 
        SET provider = 'aws'
        WHERE model_name LIKE 'amazon.titan%'
           OR model_name LIKE 'cohere.embed%'
    """))
    
    # 기존 vector → 벤더별 컬럼 복사 (dimension 기준)
    connection.execute(text("""
        UPDATE doc_embedding 
        SET azure_vector_1536 = vector
        WHERE provider = 'azure' AND dimension = 1536
    """))
    
    connection.execute(text("""
        UPDATE doc_embedding 
        SET azure_vector_3072 = vector
        WHERE provider = 'azure' AND dimension = 3072
    """))
    
    connection.execute(text("""
        UPDATE doc_embedding 
        SET aws_vector_1024 = vector
        WHERE provider = 'aws' AND dimension = 1024
    """))
    
    print("   ✅ 기존 데이터 마이그레이션 완료")
    
    # =========================================================================
    # 3. vs_doc_contents_chunks 테이블: 벤더별 컬럼 추가
    # =========================================================================
    print("\n3️⃣ vs_doc_contents_chunks 테이블에 벤더별 컬럼 추가...")
    
    # Provider 컬럼 추가
    op.add_column('vs_doc_contents_chunks',
        sa.Column('embedding_provider', sa.String(20), nullable=True,
                  comment='임베딩 벤더 (azure | aws)')
    )
    
    # Azure 전용 임베딩
    op.add_column('vs_doc_contents_chunks',
        sa.Column('azure_embedding_1536', Vector(1536), nullable=True,
                  comment='Azure text-embedding-3-small (1536d)')
    )
    
    # AWS 전용 임베딩
    op.add_column('vs_doc_contents_chunks',
        sa.Column('aws_embedding_1024', Vector(1024), nullable=True,
                  comment='AWS Titan v2 (1024d)')
    )
    
    # 기존 데이터 마이그레이션 (기본값: azure)
    connection.execute(text("""
        UPDATE vs_doc_contents_chunks 
        SET embedding_provider = 'azure',
            azure_embedding_1536 = chunk_embedding
        WHERE chunk_embedding IS NOT NULL
    """))
    
    print("   ✅ vs_doc_contents_chunks 벤더별 컬럼 추가 완료")
    
    # =========================================================================
    # 4. 인덱스 생성 (일반 인덱스 - 트랜잭션 내 실행 가능)
    # =========================================================================
    print("\n4️⃣ 벤더별 전용 인덱스 생성...")
    
    # Provider 인덱스
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_provider
        ON doc_embedding(provider)
        WHERE provider IS NOT NULL
    """))
    
    # Azure 1536d 벡터 인덱스
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_azure_1536_ivfflat
        ON doc_embedding 
        USING ivfflat (azure_vector_1536 vector_cosine_ops)
        WITH (lists = 100)
        WHERE azure_vector_1536 IS NOT NULL
    """))
    
    # AWS 1024d 벡터 인덱스
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_aws_1024_ivfflat
        ON doc_embedding 
        USING ivfflat (aws_vector_1024 vector_cosine_ops)
        WITH (lists = 100)
        WHERE aws_vector_1024 IS NOT NULL
    """))
    
    # vs_doc_contents_chunks 인덱스
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_vs_chunks_azure_1536_ivfflat
        ON vs_doc_contents_chunks 
        USING ivfflat (azure_embedding_1536 vector_cosine_ops)
        WITH (lists = 100)
        WHERE azure_embedding_1536 IS NOT NULL
    """))
    
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_vs_chunks_aws_1024_ivfflat
        ON vs_doc_contents_chunks 
        USING ivfflat (aws_embedding_1024 vector_cosine_ops)
        WITH (lists = 100)
        WHERE aws_embedding_1024 IS NOT NULL
    """))
    
    print("   ✅ 벤더별 전용 인덱스 생성 완료")
    
    # =========================================================================
    # 5. 통계 정보 출력
    # =========================================================================
    print("\n5️⃣ 마이그레이션 통계...")
    
    result = connection.execute(text("""
        SELECT 
            provider,
            COUNT(*) as count,
            COUNT(azure_vector_1536) as azure_1536_count,
            COUNT(azure_vector_3072) as azure_3072_count,
            COUNT(aws_vector_1024) as aws_1024_count
        FROM doc_embedding
        GROUP BY provider
    """))
    
    for row in result:
        print(f"   📊 Provider: {row[0]}, 총: {row[1]}개, "
              f"Azure 1536d: {row[2]}개, Azure 3072d: {row[3]}개, AWS 1024d: {row[4]}개")
    
    print("\n" + "="*80)
    print("✅ [벤더별 벡터 컬럼 분리 마이그레이션 완료]")
    print("="*80 + "\n")


def downgrade() -> None:
    """
    벤더별 컬럼 제거 (롤백)
    """
    print("\n⚠️ [벤더별 벡터 컬럼 분리 롤백 시작]")
    
    # 인덱스 삭제
    op.drop_index('idx_doc_embedding_provider', table_name='doc_embedding', if_exists=True)
    op.drop_index('idx_doc_embedding_azure_1536_ivfflat', table_name='doc_embedding', if_exists=True)
    op.drop_index('idx_doc_embedding_aws_1024_ivfflat', table_name='doc_embedding', if_exists=True)
    op.drop_index('idx_vs_chunks_azure_1536_ivfflat', table_name='vs_doc_contents_chunks', if_exists=True)
    op.drop_index('idx_vs_chunks_aws_1024_ivfflat', table_name='vs_doc_contents_chunks', if_exists=True)
    
    # doc_embedding 컬럼 제거
    op.drop_column('doc_embedding', 'aws_vector_256')
    op.drop_column('doc_embedding', 'aws_vector_1024')
    op.drop_column('doc_embedding', 'azure_vector_3072')
    op.drop_column('doc_embedding', 'azure_vector_1536')
    op.drop_column('doc_embedding', 'provider')
    
    # vs_doc_contents_chunks 컬럼 제거
    op.drop_column('vs_doc_contents_chunks', 'aws_embedding_1024')
    op.drop_column('vs_doc_contents_chunks', 'azure_embedding_1536')
    op.drop_column('vs_doc_contents_chunks', 'embedding_provider')
    
    print("✅ [롤백 완료]\n")
