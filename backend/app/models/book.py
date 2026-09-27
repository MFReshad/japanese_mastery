from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Book(TimestampMixin, Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(80), unique=True)
    edition: Mapped[Optional[str]] = mapped_column(String(120))
    jlpt_level: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class Chapter(TimestampMixin, Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255))
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    part: Mapped[Optional[object]] = mapped_column(JSON)
    title_as_printed: Mapped[Optional[str]] = mapped_column(String(255))
    has_vocabulary: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_kanji: Mapped[Optional[bool]] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    book: Mapped[Book] = relationship(back_populates="chapters")


# Match the existing Alembic schema; do not invent additional indexes.
from sqlalchemy import Index, UniqueConstraint

Book.__table__.append_constraint(
    UniqueConstraint("source_id", name="uq_books_source_id")
)
Index("ix_books_source_id", Book.__table__.c["source_id"], unique=False)
Chapter.__table__.append_constraint(
    UniqueConstraint("source_id", name="uq_chapters_source_id")
)
Index(
    "ix_chapters_book_order",
    Chapter.__table__.c["book_id"],
    Chapter.__table__.c["sort_order"],
    Chapter.__table__.c["chapter_number"],
    unique=False,
)
Index("ix_chapters_source_id", Chapter.__table__.c["source_id"], unique=False)
