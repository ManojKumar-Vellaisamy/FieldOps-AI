"""add_job_description

Revision ID: c78fe9876543
Revises: b94fe7123456
Create Date: 2026-08-27 15:00:00.000000

"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c78fe9876543'
down_revision: str | None = 'b94fe7123456'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'description')
