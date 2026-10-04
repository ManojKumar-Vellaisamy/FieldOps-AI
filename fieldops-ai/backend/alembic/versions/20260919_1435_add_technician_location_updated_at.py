"""add_technician_location_updated_at

Revision ID: f23bc4567890
Revises: e12ab3456789
Create Date: 2026-09-19 14:35:00.000000

"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f23bc4567890'
down_revision: str | None = 'e12ab3456789'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'technicians',
        sa.Column('location_updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('technicians', 'location_updated_at')
