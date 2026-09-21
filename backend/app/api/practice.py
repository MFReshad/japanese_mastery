from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.practice import AnswerResult, PracticeAnswerRequest, PracticeQuestion, PracticeRevealRequest, PracticeRevealResponse, PracticeStartRequest, PracticeStartResponse
from app.services.practice import answer_practice, reveal_question, start_practice

router = APIRouter()


@router.post("/practice/start", response_model=PracticeStartResponse)
def start(payload: PracticeStartRequest, db: Session = Depends(get_db)):
    session, questions = start_practice(db, payload)
    return PracticeStartResponse(session_id=session.id, questions=[
        PracticeQuestion(question_id=question.id, item_type=question.item_type,
                         question_type=question.question_type, prompt=question.prompt)
        for question in questions
    ])


@router.post("/practice/questions/{question_id}/reveal", response_model=PracticeRevealResponse)
def reveal(question_id: int, payload: PracticeRevealRequest, db: Session = Depends(get_db)):
    question = reveal_question(db, payload.session_id, question_id)
    return PracticeRevealResponse(answer_primary=question.answer_primary, answer_secondary=question.answer_secondary, context=question.reveal_context)


@router.post("/practice/answer", response_model=AnswerResult)
def answer(payload: PracticeAnswerRequest, db: Session = Depends(get_db)):
    if payload.result not in ("correct", "wrong"):
        raise HTTPException(400, "Result must be correct or wrong")
    progress, answered_at = answer_practice(
        db,
        payload.session_id,
        payload.question_id,
        payload.result,
        payload.note,
    )
    return AnswerResult(status=progress.status, mastery_score=progress.mastery_score, attempts=progress.attempts, answered_at=answered_at)
