from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Vocabulary(TimestampMixin, Base):
    __tablename__ = "vocabulary"
    __table_args__ = (UniqueConstraint("normalized_expression", "normalized_reading", name="uq_vocab_normalized"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    expression: Mapped[str] = mapped_column(String(255), nullable=False)
    reading: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_expression: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_reading: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    sources: Mapped[list["VocabularySource"]] = relationship(back_populates="vocabulary", cascade="all, delete-orphan")


class VocabularySource(TimestampMixin, Base):
    __tablename__ = "vocabulary_sources"
    __table_args__ = (
        UniqueConstraint("vocabulary_id", "book_id", "chapter_id", "item_order", name="uq_vocab_source_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    vocabulary_id: Mapped[int] = mapped_column(ForeignKey("vocabulary.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    item_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    original_item_order: Mapped[Optional[int]] = mapped_column(Integer)
    manually_added: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manually_reordered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expression_as_printed: Mapped[str] = mapped_column(String(255), nullable=False)
    reading_as_printed: Mapped[str] = mapped_column(String(255), nullable=False)
    meaning_as_printed: Mapped[str] = mapped_column(Text, nullable=False)
    book_as_printed: Mapped[Optional[str]] = mapped_column("book", String(255))
    chapter_as_printed: Mapped[Optional[Any]] = mapped_column("chapter", JSON)
    meanings_as_printed: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    source_page: Mapped[Optional[str]] = mapped_column(String(80))
    source_page_as_imported: Mapped[Optional[Any]] = mapped_column(JSON)
    source_line: Mapped[Optional[int]] = mapped_column(Integer)
    source_section: Mapped[Optional[str]] = mapped_column(String(120))
    repaired: Mapped[Optional[bool]] = mapped_column(Boolean)
    repair_note: Mapped[Optional[str]] = mapped_column(Text)
    raw_line: Mapped[Optional[str]] = mapped_column(Text)

    vocabulary: Mapped[Vocabulary] = relationship(back_populates="sources")


class Kanji(TimestampMixin, Base):
    __tablename__ = "kanji"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    character: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)

    sources: Mapped[list["KanjiSource"]] = relationship(back_populates="kanji", cascade="all, delete-orphan")


class KanjiSource(TimestampMixin, Base):
    __tablename__ = "kanji_sources"
    __table_args__ = (UniqueConstraint("kanji_id", "book_id", "chapter_id", "item_order", name="uq_kanji_source_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    kanji_id: Mapped[int] = mapped_column(ForeignKey("kanji.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    item_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meaning_as_printed: Mapped[str] = mapped_column(Text, nullable=False)
    meanings_as_printed: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    onyomi_as_printed: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    kunyomi_as_printed: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    book_as_printed: Mapped[Optional[str]] = mapped_column("book", String(255))
    chapter_as_printed: Mapped[Optional[Any]] = mapped_column("chapter", JSON)
    part: Mapped[Optional[Any]] = mapped_column(JSON)
    entry_number_as_printed: Mapped[Optional[int]] = mapped_column(Integer)
    chapter_title_as_printed: Mapped[Optional[str]] = mapped_column(String(255))
    stroke_count_as_printed: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    source_page: Mapped[Optional[str]] = mapped_column(String(80))
    source_page_as_imported: Mapped[Optional[Any]] = mapped_column(JSON)
    source_book_page: Mapped[Optional[int]] = mapped_column(Integer)
    source_section: Mapped[Optional[str]] = mapped_column(String(120))
    chapter_inferred: Mapped[Optional[bool]] = mapped_column(Boolean)
    uncertain: Mapped[Optional[bool]] = mapped_column(Boolean)
    extraction_batch: Mapped[Optional[str]] = mapped_column(String(255))

    @property
    def onyomi(self) -> list[str]:
        return self.onyomi_as_printed

    @onyomi.setter
    def onyomi(self, value: list[str]) -> None:
        self.onyomi_as_printed = value

    @property
    def kunyomi(self) -> list[str]:
        return self.kunyomi_as_printed

    @kunyomi.setter
    def kunyomi(self, value: list[str]) -> None:
        self.kunyomi_as_printed = value

    kanji: Mapped[Kanji] = relationship(back_populates="sources")
    examples: Mapped[list["KanjiExample"]] = relationship(back_populates="kanji_source", cascade="all, delete-orphan")


class KanjiExample(Base):
    __tablename__ = "kanji_examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    kanji_source_id: Mapped[int] = mapped_column(ForeignKey("kanji_sources.id", ondelete="CASCADE"), nullable=False)
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    reading: Mapped[str] = mapped_column(String(255), nullable=False)
    meaning: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    kanji_source: Mapped[KanjiSource] = relationship(back_populates="examples")
