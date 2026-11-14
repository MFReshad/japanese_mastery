"""Add explicit vocabulary practice directions."""

from alembic import op


revision = "0012_vocab_directions"
down_revision = "0011_manual_knowledge"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_practice_type",
        "practice_sessions",
        "practice_type in ('vocabulary', 'vocab_word_to_meaning', 'vocab_meaning_to_word', 'kanji', 'mixed', 'important_kanji_words', 'kanji_example_words')",
    )


def downgrade():
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_practice_type",
        "practice_sessions",
        "practice_type in ('vocabulary', 'kanji', 'mixed', 'important_kanji_words', 'kanji_example_words')",
    )
