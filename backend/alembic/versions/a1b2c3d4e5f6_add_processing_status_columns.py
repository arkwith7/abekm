"""add processing status columns to tb_file_bss_info

Revision ID: a1b2c3d4e5f6
Revises: b38f1337b6ae
Create Date: 2025-10-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'b38f1337b6ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    비동기 문서 처리 상태 관리를 위한 컬럼 추가
    
    추가되는 컬럼:
    - processing_status: 처리 상태 (pending/processing/completed/failed)
    - processing_error: 처리 오류 메시지
    - processing_started_at: 처리 시작 시간
    - processing_completed_at: 처리 완료 시간
    """
    # tb_file_bss_info 테이블에 컬럼 추가
    op.add_column('tb_file_bss_info', 
        sa.Column('processing_status', sa.String(20), server_default='pending', nullable=True, 
                  comment='처리 상태 (pending/processing/completed/failed)'))
    
    op.add_column('tb_file_bss_info',
        sa.Column('processing_error', sa.Text(), nullable=True,
                  comment='처리 오류 메시지'))
    
    op.add_column('tb_file_bss_info',
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True,
                  comment='처리 시작 시간'))
    
    op.add_column('tb_file_bss_info',
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True,
                  comment='처리 완료 시간'))
    
    # 인덱스 추가 (상태 조회 최적화)
    op.create_index('idx_file_bss_info_processing_status', 'tb_file_bss_info', ['processing_status'])
    
    # 기존 데이터는 completed 상태로 설정
    op.execute("""
        UPDATE tb_file_bss_info 
        SET processing_status = 'completed', 
            processing_completed_at = created_date
        WHERE processing_status IS NULL OR processing_status = 'pending'
    """)


def downgrade() -> None:
    """마이그레이션 롤백"""
    # 인덱스 삭제
    op.drop_index('idx_file_bss_info_processing_status', table_name='tb_file_bss_info')
    
    # 컬럼 삭제
    op.drop_column('tb_file_bss_info', 'processing_completed_at')
    op.drop_column('tb_file_bss_info', 'processing_started_at')
    op.drop_column('tb_file_bss_info', 'processing_error')
    op.drop_column('tb_file_bss_info', 'processing_status')
