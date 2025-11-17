"""merge multimodal clip vector migration

Revision ID: 6c3d0cf1653d
Revises: 20251017_001, c5aebed798ed
Create Date: 2025-10-17 03:45:19.301347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c3d0cf1653d'
down_revision: Union[str, Sequence[str], None] = ('20251017_001', 'c5aebed798ed')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
