"""preserve source dataset identifiers and audit fields

Revision ID: 0002_dataset_compatibility
Revises: 0001_initial
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_dataset_compatibility"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("books") as batch:
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.add_column(sa.Column("note", sa.Text()))
        batch.alter_column("short_name", existing_type=sa.String(80), nullable=True)
        batch.create_unique_constraint("uq_books_source_id", ["source_id"])
        batch.create_index("ix_books_source_id", ["source_id"])

    with op.batch_alter_table("chapters") as batch:
        batch.drop_constraint("uq_chapter_book_number", type_="unique")
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.add_column(sa.Column("part", sa.JSON()))
        batch.add_column(sa.Column("title_as_printed", sa.String(255)))
        batch.add_column(sa.Column("has_vocabulary", sa.Boolean()))
        batch.add_column(sa.Column("has_kanji", sa.Boolean()))
        batch.create_unique_constraint("uq_chapters_source_id", ["source_id"])
        batch.create_index("ix_chapters_source_id", ["source_id"])

    with op.batch_alter_table("vocabulary") as batch:
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.create_unique_constraint("uq_vocabulary_source_id", ["source_id"])
        batch.create_index("ix_vocabulary_source_id", ["source_id"])

    with op.batch_alter_table("kanji") as batch:
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.create_unique_constraint("uq_kanji_source_id", ["source_id"])
        batch.create_index("ix_kanji_source_id", ["source_id"])

    with op.batch_alter_table("vocabulary_sources") as batch:
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.add_column(sa.Column("book", sa.String(255)))
        batch.add_column(sa.Column("chapter", sa.JSON()))
        batch.add_column(sa.Column("meanings_as_printed", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("source_line", sa.Integer()))
        batch.add_column(sa.Column("source_page_as_imported", sa.JSON()))
        batch.add_column(sa.Column("repaired", sa.Boolean()))
        batch.add_column(sa.Column("repair_note", sa.Text()))
        batch.add_column(sa.Column("raw_line", sa.Text()))
        batch.create_unique_constraint("uq_vocabulary_sources_source_id", ["source_id"])
        batch.create_index("ix_vocabulary_sources_source_id", ["source_id"])

    with op.batch_alter_table("kanji_sources") as batch:
        batch.add_column(sa.Column("source_id", sa.String(255)))
        batch.add_column(sa.Column("meanings_as_printed", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.alter_column("onyomi", new_column_name="onyomi_as_printed", existing_type=sa.JSON(), nullable=False)
        batch.alter_column("kunyomi", new_column_name="kunyomi_as_printed", existing_type=sa.JSON(), nullable=False)
        batch.add_column(sa.Column("book", sa.String(255)))
        batch.add_column(sa.Column("chapter", sa.JSON()))
        batch.add_column(sa.Column("part", sa.JSON()))
        batch.add_column(sa.Column("entry_number_as_printed", sa.Integer()))
        batch.add_column(sa.Column("chapter_title_as_printed", sa.String(255)))
        batch.add_column(sa.Column("stroke_count_as_printed", sa.Integer()))
        batch.add_column(sa.Column("source_book_page", sa.Integer()))
        batch.add_column(sa.Column("source_page_as_imported", sa.JSON()))
        batch.add_column(sa.Column("chapter_inferred", sa.Boolean()))
        batch.add_column(sa.Column("uncertain", sa.Boolean()))
        batch.add_column(sa.Column("extraction_batch", sa.String(255)))
        batch.create_unique_constraint("uq_kanji_sources_source_id", ["source_id"])
        batch.create_index("ix_kanji_sources_source_id", ["source_id"])


def downgrade() -> None:
    with op.batch_alter_table("kanji_sources") as batch:
        batch.drop_index("ix_kanji_sources_source_id")
        batch.drop_constraint("uq_kanji_sources_source_id", type_="unique")
        for name in ("extraction_batch", "uncertain", "chapter_inferred", "source_page_as_imported", "source_book_page", "stroke_count_as_printed",
                     "chapter_title_as_printed", "entry_number_as_printed", "part", "chapter", "book", "meanings_as_printed", "source_id"):
            batch.drop_column(name)
        batch.alter_column("onyomi_as_printed", new_column_name="onyomi", existing_type=sa.JSON(), nullable=False)
        batch.alter_column("kunyomi_as_printed", new_column_name="kunyomi", existing_type=sa.JSON(), nullable=False)
    with op.batch_alter_table("vocabulary_sources") as batch:
        batch.drop_index("ix_vocabulary_sources_source_id")
        batch.drop_constraint("uq_vocabulary_sources_source_id", type_="unique")
        for name in ("raw_line", "repair_note", "repaired", "source_page_as_imported", "source_line", "meanings_as_printed", "chapter", "book", "source_id"):
            batch.drop_column(name)
    for table in ("kanji", "vocabulary"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_source_id")
            batch.drop_constraint(f"uq_{table}_source_id", type_="unique")
            batch.drop_column("source_id")
    with op.batch_alter_table("chapters") as batch:
        batch.drop_index("ix_chapters_source_id")
        batch.drop_constraint("uq_chapters_source_id", type_="unique")
        for name in ("has_kanji", "has_vocabulary", "title_as_printed", "part", "source_id"):
            batch.drop_column(name)
        batch.create_unique_constraint("uq_chapter_book_number", ["book_id", "chapter_number"])
    with op.batch_alter_table("books") as batch:
        batch.drop_index("ix_books_source_id")
        batch.drop_constraint("uq_books_source_id", type_="unique")
        batch.drop_column("note")
        batch.drop_column("source_id")
        batch.alter_column("short_name", existing_type=sa.String(80), nullable=False)
