"""add_english_fts_to_doc_chunk

Revision ID: 20251106_001
Revises: f7g8h9i0j1k2
Create Date: 2025-11-06 09:30:00.000000

Purpose:
    doc_chunk 테이블에 영어 전문검색(FTS) 지원 추가
    - content_tsvector: 영어 전문검색 벡터 추가
    - 영어 논문 청크 단위 정밀 검색 가능
    
Benefits:
    - RAG 검색 시 영어 논문 청크 검색 개선
    - "Ambidextrous Leadership", "Innovation" 등 영어 키워드 검색 지원
    - 한국어 + 영어 dual configuration 통합 검색
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = '20251106_001'
down_revision: Union[str, Sequence[str], None] = '20251031_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    doc_chunk 테이블에 영어 FTS 추가
    
    Steps:
    1. content_tsvector 컬럼 추가
    2. GIN 인덱스 생성 (성능 최적화)
    3. 트리거 함수 생성 (INSERT/UPDATE 시 자동 업데이트)
    4. 트리거 생성
    5. 기존 데이터 마이그레이션
    """
    
    # Step 1: content_tsvector 컬럼 추가
    print("📝 doc_chunk 테이블에 content_tsvector 컬럼 추가 중...")
    op.add_column('doc_chunk',
        sa.Column('content_tsvector', TSVECTOR, nullable=True,
                 comment='전문검색 벡터 (Korean + English dual configuration)')
    )
    
    # Step 2: GIN 인덱스 생성 (전문검색 성능 최적화)
    print("📝 GIN 인덱스 생성 중...")
    op.create_index(
        'idx_doc_chunk_content_tsvector',
        'doc_chunk',
        ['content_tsvector'],
        postgresql_using='gin'
    )
    
    # Step 3: 트리거 함수 생성 (한국어 + 영어 dual configuration)
    print("📝 트리거 함수 생성 중...")
    op.execute("""
        CREATE OR REPLACE FUNCTION update_doc_chunk_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Dual configuration: Korean + English
            -- setweight 사용: 
            --   - Korean configuration (A): 한국어 형태소 분석, 높은 가중치
            --   - English configuration (A): 영어 stemming, stopword 제거
            --   - Simple configuration (B): 폴백용, 낮은 가중치
            NEW.content_tsvector := 
                setweight(to_tsvector('korean', COALESCE(NEW.content_text, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.content_text, '')), 'A') ||
                setweight(to_tsvector('simple', COALESCE(NEW.content_text, '')), 'B');
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Step 4: 트리거 생성 (INSERT, UPDATE 시 자동 실행)
    print("📝 트리거 생성 중...")
    op.execute("""
        DROP TRIGGER IF EXISTS trig_update_doc_chunk_content_tsvector ON doc_chunk;
        
        CREATE TRIGGER trig_update_doc_chunk_content_tsvector
        BEFORE INSERT OR UPDATE OF content_text
        ON doc_chunk
        FOR EACH ROW
        EXECUTE FUNCTION update_doc_chunk_content_tsvector();
    """)
    
    # Step 5: 기존 데이터 마이그레이션 (배치 처리로 성능 최적화)
    print("📝 기존 데이터 마이그레이션 시작...")
    print("   - 청크 테이블 크기 확인 중...")
    
    # 청크 수 확인
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT COUNT(*) FROM doc_chunk"))
    total_chunks = result.scalar()
    print(f"   - 총 {total_chunks:,}개 청크 발견")
    
    if total_chunks > 0:
        # 배치 크기 설정 (메모리 효율성)
        batch_size = 1000
        total_batches = (total_chunks + batch_size - 1) // batch_size
        
        print(f"   - {total_batches}개 배치로 나누어 처리 (배치 크기: {batch_size})")
        
        # 배치별로 업데이트 (트리거 실행)
        for batch_num in range(total_batches):
            offset = batch_num * batch_size
            op.execute(sa.text(f"""
                UPDATE doc_chunk
                SET content_text = content_text
                WHERE chunk_id IN (
                    SELECT chunk_id 
                    FROM doc_chunk 
                    WHERE content_tsvector IS NULL
                    ORDER BY chunk_id
                    LIMIT {batch_size}
                    OFFSET {offset}
                )
            """))
            
            if (batch_num + 1) % 10 == 0 or batch_num == total_batches - 1:
                print(f"   - 진행률: {batch_num + 1}/{total_batches} 배치 완료 ({(batch_num + 1) * 100 // total_batches}%)")
    
    print("✅ doc_chunk 영어 FTS 마이그레이션 완료!")
    print("✅ 이제 RAG 검색에서 영어 논문 청크를 정밀하게 검색할 수 있습니다.")


def downgrade() -> None:
    """
    doc_chunk 영어 FTS 제거 및 이전 상태로 복원
    """
    
    print("⚠️ doc_chunk 영어 FTS 제거 중...")
    
    # Step 1: 트리거 제거
    op.execute("DROP TRIGGER IF EXISTS trig_update_doc_chunk_content_tsvector ON doc_chunk;")
    
    # Step 2: 트리거 함수 제거
    op.execute("DROP FUNCTION IF EXISTS update_doc_chunk_content_tsvector();")
    
    # Step 3: 인덱스 제거
    op.drop_index('idx_doc_chunk_content_tsvector', table_name='doc_chunk')
    
    # Step 4: 컬럼 제거
    op.drop_column('doc_chunk', 'content_tsvector')
    
    print("✅ doc_chunk 영어 FTS 제거 완료")
