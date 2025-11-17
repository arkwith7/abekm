"""add_document_type_and_processing_options

Revision ID: 47e3c2b8ea1d
Revises: 6c3d0cf1653d
Create Date: 2025-10-20 02:38:16.429849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '47e3c2b8ea1d'
down_revision: Union[str, Sequence[str], None] = '6c3d0cf1653d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    문서 유형별 파이프라인 지원을 위한 컬럼 추가
    - document_type: 문서 유형 (general, academic_paper, patent, etc.)
    - processing_options: 유형별 처리 옵션 (JSONB)
    """
    # 1. document_type 컬럼 추가
    op.add_column(
        'tb_file_bss_info',
        sa.Column(
            'document_type',
            sa.String(50),
            nullable=False,
            server_default='general',
            comment='문서 유형 (general/academic_paper/patent/technical_report/business_document/presentation)'
        )
    )
    
    # 2. processing_options 컬럼 추가 (JSONB)
    op.add_column(
        'tb_file_bss_info',
        sa.Column(
            'processing_options',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}',
            comment='문서 유형별 처리 옵션 (extract_figures, parse_references 등)'
        )
    )
    
    # 3. document_type 체크 제약 조건 추가
    op.create_check_constraint(
        'chk_document_type',
        'tb_file_bss_info',
        "document_type IN ('general', 'academic_paper', 'patent', 'technical_report', 'business_document', 'presentation')"
    )
    
    # 4. document_type 인덱스 생성
    op.create_index(
        'idx_file_bss_info_document_type',
        'tb_file_bss_info',
        ['document_type']
    )
    
    # 5. 복합 인덱스 생성 (container + document_type)
    op.create_index(
        'idx_file_bss_info_container_type',
        'tb_file_bss_info',
        ['knowledge_container_id', 'document_type']
    )
    
    # 6. processing_options GIN 인덱스 생성 (JSONB 검색 최적화)
    op.execute(
        "CREATE INDEX idx_file_bss_info_processing_options "
        "ON tb_file_bss_info USING GIN (processing_options)"
    )
    
    # 7. 기존 데이터 자동 분류 (선택적)
    # 학술 논문 감지
    op.execute("""
        UPDATE tb_file_bss_info
        SET document_type = 'academic_paper'
        WHERE document_type = 'general'
          AND (
            file_lgc_nm ILIKE '%journal%' OR
            file_lgc_nm ILIKE '%paper%' OR
            file_lgc_nm ILIKE '%conference%' OR
            file_lgc_nm ILIKE '%thesis%' OR
            file_lgc_nm ILIKE '%학술%' OR
            file_lgc_nm ILIKE '%논문%'
          )
    """)
    
    # 특허 문서 감지
    op.execute("""
        UPDATE tb_file_bss_info
        SET document_type = 'patent'
        WHERE document_type = 'general'
          AND (
            file_lgc_nm ILIKE '%patent%' OR
            file_lgc_nm ILIKE '%특허%'
          )
    """)
    
    # 프레젠테이션 감지
    op.execute("""
        UPDATE tb_file_bss_info
        SET document_type = 'presentation'
        WHERE document_type = 'general'
          AND file_extsn IN ('pptx', 'ppt')
    """)
    
    # 8. 통계 뷰 생성
    op.execute("""
        CREATE OR REPLACE VIEW vw_document_type_stats AS
        SELECT 
            document_type,
            COUNT(*) as total_documents,
            COUNT(CASE WHEN del_yn = 'N' THEN 1 END) as active_documents,
            COUNT(CASE WHEN del_yn = 'Y' THEN 1 END) as deleted_documents,
            MIN(created_date) as first_uploaded,
            MAX(created_date) as last_uploaded
        FROM tb_file_bss_info
        GROUP BY document_type
    """)


def downgrade() -> None:
    """마이그레이션 롤백"""
    # 1. 통계 뷰 삭제
    op.execute("DROP VIEW IF EXISTS vw_document_type_stats")
    
    # 2. 인덱스 삭제
    op.drop_index('idx_file_bss_info_processing_options', 'tb_file_bss_info')
    op.drop_index('idx_file_bss_info_container_type', 'tb_file_bss_info')
    op.drop_index('idx_file_bss_info_document_type', 'tb_file_bss_info')
    
    # 3. 체크 제약 조건 삭제
    op.drop_constraint('chk_document_type', 'tb_file_bss_info', type_='check')
    
    # 4. 컬럼 삭제
    op.drop_column('tb_file_bss_info', 'processing_options')
    op.drop_column('tb_file_bss_info', 'document_type')
