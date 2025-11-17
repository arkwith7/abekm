"""멀티모달 검색 지원 - CLIP 벡터 필드 추가

Revision ID: 20251017_001
Revises: 20251015_074
Create Date: 2025-10-17

멀티모달 검색을 위한 CLIP 임베딩 벡터 필드 추가:
- doc_embedding.clip_vector (512차원): Azure CLIP 이미지/텍스트 임베딩
- HNSW 인덱스: 코사인 유사도 기반 고속 검색
- 기존 vector(1536d): 텍스트 임베딩 유지
- 듀얼 벡터 전략: 텍스트(1536d) + 멀티모달(512d)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '20251017_001'
down_revision: Union[str, None] = '20251015_074'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """멀티모달 검색을 위한 CLIP 벡터 컬럼 및 인덱스 추가"""
    
    # 1. doc_embedding 테이블에 clip_vector 컬럼 추가 (512차원)
    op.add_column('doc_embedding', 
                  sa.Column('clip_vector', Vector(512), nullable=True,
                           comment='Azure CLIP 멀티모달 임베딩 (512d) - 이미지/텍스트 크로스 모달'))
    
    # 2. HNSW 인덱스 생성 (코사인 유사도)
    # 참고: HNSW 파라미터
    # - m=16: 각 레이어의 최대 연결 수 (기본값, 검색 속도와 정확도 균형)
    # - ef_construction=64: 인덱스 생성 시 탐색 깊이 (기본값, 품질 향상)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_clip_vector 
        ON doc_embedding 
        USING hnsw (clip_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    
    # 3. 멀티모달 복합 인덱스 (file + modality)
    # 특정 파일의 이미지/텍스트 임베딩 필터링 최적화
    op.create_index('idx_doc_embedding_multimodal_filter', 
                    'doc_embedding', 
                    ['file_bss_info_sno', 'modality'], 
                    unique=False)
    
    # 4. CLIP 벡터 존재 여부 인덱스
    # clip_vector가 NULL이 아닌 레코드 빠르게 조회
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_embedding_clip_vector_exists
        ON doc_embedding (clip_vector)
        WHERE clip_vector IS NOT NULL;
    """)
    
    print("✅ 멀티모달 검색을 위한 CLIP 벡터 컬럼 및 인덱스 추가 완료")


def downgrade() -> None:
    """마이그레이션 롤백"""
    
    # 인덱스 삭제
    op.drop_index('idx_doc_embedding_clip_vector_exists', table_name='doc_embedding')
    op.drop_index('idx_doc_embedding_multimodal_filter', table_name='doc_embedding')
    op.execute("DROP INDEX IF EXISTS idx_doc_embedding_clip_vector;")
    
    # 컬럼 삭제
    op.drop_column('doc_embedding', 'clip_vector')
    
    print("✅ CLIP 벡터 관련 변경사항 롤백 완료")
