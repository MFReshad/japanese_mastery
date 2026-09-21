from __future__ import annotations

from app.schemas.common import OrmModel, Timestamped


class BookBase(OrmModel):
    title: str
    short_name: str | None = None
    edition: str | None = None
    jlpt_level: str | None = None
    description: str | None = None
    is_demo: bool = False


class BookCreate(BookBase):
    pass


class BookUpdate(OrmModel):
    title: str | None = None
    short_name: str | None = None
    edition: str | None = None
    jlpt_level: str | None = None
    description: str | None = None


class BookRead(BookBase, Timestamped):
    id: int
    source_id: str | None = None
    vocabulary_count: int = 0
    kanji_count: int = 0


class ChapterBase(OrmModel):
    book_id: int
    chapter_number: int
    title: str
    sort_order: int = 0


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(OrmModel):
    book_id: int | None = None
    chapter_number: int | None = None
    title: str | None = None
    sort_order: int | None = None


class ChapterRead(ChapterBase, Timestamped):
    id: int
    source_id: str | None = None
    part: int | str | None = None
