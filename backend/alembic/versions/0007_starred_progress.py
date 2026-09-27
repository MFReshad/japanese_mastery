"""Add starred progress preference."""

from alembic import op
import sqlalchemy as sa

revision = "0007_starred_progress"
down_revision = "0006_repair_kanji_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("item_progress", sa.Column("is_starred", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.alter_column("item_progress", "is_starred", server_default=None)
    op.drop_constraint("ck_session_mode", "practice_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_mode",
        "practice_sessions",
        "mode in ('random', 'weak', 'wrong', 'never_practiced', 'mastery_review', 'starred', 'starred_priority')",
    )


def downgrade():
    op.drop_constraint("ck_session_mode", "practice_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_mode",
        "practice_sessions",
        "mode in ('random', 'weak', 'wrong', 'never_practiced', 'mastery_review')",
    )
    op.drop_column("item_progress", "is_starred")
