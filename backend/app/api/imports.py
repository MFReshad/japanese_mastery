from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.importer import import_directory

router = APIRouter()


class ImportRequest(BaseModel):
    directory: str = "data/imports"
    dry_run: bool = True


@router.post("/import")
def run_import(payload: ImportRequest, db: Session = Depends(get_db)):
    return import_directory(db, Path(payload.directory), dry_run=payload.dry_run)
