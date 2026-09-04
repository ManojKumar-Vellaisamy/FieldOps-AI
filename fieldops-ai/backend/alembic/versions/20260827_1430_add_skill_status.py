"""add_skill_status

Revision ID: b94fe7123456
Revises: c86fd5199e45
Create Date: 2026-08-27 14:30:00.000000

"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b94fe7123456'
down_revision: str | None = 'c86fd5199e45'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('skills', sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'))
    op.add_column('skills', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))


def downgrade() -> None:
    op.drop_column('skills', 'updated_at')
    op.drop_column('skills', 'status')
