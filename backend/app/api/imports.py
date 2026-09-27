from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services import import_operations as operations
from app.services.import_operations import ImportRequest

router = APIRouter()


@router.post("/import")
def run_import(payload: ImportRequest, db: Session = Depends(get_db)):
    return operations.run_import(payload, db)
