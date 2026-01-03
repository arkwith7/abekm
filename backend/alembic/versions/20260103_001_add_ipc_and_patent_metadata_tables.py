"""add IPC code and patent metadata tables

Revision ID: 20260103_001
Revises: 20251225_001
Create Date: 2026-01-03 00:00:00.000000

Phase 1 (Week 1): IPC 코드 DB 구축 및 특허 메타데이터 테이블
- tb_ipc_code: 국제특허분류(IPC) 마스터 테이블
- tb_patent_metadata: 문서 시스템과 연계되는 특허 메타데이터 (간소화)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260103_001'
down_revision = '20251225_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create IPC and patent metadata tables."""
    
    # =========================================================================
    # 1. tb_ipc_code - IPC 분류 코드 마스터 테이블
    # =========================================================================
    op.create_table(
        'tb_ipc_code',
        sa.Column('code', sa.String(20), primary_key=True, comment='IPC 분류 코드 (예: H04W, H04W 4/00)'),
        sa.Column('level', sa.String(10), nullable=False, comment='분류 레벨 (SECTION/CLASS/SUBCLASS/GROUP/SUBGROUP)'),
        sa.Column('parent_code', sa.String(20), nullable=True, comment='상위 분류 코드 (SECTION의 경우 NULL)'),
        sa.Column('description_ko', sa.Text(), nullable=True, comment='한글 설명'),
        sa.Column('description_en', sa.Text(), nullable=True, comment='영문 설명'),
        sa.Column('section', sa.String(1), nullable=True, comment='섹션 (A~H)'),
        sa.Column('class_code', sa.String(3), nullable=True, comment='클래스 (H04 등)'),
        sa.Column('subclass_code', sa.String(4), nullable=True, comment='서브클래스 (H04W 등)'),
        sa.Column('is_active', sa.String(1), nullable=False, server_default='Y', comment='활성화 여부 (Y/N)'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_modified_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        comment='IPC 분류 코드 마스터 테이블'
    )
    
    # 인덱스
    op.create_index('idx_ipc_level', 'tb_ipc_code', ['level'])
    op.create_index('idx_ipc_parent', 'tb_ipc_code', ['parent_code'])
    op.create_index('idx_ipc_section', 'tb_ipc_code', ['section'])
    op.create_index('idx_ipc_active', 'tb_ipc_code', ['is_active'])
    
    # =========================================================================
    # 2. tb_patent_metadata - 특허 메타데이터 테이블
    # =========================================================================
    op.create_table(
        'tb_patent_metadata',
        sa.Column('metadata_id', sa.Integer(), autoincrement=True, primary_key=True, comment='메타데이터 ID'),
        sa.Column('file_bss_info_sno', sa.Integer(), nullable=True, comment='파일 기본 정보 일련번호 (tb_file_bss_info FK, nullable for external)'),
        sa.Column('application_number', sa.String(50), nullable=False, comment='출원번호 (예: 10-2023-0123456)'),
        sa.Column('publication_number', sa.String(50), nullable=True, comment='공개번호'),
        sa.Column('registration_number', sa.String(50), nullable=True, comment='등록번호'),
        sa.Column('ipc_codes', sa.Text(), nullable=True, comment='IPC 코드 목록 (쉼표 구분)'),
        sa.Column('main_ipc_code', sa.String(20), nullable=True, comment='주 IPC 코드'),
        sa.Column('applicant', sa.String(200), nullable=True, comment='대표 출원인'),
        sa.Column('inventor', sa.String(200), nullable=True, comment='대표 발명자'),
        sa.Column('legal_status', sa.String(50), nullable=False, server_default='APPLICATION', comment='법적 상태'),
        sa.Column('status_date', sa.DateTime(timezone=True), nullable=True, comment='상태 변경일'),
        sa.Column('application_date', sa.DateTime(timezone=True), nullable=True, comment='출원일'),
        sa.Column('publication_date', sa.DateTime(timezone=True), nullable=True, comment='공개일'),
        sa.Column('registration_date', sa.DateTime(timezone=True), nullable=True, comment='등록일'),
        sa.Column('abstract', sa.Text(), nullable=True, comment='초록'),
        sa.Column('claims_summary', sa.Text(), nullable=True, comment='청구항 요약'),
        sa.Column('knowledge_container_id', sa.String(50), nullable=True, comment='지식 컨테이너 ID'),
        sa.Column('created_by', sa.String(50), nullable=True, comment='생성자'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_modified_by', sa.String(50), nullable=True, comment='최종 수정자'),
        sa.Column('last_modified_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('del_yn', sa.String(1), nullable=False, server_default='N', comment='삭제 여부'),
        comment='특허 메타데이터 (문서 시스템 연계용)'
    )
    
    # 인덱스
    op.create_index('idx_patent_meta_file', 'tb_patent_metadata', ['file_bss_info_sno'])
    op.create_index('idx_patent_meta_app_no', 'tb_patent_metadata', ['application_number'], unique=True)
    op.create_index('idx_patent_meta_pub_no', 'tb_patent_metadata', ['publication_number'])
    op.create_index('idx_patent_meta_reg_no', 'tb_patent_metadata', ['registration_number'])
    op.create_index('idx_patent_meta_main_ipc', 'tb_patent_metadata', ['main_ipc_code'])
    op.create_index('idx_patent_meta_status', 'tb_patent_metadata', ['legal_status'])
    op.create_index('idx_patent_meta_container', 'tb_patent_metadata', ['knowledge_container_id'])
    op.create_index('idx_patent_meta_del_yn', 'tb_patent_metadata', ['del_yn'])
    
    # =========================================================================
    # 3. IPC 섹션 시드 데이터 (8개 섹션)
    # =========================================================================
    op.execute("""
        INSERT INTO tb_ipc_code (code, level, parent_code, description_ko, description_en, section, is_active) VALUES
        ('A', 'SECTION', NULL, '생활필需品', 'Human Necessities', 'A', 'Y'),
        ('B', 'SECTION', NULL, '처리조작;운수', 'Performing Operations; Transporting', 'B', 'Y'),
        ('C', 'SECTION', NULL, '화학;야금', 'Chemistry; Metallurgy', 'C', 'Y'),
        ('D', 'SECTION', NULL, '섬유;지류', 'Textiles; Paper', 'D', 'Y'),
        ('E', 'SECTION', NULL, '고정구조물', 'Fixed Constructions', 'E', 'Y'),
        ('F', 'SECTION', NULL, '기계공학;조명;가열;무기;폭파', 'Mechanical Engineering; Lighting; Heating; Weapons; Blasting', 'F', 'Y'),
        ('G', 'SECTION', NULL, '물리학', 'Physics', 'G', 'Y'),
        ('H', 'SECTION', NULL, '전기', 'Electricity', 'H', 'Y');
    """)
    
    # 주요 클래스 샘플 (대표적인 몇 개만 추가)
    op.execute("""
        INSERT INTO tb_ipc_code (code, level, parent_code, description_ko, description_en, section, class_code, is_active) VALUES
        ('G06', 'CLASS', 'G', '계산;계수', 'Computing; Calculating; Counting', 'G', 'G06', 'Y'),
        ('H04', 'CLASS', 'H', '전기통신기술', 'Electric Communication Technique', 'H', 'H04', 'Y');
    """)
    
    # 주요 서브클래스 샘플
    op.execute("""
        INSERT INTO tb_ipc_code (code, level, parent_code, description_ko, description_en, section, class_code, subclass_code, is_active) VALUES
        ('G06N', 'SUBCLASS', 'G06', '특정한 계산모델에 기초한 컴퓨터시스템', 'Computer Systems Based on Specific Computational Models', 'G', 'G06', 'G06N', 'Y'),
        ('H04W', 'SUBCLASS', 'H04', '무선통신네트워크', 'Wireless Communication Networks', 'H', 'H04', 'H04W', 'Y');
    """)


def downgrade() -> None:
    """Drop IPC and patent metadata tables."""
    op.drop_index('idx_patent_meta_del_yn', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_container', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_status', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_main_ipc', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_reg_no', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_pub_no', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_app_no', table_name='tb_patent_metadata')
    op.drop_index('idx_patent_meta_file', table_name='tb_patent_metadata')
    op.drop_table('tb_patent_metadata')
    
    op.drop_index('idx_ipc_active', table_name='tb_ipc_code')
    op.drop_index('idx_ipc_section', table_name='tb_ipc_code')
    op.drop_index('idx_ipc_parent', table_name='tb_ipc_code')
    op.drop_index('idx_ipc_level', table_name='tb_ipc_code')
    op.drop_table('tb_ipc_code')
