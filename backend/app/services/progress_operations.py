from __future__ import annotations
from app.services.lookup_cache import lookup_cache
from app.repositories import progress as queries

from sqlalchemy.orm import Session


def progress(db: Session = None):
    return lookup_cache.get_value("progress", lambda: queries.progress(db))


def book_coverage(db: Session = None):
    return lookup_cache.get_value("coverage", lambda: queries.book_coverage(db))
