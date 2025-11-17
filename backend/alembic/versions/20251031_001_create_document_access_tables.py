"""create_document_access_tables

Revision ID: 20251031_001
Revises: 20251030_001
Create Date: 2025-10-31 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251031_001'
down_revision: Union[str, Sequence[str], None] = '20251030_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """문서 접근 제어 테이블 및 ENUM 타입 생성"""
    bind = op.get_bind()

    access_level_enum = postgresql.ENUM(
        'public', 'restricted', 'private',
        name='access_level_enum',
        create_type=False
    )
    rule_type_enum = postgresql.ENUM(
        'user', 'department',
        name='rule_type_enum',
        create_type=False
    )
    permission_level_enum = postgresql.ENUM(
        'view', 'download', 'edit',
        name='permission_level_enum',
        create_type=False
    )

    access_level_enum.create(bind, checkfirst=True)
    rule_type_enum.create(bind, checkfirst=True)
    permission_level_enum.create(bind, checkfirst=True)

    op.create_table(
        'tb_document_access_rules',
        sa.Column('rule_id', sa.Integer(), primary_key=True, autoincrement=True, comment='접근 규칙 일련번호'),
        sa.Column('file_bss_info_sno', sa.Integer(), sa.ForeignKey('tb_file_bss_info.file_bss_info_sno', ondelete='CASCADE'), nullable=False, comment='파일 기본 정보 일련번호'),
        sa.Column('access_level', access_level_enum, nullable=False, server_default=sa.text("'public'::access_level_enum"), comment='접근 레벨 (public/restricted/private)'),
        sa.Column('rule_type', rule_type_enum, nullable=True, comment='규칙 타입 (user/department)'),
        sa.Column('target_id', sa.String(length=100), nullable=True, comment='대상 ID (user: emp_no, department: dept_nm)'),
        sa.Column('permission_level', permission_level_enum, nullable=True, server_default=sa.text("'view'::permission_level_enum"), comment='권한 레벨 (view/download/edit)'),
        sa.Column('is_inherited', sa.String(length=1), nullable=False, server_default=sa.text("'Y'"), comment='컨테이너 권한 상속 여부 (Y/N)'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='추가 메타데이터 (규칙 설명, 유효기간 등)'),
        sa.Column('created_by', sa.String(length=50), nullable=False, comment='생성자 사번'),
        sa.Column('created_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='생성 일시'),
        sa.Column('last_modified_by', sa.String(length=50), nullable=True, comment='최종 수정자 사번'),
        sa.Column('last_modified_date', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()'), comment='최종 수정 일시'),
        sa.CheckConstraint(
            "(access_level = 'restricted' AND rule_type IS NOT NULL AND target_id IS NOT NULL) OR (access_level <> 'restricted')",
            name='check_restricted_requires_target'
        )
    )

    op.create_index('idx_document_access_file', 'tb_document_access_rules', ['file_bss_info_sno'])
    op.create_index('idx_document_access_level', 'tb_document_access_rules', ['access_level'])
    op.create_index('idx_document_access_target', 'tb_document_access_rules', ['rule_type', 'target_id'])
    op.create_index('idx_document_access_composite', 'tb_document_access_rules', ['file_bss_info_sno', 'access_level'])
    op.create_index('idx_document_access_inherited', 'tb_document_access_rules', ['is_inherited'])
    op.create_index('idx_document_access_created', 'tb_document_access_rules', ['created_date'])

    op.create_table(
        'tb_document_access_log',
        sa.Column('log_id', sa.Integer(), primary_key=True, autoincrement=True, comment='로그 일련번호'),
        sa.Column('file_bss_info_sno', sa.Integer(), sa.ForeignKey('tb_file_bss_info.file_bss_info_sno', ondelete='CASCADE'), nullable=False, comment='파일 기본 정보 일련번호'),
        sa.Column('user_emp_no', sa.String(length=20), nullable=False, comment='접근 사용자 사번'),
        sa.Column('access_type', sa.String(length=20), nullable=False, comment='접근 타입 (view/download/edit)'),
        sa.Column('access_granted', sa.String(length=1), nullable=False, comment='접근 허용 여부 (Y/N)'),
        sa.Column('denial_reason', sa.String(length=500), nullable=True, comment='접근 거부 사유'),
        sa.Column('accessed_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='접근 일시'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='추가 메타데이터 (IP, User-Agent 등)')
    )

    op.create_index('idx_access_log_file', 'tb_document_access_log', ['file_bss_info_sno'])
    op.create_index('idx_access_log_user', 'tb_document_access_log', ['user_emp_no'])
    op.create_index('idx_access_log_date', 'tb_document_access_log', ['accessed_date'])
    op.create_index('idx_access_log_granted', 'tb_document_access_log', ['access_granted'])


def downgrade() -> None:
    """문서 접근 제어 테이블 및 ENUM 타입 제거"""
    op.drop_index('idx_access_log_granted', table_name='tb_document_access_log')
    op.drop_index('idx_access_log_date', table_name='tb_document_access_log')
    op.drop_index('idx_access_log_user', table_name='tb_document_access_log')
    op.drop_index('idx_access_log_file', table_name='tb_document_access_log')
    op.drop_table('tb_document_access_log')

    op.drop_index('idx_document_access_created', table_name='tb_document_access_rules')
    op.drop_index('idx_document_access_inherited', table_name='tb_document_access_rules')
    op.drop_index('idx_document_access_composite', table_name='tb_document_access_rules')
    op.drop_index('idx_document_access_target', table_name='tb_document_access_rules')
    op.drop_index('idx_document_access_level', table_name='tb_document_access_rules')
    op.drop_index('idx_document_access_file', table_name='tb_document_access_rules')
    op.drop_table('tb_document_access_rules')

    bind = op.get_bind()
    permission_level_enum = postgresql.ENUM('view', 'download', 'edit', name='permission_level_enum')
    rule_type_enum = postgresql.ENUM('user', 'department', name='rule_type_enum')
    access_level_enum = postgresql.ENUM('public', 'restricted', 'private', name='access_level_enum')

    permission_level_enum.drop(bind, checkfirst=True)
    rule_type_enum.drop(bind, checkfirst=True)
    access_level_enum.drop(bind, checkfirst=True)
