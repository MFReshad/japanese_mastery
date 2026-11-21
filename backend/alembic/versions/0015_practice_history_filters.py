"""store practice session filter snapshots

Revision ID: 0015_practice_history_filters
Revises: 0014_reset_example_rollup
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_practice_history_filters"
down_revision = "0014_reset_example_rollup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practice_sessions", sa.Column("filter_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("practice_sessions", "filter_snapshot")
