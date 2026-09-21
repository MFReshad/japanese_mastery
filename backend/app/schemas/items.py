from __future__ import annotations

from app.schemas.common import OrmModel, Timestamped


class VocabularySourceCreate(OrmModel):
    book_id: int
    chapter_id: int | None = None
    item_order: int = 0
    expression: str
    reading: str
    meaning: str
    notes: str | None = None
    source_file: str | None = None
    source_page: str | None = None
    source_section: str | None = None


class VocabularySourceUpdate(OrmModel):
    chapter_id: int | None = None
    item_order: int | None = None
    expression_as_printed: str | None = None
    reading_as_printed: str | None = None
    meaning_as_printed: str | None = None
    notes: str | None = None
    source_page: str | None = None
    source_section: str | None = None


class VocabularySourceRead(Timestamped):
    id: int
    source_id: str | None = None
    vocabulary_id: int
    book_id: int
    chapter_id: int | None
    item_order: int
    original_item_order: int | None = None
    manually_added: bool = False
    manually_reordered: bool = False
    expression_as_printed: str
    reading_as_printed: str
    meaning_as_printed: str
    notes: str | None
    source_file: str | None
    source_page: str | None
    source_section: str | None
    expression: str
    reading: str
    status: str = "new"


class KanjiExampleIn(OrmModel):
    word: str
    reading: str
    meaning: str
    sort_order: int = 0


class KanjiSourceCreate(OrmModel):
    book_id: int
    chapter_id: int | None = None
    item_order: int = 0
    character: str
    meaning: str
    onyomi: list[str] = []
    kunyomi: list[str] = []
    examples: list[KanjiExampleIn] = []
    notes: str | None = None
    source_file: str | None = None
    source_page: str | None = None
    source_section: str | None = None


class KanjiSourceUpdate(OrmModel):
    chapter_id: int | None = None
    item_order: int | None = None
    meaning_as_printed: str | None = None
    onyomi: list[str] | None = None
    kunyomi: list[str] | None = None
    notes: str | None = None
    uncertain: bool | None = None
    examples: list[KanjiExampleIn] | None = None


class KanjiSourceRead(Timestamped):
    id: int
    source_id: str | None = None
    kanji_id: int
    book_id: int
    chapter_id: int | None
    item_order: int
    character: str
    meaning_as_printed: str
    onyomi: list[str]
    kunyomi: list[str]
    notes: str | None
    uncertain: bool | None = None
    source_file: str | None
    source_page: str | None
    source_section: str | None
    examples: list[KanjiExampleIn] = []
    status: str = "new"
