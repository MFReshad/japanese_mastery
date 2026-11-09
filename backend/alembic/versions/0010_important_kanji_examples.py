"""Mark individual kanji examples as important."""

from alembic import op
import sqlalchemy as sa

revision = "0010_important_kanji_examples"
down_revision = "0009_book_active"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "kanji_examples",
        sa.Column("is_important", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.alter_column(
        "practice_sessions",
        "practice_type",
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_session_practice_type",
        "practice_sessions",
        "practice_type in ('vocabulary', 'kanji', 'mixed', 'important_kanji_words')",
    )


def downgrade():
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_practice_type",
        "practice_sessions",
        "practice_type in ('vocabulary', 'kanji', 'mixed')",
    )
    op.alter_column(
        "practice_sessions",
        "practice_type",
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=False,
    )
    op.drop_column("kanji_examples", "is_important")
