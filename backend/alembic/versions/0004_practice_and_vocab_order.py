"""Practice reveal context, wrong notes, and editable vocabulary order."""

from alembic import op
import sqlalchemy as sa

revision = "0004_practice_and_vocab_order"
down_revision = "0003_practice_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("practice_questions", sa.Column("reveal_context", sa.JSON(), nullable=True))
    op.add_column("practice_answers", sa.Column("wrong_note", sa.Text(), nullable=True))
    op.add_column("vocabulary_sources", sa.Column("original_item_order", sa.Integer(), nullable=True))
    op.add_column("vocabulary_sources", sa.Column("manually_added", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("vocabulary_sources", sa.Column("manually_reordered", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE vocabulary_sources SET original_item_order = item_order WHERE source_id IS NOT NULL")
    op.execute("UPDATE vocabulary_sources SET manually_added = true WHERE source_id IS NULL")


def downgrade():
    op.drop_column("vocabulary_sources", "manually_reordered")
    op.drop_column("vocabulary_sources", "manually_added")
    op.drop_column("vocabulary_sources", "original_item_order")
    op.drop_column("practice_answers", "wrong_note")
    op.drop_column("practice_questions", "reveal_context")
