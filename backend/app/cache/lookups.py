from __future__ import annotations

from threading import RLock
from time import monotonic
from typing import Callable, TypeVar

from app.schemas.books import BookRead, ChapterRead

T = TypeVar("T")


class LookupCache:
    def __init__(self, ttl_seconds: float = 30) -> None:
        self.ttl_seconds = ttl_seconds
        self._expires = {}
        self._values = {}
        self._lock = RLock()
        self._books: list[BookRead] | None = None
        self._chapters: list[ChapterRead] | None = None
        self._chapters_by_book: dict[int, list[ChapterRead]] = {}

    def get_books(self, loader: Callable[[], list[BookRead]]) -> list[BookRead]:
        with self._lock:
            if self._books is None or monotonic() >= self._expires.get("books", 0):
                self._expires["books"] = monotonic() + self.ttl_seconds
                self._books = loader()
            return self._books

    def get_chapters(
        self, loader: Callable[[], list[ChapterRead]]
    ) -> list[ChapterRead]:
        with self._lock:
            if self._chapters is None or monotonic() >= self._expires.get(
                "chapters", 0
            ):
                self._expires["chapters"] = monotonic() + self.ttl_seconds
                self._chapters = loader()
            return self._chapters

    def get_chapters_by_book(
        self, book_id: int, loader: Callable[[], list[ChapterRead]]
    ) -> list[ChapterRead]:
        with self._lock:
            if (
                book_id not in self._chapters_by_book
                or monotonic() >= self._expires.get(book_id, 0)
            ):
                self._expires[book_id] = monotonic() + self.ttl_seconds
                self._chapters_by_book[book_id] = loader()
            return self._chapters_by_book[book_id]

    def invalidate_books(self) -> None:
        with self._lock:
            self._books = None

    def invalidate_chapters(self, book_id: int | None = None) -> None:
        with self._lock:
            self._chapters = None
            if book_id is None:
                self._chapters_by_book.clear()
            else:
                self._chapters_by_book.pop(book_id, None)

    def get_value(self, key, loader, ttl_seconds=3):
        with self._lock:
            entry = self._values.get(key)
            if entry is None or entry[0] <= monotonic():
                entry = (monotonic() + ttl_seconds, loader())
                self._values[key] = entry
            return entry[1]

    def invalidate_progress(self):
        with self._lock:
            self._values.clear()

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._books = None
            self._chapters = None
            self._chapters_by_book.clear()


lookup_cache = LookupCache()
