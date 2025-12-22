"""create patent collection tables

Revision ID: 20251222_002
Revises: 20251222_001
Create Date: 2025-12-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251222_002'
down_revision = '20251222_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """특허 수집 관리 테이블 생성"""
    
    # 1. tb_patent_collection_settings - 사용자별 특허 수집 설정
    op.create_table(
        'tb_patent_collection_settings',
        sa.Column('setting_id', sa.Integer(), autoincrement=True, nullable=False, comment='설정 ID'),
        sa.Column('user_emp_no', sa.String(20), nullable=False, comment='사용자 사번'),
        sa.Column('container_id', sa.String(50), nullable=False, comment='대상 컨테이너 ID'),
        sa.Column('search_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='검색 조건 (IPC, 키워드, 출원인)'),
        sa.Column('max_results', sa.Integer(), nullable=False, server_default='100', comment='최대 수집 건수'),
        sa.Column('auto_download_pdf', sa.Boolean(), nullable=False, server_default='false', comment='PDF 자동 다운로드 여부'),
        sa.Column('auto_generate_embeddings', sa.Boolean(), nullable=False, server_default='true', comment='임베딩 자동 생성 여부'),
        sa.Column('schedule_type', sa.String(20), nullable=False, server_default='manual', comment='스케줄 타입 (manual/daily/weekly/monthly)'),
        sa.Column('schedule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='스케줄 상세 설정'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='활성화 여부'),
        sa.Column('last_collection_date', sa.DateTime(timezone=True), nullable=True, comment='마지막 수집 일시'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='생성일'),
        sa.Column('updated_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='수정일'),
        sa.PrimaryKeyConstraint('setting_id'),
        sa.ForeignKeyConstraint(['user_emp_no'], ['tb_user.emp_no'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['container_id'], ['tb_knowledge_containers.container_id'], ondelete='CASCADE')
    )
    
    # 인덱스 생성
    op.create_index('idx_patent_collection_settings_user', 'tb_patent_collection_settings', ['user_emp_no'])
    op.create_index('idx_patent_collection_settings_container', 'tb_patent_collection_settings', ['container_id'])
    op.create_index('idx_patent_collection_settings_active', 'tb_patent_collection_settings', ['is_active'])
    
    # 2. tb_patent_collection_tasks - 특허 수집 작업 상태 추적
    op.create_table(
        'tb_patent_collection_tasks',
        sa.Column('task_id', sa.String(100), nullable=False, comment='Celery Task ID'),
        sa.Column('setting_id', sa.Integer(), nullable=True, comment='수집 설정 ID'),
        sa.Column('user_emp_no', sa.String(20), nullable=False, comment='사용자 사번'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', comment='작업 상태 (pending/running/completed/failed)'),
        sa.Column('progress_current', sa.Integer(), nullable=False, server_default='0', comment='현재 진행 건수'),
        sa.Column('progress_total', sa.Integer(), nullable=False, server_default='0', comment='전체 작업 건수'),
        sa.Column('collected_count', sa.Integer(), nullable=False, server_default='0', comment='수집 성공 건수'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0', comment='오류 건수'),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='오류 상세 정보'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='시작 시간'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='완료 시간'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='생성일'),
        sa.PrimaryKeyConstraint('task_id'),
        sa.ForeignKeyConstraint(['setting_id'], ['tb_patent_collection_settings.setting_id'], ondelete='SET NULL')
    )
    
    # 인덱스 생성
    op.create_index('idx_patent_collection_tasks_user', 'tb_patent_collection_tasks', ['user_emp_no'])
    op.create_index('idx_patent_collection_tasks_status', 'tb_patent_collection_tasks', ['status'])
    op.create_index('idx_patent_collection_tasks_setting', 'tb_patent_collection_tasks', ['setting_id'])
    
    # 3. tb_file_bss_info에 특허 관련 컬럼 추가 (이미 존재하지 않는 경우)
    # ALTER TABLE은 이미 존재하는 컬럼이면 오류가 발생하므로 조건부 추가
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='tb_file_bss_info' AND column_name='patent_application_number'
            ) THEN
                ALTER TABLE tb_file_bss_info 
                ADD COLUMN patent_application_number VARCHAR(50);
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='tb_file_bss_info' AND column_name='patent_publication_number'
            ) THEN
                ALTER TABLE tb_file_bss_info 
                ADD COLUMN patent_publication_number VARCHAR(50);
            END IF;
        END $$;
    """)
    
    # 특허 문서 검색을 위한 인덱스
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_bss_info_patent_app_no 
        ON tb_file_bss_info(patent_application_number) 
        WHERE patent_application_number IS NOT NULL;
    """)


def downgrade() -> None:
    """특허 수집 관리 테이블 삭제"""
    
    # 인덱스 삭제
    op.drop_index('idx_patent_collection_tasks_setting', table_name='tb_patent_collection_tasks')
    op.drop_index('idx_patent_collection_tasks_status', table_name='tb_patent_collection_tasks')
    op.drop_index('idx_patent_collection_tasks_user', table_name='tb_patent_collection_tasks')
    
    op.drop_index('idx_patent_collection_settings_active', table_name='tb_patent_collection_settings')
    op.drop_index('idx_patent_collection_settings_container', table_name='tb_patent_collection_settings')
    op.drop_index('idx_patent_collection_settings_user', table_name='tb_patent_collection_settings')
    
    # 테이블 삭제 (순서 중요: 외래키 참조 역순)
    op.drop_table('tb_patent_collection_tasks')
    op.drop_table('tb_patent_collection_settings')
    
    # tb_file_bss_info 컬럼 삭제
    op.execute("DROP INDEX IF EXISTS idx_file_bss_info_patent_app_no;")
    op.execute("ALTER TABLE tb_file_bss_info DROP COLUMN IF EXISTS patent_publication_number;")
    op.execute("ALTER TABLE tb_file_bss_info DROP COLUMN IF EXISTS patent_application_number;")
