from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.practice import (
    AnswerResult,
    PracticeAnswerRequest,
    PracticeQuestion,
    PracticeRevealRequest,
    PracticeRevealResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    PracticeHistoryDetail,
    PracticeHistoryPage,
)
from app.services.practice import PracticeService
from app.services.practice.history import history_detail, list_history

router = APIRouter()


@router.get("/practice/history", response_model=PracticeHistoryPage)
def history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return list_history(db, limit, offset)


@router.get("/practice/history/{session_id}", response_model=PracticeHistoryDetail)
def history_session(session_id: int, db: Session = Depends(get_db)):
    return history_detail(db, session_id)


@router.post("/practice/start", response_model=PracticeStartResponse)
def start(payload: PracticeStartRequest, db: Session = Depends(get_db)):
    session, questions = PracticeService.start(db, payload)
    return PracticeStartResponse(
        session_id=session.id,
        questions=[
            PracticeQuestion(
                question_id=question.id,
                item_type=question.item_type,
                question_type=question.question_type,
                prompt=question.prompt,
            )
            for question in questions
        ],
    )


@router.post(
    "/practice/questions/{question_id}/reveal", response_model=PracticeRevealResponse
)
def reveal(
    question_id: int, payload: PracticeRevealRequest, db: Session = Depends(get_db)
):
    question = PracticeService.reveal(db, payload.session_id, question_id)
    return PracticeRevealResponse(
        answer_primary=question.answer_primary,
        answer_secondary=question.answer_secondary,
        context=question.reveal_context,
    )


@router.post("/practice/answer", response_model=AnswerResult)
def answer(payload: PracticeAnswerRequest, db: Session = Depends(get_db)):
    if payload.result not in ("correct", "wrong"):
        raise HTTPException(400, "Result must be correct or wrong")
    progress, answered_at = PracticeService.answer(
        db,
        payload.session_id,
        payload.question_id,
        payload.result,
        payload.note,
    )
    return AnswerResult(
        status=progress.status,
        mastery_score=progress.mastery_score,
        attempts=progress.attempts,
        answered_at=answered_at,
    )


@router.get("/practice/sessions/{session_id}")
def resume(session_id: int, db: Session = Depends(get_db)):
    return PracticeService.resume(db, session_id)
