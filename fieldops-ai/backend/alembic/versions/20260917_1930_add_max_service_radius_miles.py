"""add_max_service_radius_miles

Revision ID: d89fa1234567
Revises: c78fe9876543
Create Date: 2026-09-17 19:30:00.000000

"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd89fa1234567'
down_revision: str | None = 'c78fe9876543'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'system_settings',
        sa.Column('max_service_radius_miles', sa.Float(), nullable=True, server_default='100.0'),
    )


def downgrade() -> None:
    op.drop_column('system_settings', 'max_service_radius_miles')
