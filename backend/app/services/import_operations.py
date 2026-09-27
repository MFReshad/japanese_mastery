from __future__ import annotations
from pathlib import Path

from app.core import get_settings
from app.errors import InvalidOperation
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.importer import import_directory
from app.services.lookup_cache import lookup_cache


class ImportRequest(BaseModel):
    directory: str = "data/imports"
    dry_run: bool = True


def run_import(payload: ImportRequest, db: Session = None):
    approved = Path(get_settings().import_directory).resolve()
    if Path(payload.directory).resolve() != approved:
        raise InvalidOperation("Import is restricted to the configured directory")
    result = import_directory(db, approved, dry_run=payload.dry_run)
    if not payload.dry_run:
        lookup_cache.clear()
    return result
