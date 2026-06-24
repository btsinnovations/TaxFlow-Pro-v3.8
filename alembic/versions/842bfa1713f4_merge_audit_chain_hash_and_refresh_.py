"""merge audit chain hash and refresh token heads

Revision ID: 842bfa1713f4
Revises: c4062c0c95ff, f2a9b8c1d4e5
Create Date: 2026-06-21 10:33:19.242624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '842bfa1713f4'
down_revision: Union[str, Sequence[str], None] = ('c4062c0c95ff', 'f2a9b8c1d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
