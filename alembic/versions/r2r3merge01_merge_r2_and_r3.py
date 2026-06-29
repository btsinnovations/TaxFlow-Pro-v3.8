"""merge R2 and R3

Revision ID: r2r3merge01
Revises: r2periodclose01, r3reconlock01
Create Date: 2026-06-29 03:58:56.982402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r2r3merge01'
down_revision: Union[str, Sequence[str], None] = ('r2periodclose01', 'r3reconlock01')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
