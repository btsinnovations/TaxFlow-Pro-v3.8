"""merge local auth and v3.9 services heads

Revision ID: 377bb18e5f7c
Revises: c3a1f7e9d220, e8b7c1d5f3a2
Create Date: 2026-06-19 07:37:08.587117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '377bb18e5f7c'
down_revision: Union[str, Sequence[str], None] = ('c3a1f7e9d220', 'e8b7c1d5f3a2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
