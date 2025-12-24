"""Add last_collection_result to patent_collection_settings

Revision ID: 20251224_001
Revises: 20251222_002
Create Date: 2025-12-24 06:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251224_001'
down_revision: Union[str, Sequence[str], None] = '20251222_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_collection_result column to tb_patent_collection_settings."""
    op.add_column(
        'tb_patent_collection_settings',
        sa.Column(
            'last_collection_result',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='마지막 수집 결과 (collected, errors)'
        )
    )


def downgrade() -> None:
    """Remove last_collection_result column from tb_patent_collection_settings."""
    op.drop_column('tb_patent_collection_settings', 'last_collection_result')
