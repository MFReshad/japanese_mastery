"""Add active/inactive state for book management."""

from alembic import op
import sqlalchemy as sa

revision = "0009_book_active"
down_revision = "0008_stabilization"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "books",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade():
    op.drop_column("books", "is_active")
