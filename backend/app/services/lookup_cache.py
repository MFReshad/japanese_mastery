from __future__ import annotations

from threading import RLock
from typing import Callable, TypeVar

from app.schemas.books import BookRead, ChapterRead

T = TypeVar("T")


class LookupCache:
    def __init__(self) -> None:
        self._lock = RLock()
        self._books: list[BookRead] | None = None
        self._chapters: list[ChapterRead] | None = None
        self._chapters_by_book: dict[int, list[ChapterRead]] = {}

    def get_books(self, loader: Callable[[], list[BookRead]]) -> list[BookRead]:
        with self._lock:
            if self._books is None:
                self._books = loader()
            return self._books

    def get_chapters(self, loader: Callable[[], list[ChapterRead]]) -> list[ChapterRead]:
        with self._lock:
            if self._chapters is None:
                self._chapters = loader()
            return self._chapters

    def get_chapters_by_book(self, book_id: int, loader: Callable[[], list[ChapterRead]]) -> list[ChapterRead]:
        with self._lock:
            if book_id not in self._chapters_by_book:
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

    def clear(self) -> None:
        with self._lock:
            self._books = None
            self._chapters = None
            self._chapters_by_book.clear()


lookup_cache = LookupCache()
