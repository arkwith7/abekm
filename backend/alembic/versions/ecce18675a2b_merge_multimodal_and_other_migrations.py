"""merge multimodal and other migrations

Revision ID: ecce18675a2b
Revises: 20251015_074, 46680deb9c2a
Create Date: 2025-10-15 07:44:35.223397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecce18675a2b'
down_revision: Union[str, Sequence[str], None] = ('20251015_074', '46680deb9c2a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
