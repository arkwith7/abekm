"""add_refresh_token_table

Revision ID: 9c2a4d9c1b2e
Revises: 3e19d6566abb
Create Date: 2025-08-18 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9c2a4d9c1b2e'
down_revision: Union[str, Sequence[str], None] = '3e19d6566abb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tb_refresh_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('tb_user.id', ondelete='CASCADE'), nullable=False, comment='사용자 ID'),
        sa.Column('emp_no', sa.String(length=20), nullable=False, comment='사번'),
        sa.Column('jti', sa.String(length=64), nullable=False, comment='JWT 토큰 ID (고유 식별자)'),
        sa.Column('token_hash', sa.String(length=255), nullable=False, comment='Refresh 토큰 해시값'),
        sa.Column('user_agent', sa.Text(), nullable=True, comment='사용자 에이전트'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='IP 주소'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='발급 시각'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='만료 시각'),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True, comment='로테이션(재발급) 시각'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True, comment='철회 시각'),
        sa.Column('revoke_reason', sa.Text(), nullable=True, comment='철회 사유'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='활성 상태'),
    )
    op.create_index('idx_tb_refresh_tokens_emp_no', 'tb_refresh_tokens', ['emp_no'])
    op.create_index('idx_tb_refresh_tokens_user_id', 'tb_refresh_tokens', ['user_id'])
    op.create_index('idx_tb_refresh_tokens_active', 'tb_refresh_tokens', ['is_active'])
    op.create_index('idx_tb_refresh_tokens_expires', 'tb_refresh_tokens', ['expires_at'])
    op.create_unique_constraint('uq_tb_refresh_tokens_jti', 'tb_refresh_tokens', ['jti'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_tb_refresh_tokens_jti', 'tb_refresh_tokens', type_='unique')
    op.drop_index('idx_tb_refresh_tokens_expires', table_name='tb_refresh_tokens')
    op.drop_index('idx_tb_refresh_tokens_active', table_name='tb_refresh_tokens')
    op.drop_index('idx_tb_refresh_tokens_user_id', table_name='tb_refresh_tokens')
    op.drop_index('idx_tb_refresh_tokens_emp_no', table_name='tb_refresh_tokens')
    op.drop_table('tb_refresh_tokens')
