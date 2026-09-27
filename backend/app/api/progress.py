from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.practice import CoverageChapter, ProgressRead
from app.services import progress_operations as operations

router = APIRouter()


@router.get("/progress", response_model=list[ProgressRead])
def progress(db: Session = Depends(get_db)):
    return operations.progress(db)


@router.get("/progress/books", response_model=list[CoverageChapter])
def book_coverage(db: Session = Depends(get_db)):
    return operations.book_coverage(db)
