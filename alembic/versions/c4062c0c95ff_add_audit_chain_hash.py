"""add audit chain_hash

Revision ID: c4062c0c95ff
Revises: 2227f9254a8b
Create Date: 2026-06-21 05:00:29.189590

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa

from backend.audit.audit_trail import _compute_chain_hash, _normalize_dt
from backend.utils.redaction import redact_pii_in_json

# revision identifiers, used by Alembic.
revision: str = 'c4062c0c95ff'
down_revision: Union[str, Sequence[str], None] = '2227f9254a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _redact_for_hash(details_raw):
    if details_raw is None:
        return {}
    if isinstance(details_raw, str):
        try:
            parsed = json.loads(details_raw)
        except (json.JSONDecodeError, TypeError):
            parsed = {"_raw": str(details_raw)}
    else:
        parsed = details_raw
    return redact_pii_in_json(parsed)


def upgrade() -> None:
    """Add chain_hash column and deterministically backfill existing rows."""
    conn = op.get_bind()
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    except Exception:
        tables = set()
    if 'audit_entries' not in tables:
        return
    op.add_column(
        'audit_entries',
        sa.Column('chain_hash', sa.String(length=64), nullable=True)
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, occurred_at, action, resource_type, resource_id, actor_id, details "
            "FROM audit_entries ORDER BY id ASC"
        )
    ).fetchall()

    previous_hash = "0" * 64
    for row in rows:
        details = _redact_for_hash(row.details)
        chain_hash = _compute_chain_hash(
            previous_chain_hash=previous_hash,
            entry_id=row.id,
            occurred_at=row.occurred_at,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            user_id=row.actor_id,
            tenant_id=None,
            details=details,
        )
        connection.execute(
            sa.text("UPDATE audit_entries SET chain_hash = :chain_hash WHERE id = :id"),
            {"chain_hash": chain_hash, "id": row.id},
        )
        previous_hash = chain_hash


def downgrade() -> None:
    """Remove the chain_hash column."""
    conn = op.get_bind()
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    except Exception:
        tables = set()
    if 'audit_entries' not in tables:
        return
    try:
        with op.batch_alter_table('audit_entries', schema=None) as batch_op:
            batch_op.drop_column('chain_hash')
    except Exception:
        pass
