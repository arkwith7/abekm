"""Migrate vs_doc_contents_chunks to 1536 dimensions

Revision ID: k3l4m5n6o7p8
Revises: j1k2l3m4n5o6
Create Date: 2025-10-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'k3l4m5n6o7p8'
down_revision = 'j1k2l3m4n5o6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    vs_doc_contents_chunks 테이블을 1536차원으로 마이그레이션
    - .env 설정: VECTOR_DIMENSION=1536, text-embedding-3-small 사용
    - pgvector 0.5.1: HNSW/IVFFLAT 최대 2000차원 지원 (1536은 안전)
    """
    print("\n" + "=" * 80)
    print("🔄 vs_doc_contents_chunks 마이그레이션 시작: 1024 → 1536 차원")
    print("=" * 80)
    
    # 1. 기존 HNSW 인덱스 삭제 (1024차원)
    print("\n[1/5] 기존 HNSW 인덱스 삭제 중...")
    op.execute("DROP INDEX IF EXISTS idx_vs_doc_chunks_embedding")
    print("   ✅ idx_vs_doc_chunks_embedding 삭제 완료")
    
    # 2. 기존 데이터 백업 (선택적, 데이터가 있는 경우)
    print("\n[2/5] 기존 데이터 확인 중...")
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT COUNT(*) FROM vs_doc_contents_chunks"))
    count = result.scalar() or 0
    print(f"   📊 현재 레코드 수: {count}개")
    
    if count > 0:
        print("   ⚠️  기존 데이터 발견! 1536차원으로 재임베딩 필요")
        print("   💡 마이그레이션 후 문서 재업로드 권장")
    
    # 3. 벡터 컬럼 타입 변경 (1024 → 1536)
    print("\n[3/5] chunk_embedding 컬럼 차원 변경 중: 1024 → 1536")
    op.execute("""
        ALTER TABLE vs_doc_contents_chunks 
        ALTER COLUMN chunk_embedding TYPE vector(1536) 
        USING chunk_embedding::text::vector(1536)
    """)
    print("   ✅ chunk_embedding 컬럼 → vector(1536) 변경 완료")
    
    # 4. 새로운 HNSW 인덱스 생성 (1536차원)
    print("\n[4/5] 새로운 HNSW 인덱스 생성 중...")
    op.execute("""
        CREATE INDEX idx_vs_doc_chunks_embedding 
        ON vs_doc_contents_chunks 
        USING hnsw (chunk_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    print("   ✅ HNSW 인덱스 (1536차원) 생성 완료")
    print("   📊 인덱스 파라미터: m=16, ef_construction=64")
    
    # 5. 마이그레이션 완료 메시지
    print("\n[5/5] 마이그레이션 완료!")
    print("=" * 80)
    print("✅ vs_doc_contents_chunks 마이그레이션 성공")
    print("=" * 80)
    print("\n📋 마이그레이션 요약:")
    print("   - 벡터 차원: 1024 → 1536")
    print("   - 임베딩 모델: text-embedding-3-small (Azure OpenAI)")
    print("   - 인덱스: HNSW (m=16, ef_construction=64)")
    print("   - pgvector 버전: 0.5.1 호환 (2000차원 제한 통과)")
    print("\n⚠️  다음 단계:")
    print("   1. 기존 문서 삭제 및 재업로드")
    print("   2. text-embedding-3-small (1536차원) 임베딩 생성 확인")
    print("   3. 검색 기능 테스트")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """
    롤백: 1536차원 → 1024차원
    (주의: 기존 1536차원 임베딩 데이터는 손실됨)
    """
    print("\n" + "=" * 80)
    print("🔄 vs_doc_contents_chunks 롤백 시작: 1536 → 1024 차원")
    print("=" * 80)
    
    # 1. HNSW 인덱스 삭제
    print("\n[1/3] HNSW 인덱스 삭제 중...")
    op.execute("DROP INDEX IF EXISTS idx_vs_doc_chunks_embedding")
    print("   ✅ 인덱스 삭제 완료")
    
    # 2. 벡터 컬럼 타입 변경 (1536 → 1024)
    print("\n[2/3] chunk_embedding 컬럼 차원 변경 중: 1536 → 1024")
    op.execute("""
        ALTER TABLE vs_doc_contents_chunks 
        ALTER COLUMN chunk_embedding TYPE vector(1024)
        USING chunk_embedding::text::vector(1024)
    """)
    print("   ✅ chunk_embedding 컬럼 → vector(1024) 변경 완료")
    
    # 3. 이전 HNSW 인덱스 재생성
    print("\n[3/3] 이전 HNSW 인덱스 재생성 중...")
    op.execute("""
        CREATE INDEX idx_vs_doc_chunks_embedding 
        ON vs_doc_contents_chunks 
        USING hnsw (chunk_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    print("   ✅ HNSW 인덱스 (1024차원) 재생성 완료")
    
    print("\n✅ 롤백 완료: 1024차원으로 복원")
    print("=" * 80 + "\n")
