"""Manual known/unknown marks for vocabulary and kanji example words."""

from alembic import op
import sqlalchemy as sa

revision = "0011_manual_knowledge"
down_revision = "0010_important_kanji_examples"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vocabulary_sources", sa.Column("knowledge_status", sa.String(10), nullable=True))
    op.add_column("kanji_examples", sa.Column("knowledge_status", sa.String(10), nullable=True))
    op.create_check_constraint("ck_vocab_source_knowledge", "vocabulary_sources", "knowledge_status IS NULL OR knowledge_status IN ('known', 'unknown')")
    op.create_check_constraint("ck_kanji_example_knowledge", "kanji_examples", "knowledge_status IS NULL OR knowledge_status IN ('known', 'unknown')")
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_practice_type", "practice_sessions", "practice_type in ('vocabulary', 'kanji', 'mixed', 'important_kanji_words', 'kanji_example_words')")


def downgrade():
    op.drop_constraint("ck_session_practice_type", "practice_sessions", type_="check")
    op.create_check_constraint("ck_session_practice_type", "practice_sessions", "practice_type in ('vocabulary', 'kanji', 'mixed', 'important_kanji_words')")
    op.drop_constraint("ck_kanji_example_knowledge", "kanji_examples", type_="check")
    op.drop_constraint("ck_vocab_source_knowledge", "vocabulary_sources", type_="check")
    op.drop_column("kanji_examples", "knowledge_status")
    op.drop_column("vocabulary_sources", "knowledge_status")
