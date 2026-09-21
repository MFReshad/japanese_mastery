"""Indexes for chapter reading, practice filtering, and progress summaries."""

from alembic import op

revision = "0005_read_path_indexes"
down_revision = "0004_practice_and_vocab_order"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_chapters_book_order", "chapters", ["book_id", "sort_order", "chapter_number"])
    op.create_index("ix_vocab_sources_book_chapter_order", "vocabulary_sources", ["book_id", "chapter_id", "item_order", "id"])
    op.create_index("ix_vocab_sources_chapter_order", "vocabulary_sources", ["chapter_id", "item_order", "id"])
    op.create_index("ix_kanji_sources_book_chapter_order", "kanji_sources", ["book_id", "chapter_id", "item_order", "id"])
    op.create_index("ix_kanji_sources_chapter_order", "kanji_sources", ["chapter_id", "item_order", "id"])
    op.create_index("ix_item_progress_type_item", "item_progress", ["item_type", "item_id"])
    op.create_index("ix_item_progress_type_status", "item_progress", ["item_type", "status"])
    op.create_index("ix_kanji_examples_source_order", "kanji_examples", ["kanji_source_id", "sort_order"])
    op.create_index("ix_practice_answers_item", "practice_answers", ["item_type", "item_id"])


def downgrade():
    op.drop_index("ix_practice_answers_item", table_name="practice_answers")
    op.drop_index("ix_kanji_examples_source_order", table_name="kanji_examples")
    op.drop_index("ix_item_progress_type_status", table_name="item_progress")
    op.drop_index("ix_item_progress_type_item", table_name="item_progress")
    op.drop_index("ix_kanji_sources_chapter_order", table_name="kanji_sources")
    op.drop_index("ix_kanji_sources_book_chapter_order", table_name="kanji_sources")
    op.drop_index("ix_vocab_sources_chapter_order", table_name="vocabulary_sources")
    op.drop_index("ix_vocab_sources_book_chapter_order", table_name="vocabulary_sources")
    op.drop_index("ix_chapters_book_order", table_name="chapters")
