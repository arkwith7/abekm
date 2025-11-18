"""add_permission_request_tables

Revision ID: 20251030_001
Revises: 20251017_001_add_clip_vector_for_multimodal
Create Date: 2025-10-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251030_001'
down_revision: Union[str, Sequence[str], None] = '7641fa6f6c28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """권한 요청 관리 테이블 생성"""
    
    # 테이블 존재 여부 확인
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # 1. 권한 요청 테이블
    if 'tb_permission_requests' not in existing_tables:
        op.create_table(
            'tb_permission_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('request_id', sa.String(length=50), nullable=False, unique=True, comment='요청 ID (REQ-20251030-001)'),
        
        # 요청자 정보
        sa.Column('requester_emp_no', sa.String(length=20), nullable=False, comment='요청자 사번'),
        sa.Column('requester_name', sa.String(length=100), nullable=True, comment='요청자 이름'),
        sa.Column('requester_department', sa.String(length=100), nullable=True, comment='요청자 부서'),
        
        # 대상 컨테이너 및 권한
        sa.Column('container_id', sa.String(length=50), nullable=False, comment='컨테이너 ID'),
        sa.Column('container_name', sa.String(length=200), nullable=True, comment='컨테이너 이름'),
        sa.Column('current_permission_level', sa.String(length=50), nullable=True, comment='현재 권한 레벨'),
        sa.Column('requested_permission_level', sa.String(length=50), nullable=False, comment='요청 권한 레벨'),
        
        # 요청 상세
        sa.Column('request_reason', sa.Text(), nullable=False, comment='요청 사유'),
        sa.Column('business_justification', sa.Text(), nullable=True, comment='업무 근거'),
        sa.Column('expected_usage_period', sa.String(length=100), nullable=True, comment='사용 예정 기간'),
        sa.Column('urgency_level', sa.String(length=20), server_default='normal', comment='긴급도 (urgent, high, normal, low)'),
        
        # 상태 관리
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False, comment='상태 (pending, approved, rejected, cancelled)'),
        
        # 처리 정보
        sa.Column('approver_emp_no', sa.String(length=20), nullable=True, comment='승인자 사번'),
        sa.Column('approver_name', sa.String(length=100), nullable=True, comment='승인자 이름'),
        sa.Column('approval_comment', sa.Text(), nullable=True, comment='승인 코멘트'),
        sa.Column('rejection_reason', sa.Text(), nullable=True, comment='거부 사유'),
        sa.Column('auto_approved', sa.Boolean(), server_default=sa.text('false'), comment='자동 승인 여부'),
        
        # 일시 정보
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='요청 일시'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True, comment='처리 일시'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='만료 일시'),
        
        # 외래키
        sa.ForeignKeyConstraint(['requester_emp_no'], ['tb_user.emp_no'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['container_id'], ['tb_knowledge_containers.container_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approver_emp_no'], ['tb_user.emp_no'], ondelete='SET NULL'),
        )
        
        # 인덱스
        op.create_index('idx_permission_requests_requester', 'tb_permission_requests', ['requester_emp_no'])
        op.create_index('idx_permission_requests_container', 'tb_permission_requests', ['container_id'])
        op.create_index('idx_permission_requests_status', 'tb_permission_requests', ['status'])
        op.create_index('idx_permission_requests_requested_at', 'tb_permission_requests', ['requested_at'], postgresql_using='btree', postgresql_ops={'requested_at': 'DESC'})
        op.create_index('idx_permission_requests_approver', 'tb_permission_requests', ['approver_emp_no'])
    
    # 2. 권한 감사 로그 테이블
    if 'tb_permission_audit_log' not in existing_tables:
        op.create_table(
            'tb_permission_audit_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('log_id', sa.String(length=50), nullable=False, unique=True, comment='로그 ID'),
        
        # 작업 정보
        sa.Column('action_type', sa.String(length=50), nullable=False, comment='작업 타입 (request_created, approved, rejected, cancelled)'),
        sa.Column('actor_emp_no', sa.String(length=20), nullable=False, comment='작업 수행자 사번'),
        sa.Column('actor_name', sa.String(length=100), nullable=True, comment='작업 수행자 이름'),
        
        # 대상 정보
        sa.Column('target_emp_no', sa.String(length=20), nullable=True, comment='대상 사용자 사번'),
        sa.Column('container_id', sa.String(length=50), nullable=True, comment='컨테이너 ID'),
        sa.Column('permission_level', sa.String(length=50), nullable=True, comment='권한 레벨'),
        
        # 요청 관련
        sa.Column('request_id', sa.String(length=50), nullable=True, comment='요청 ID'),
        
        # 상세 정보
        sa.Column('action_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='작업 상세 정보'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='IP 주소'),
        sa.Column('user_agent', sa.Text(), nullable=True, comment='User Agent'),
        
        # 일시
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='생성 일시'),
        
        # 외래키
        sa.ForeignKeyConstraint(['actor_emp_no'], ['tb_user.emp_no'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['request_id'], ['tb_permission_requests.request_id'], ondelete='SET NULL'),
        )
        
        # 인덱스
        op.create_index('idx_audit_log_action_type', 'tb_permission_audit_log', ['action_type'])
        op.create_index('idx_audit_log_actor', 'tb_permission_audit_log', ['actor_emp_no'])
        op.create_index('idx_audit_log_created_at', 'tb_permission_audit_log', ['created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
        op.create_index('idx_audit_log_request_id', 'tb_permission_audit_log', ['request_id'])
    
    # 3. 자동 승인 규칙 테이블
    if 'tb_auto_approval_rules' not in existing_tables:
        op.create_table(
            'tb_auto_approval_rules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('rule_id', sa.String(length=50), nullable=False, unique=True, comment='규칙 ID'),
        
        # 규칙 정보
        sa.Column('rule_name', sa.String(length=200), nullable=False, comment='규칙 이름'),
        sa.Column('description', sa.Text(), nullable=True, comment='규칙 설명'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False, comment='활성 상태'),
        sa.Column('priority', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='우선순위 (높을수록 먼저 적용)'),
        
        # 조건
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='승인 조건 (JSON)'),
        
        # 작업
        sa.Column('action', sa.String(length=50), server_default='auto_approve', nullable=False, comment='작업 (auto_approve, require_approval)'),
        
        # 생성 정보
        sa.Column('created_by', sa.String(length=20), nullable=True, comment='생성자 사번'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='생성 일시'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='수정 일시'),
        
        # 외래키
        sa.ForeignKeyConstraint(['created_by'], ['tb_user.emp_no'], ondelete='SET NULL'),
        )
        
        # 인덱스
        op.create_index('idx_auto_approval_rules_active', 'tb_auto_approval_rules', ['is_active'])
        op.create_index('idx_auto_approval_rules_priority', 'tb_auto_approval_rules', ['priority'], postgresql_using='btree', postgresql_ops={'priority': 'DESC'})


def downgrade() -> None:
    """권한 요청 관리 테이블 삭제"""
    
    # 인덱스 삭제 (역순)
    op.drop_index('idx_auto_approval_rules_priority', table_name='tb_auto_approval_rules')
    op.drop_index('idx_auto_approval_rules_active', table_name='tb_auto_approval_rules')
    
    op.drop_index('idx_audit_log_request_id', table_name='tb_permission_audit_log')
    op.drop_index('idx_audit_log_created_at', table_name='tb_permission_audit_log')
    op.drop_index('idx_audit_log_actor', table_name='tb_permission_audit_log')
    op.drop_index('idx_audit_log_action_type', table_name='tb_permission_audit_log')
    
    op.drop_index('idx_permission_requests_approver', table_name='tb_permission_requests')
    op.drop_index('idx_permission_requests_requested_at', table_name='tb_permission_requests')
    op.drop_index('idx_permission_requests_status', table_name='tb_permission_requests')
    op.drop_index('idx_permission_requests_container', table_name='tb_permission_requests')
    op.drop_index('idx_permission_requests_requester', table_name='tb_permission_requests')
    
    # 테이블 삭제
    op.drop_table('tb_auto_approval_rules')
    op.drop_table('tb_permission_audit_log')
    op.drop_table('tb_permission_requests')
