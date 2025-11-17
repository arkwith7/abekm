"""merge_multimodal_and_processing_status

Revision ID: j1k2l3m4n5o6
Revises: a1b2c3d4e5f6, d4e5f6g7h8i9
Create Date: 2025-10-15 05:15:00.000000

Merge two branches:
- a1b2c3d4e5f6: add processing status columns
- d4e5f6g7h8i9: fix multimodal schema missing columns
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'd4e5f6g7h8i9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branches - no additional schema changes needed"""
    pass


def downgrade() -> None:
    """Rollback merge"""
    pass
