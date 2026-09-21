from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import ItemProgress


def calculate_status(attempts: int, correct_count: int, wrong_count: int, streak: int, last_result: str | None) -> tuple[str, float]:
    if attempts == 0:
        return "new", 0.0
    accuracy = correct_count / attempts
    if last_result == "wrong" or accuracy < 0.7:
        return "weak", round(accuracy, 4)
    if attempts >= 5 and accuracy >= 0.9 and streak >= 3:
        return "mastered", round(accuracy, 4)
    return "learning", round(accuracy, 4)


def get_or_create_progress(db: Session, item_type: str, item_id: int) -> ItemProgress:
    progress = db.scalar(select(ItemProgress).where(ItemProgress.item_type == item_type, ItemProgress.item_id == item_id))
    if progress:
        return progress
    progress = ItemProgress(item_type=item_type, item_id=item_id, attempts=0, correct_count=0,
                            wrong_count=0, current_correct_streak=0, mastery_score=0, status="new")
    db.add(progress)
    return progress


def record_answer(db: Session, item_type: str, item_id: int, result: str) -> ItemProgress:
    progress = get_or_create_progress(db, item_type, item_id)
    progress.attempts += 1
    progress.last_result = result
    progress.last_practiced_at = datetime.now(timezone.utc)
    if result == "correct":
        progress.correct_count += 1
        progress.current_correct_streak += 1
    else:
        progress.wrong_count += 1
        progress.current_correct_streak = 0
    progress.status, progress.mastery_score = calculate_status(
        progress.attempts,
        progress.correct_count,
        progress.wrong_count,
        progress.current_correct_streak,
        progress.last_result,
    )
    return progress
