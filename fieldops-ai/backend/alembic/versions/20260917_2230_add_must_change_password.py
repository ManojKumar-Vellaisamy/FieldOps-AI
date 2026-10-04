"""add_must_change_password

Revision ID: e12ab3456789
Revises: d89fa1234567
Create Date: 2026-09-17 22:30:00.000000

"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e12ab3456789'
down_revision: str | None = 'd89fa1234567'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
