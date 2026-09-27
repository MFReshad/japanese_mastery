from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import Field, model_validator

from app.schemas.common import OrmModel


class PracticeStartRequest(OrmModel):
    practice_type: Literal["vocabulary", "kanji", "mixed"] = "mixed"
    mode: Literal[
        "random",
        "weak",
        "wrong",
        "never_practiced",
        "mastery_review",
        "starred",
        "starred_priority",
    ] = "random"
    book_ids: list[int] = []
    chapter_ids: list[int] = []
    source_entry_ids: list[int] = []
    parts: list[int | str] = []
    order_start: int | None = None
    order_end: int | None = None
    question_count: int | None = Field(default=10, ge=1, le=2000)

    @model_validator(mode="after")
    def validate_ranges(self):
        if any(
            value <= 0
            for value in self.book_ids + self.chapter_ids + self.source_entry_ids
        ):
            raise ValueError("IDs must be positive")
        if any(
            value is not None and value < 0
            for value in (self.order_start, self.order_end)
        ):
            raise ValueError("Order must be nonnegative")
        if (
            self.order_start is not None
            and self.order_end is not None
            and self.order_start > self.order_end
        ):
            raise ValueError("Order start must not exceed order end")
        return self


class PracticeQuestion(OrmModel):
    question_id: int
    item_type: str
    question_type: str
    prompt: str


class PracticeStartResponse(OrmModel):
    session_id: int
    questions: list[PracticeQuestion]


class PracticeAnswerRequest(OrmModel):
    session_id: int
    question_id: int
    result: Literal["correct", "wrong"]
    note: str | None = Field(default=None, max_length=2000)


class PracticeRevealRequest(OrmModel):
    session_id: int


class PracticeRevealResponse(OrmModel):
    answer_primary: str
    answer_secondary: str | None = None
    context: dict | None = None


class ProgressRead(OrmModel):
    item_type: str
    total: int
    new: int
    learning: int
    weak: int
    mastered: int


class CoverageChapter(OrmModel):
    book_id: int
    book_title: str
    chapter_id: int
    chapter_title: str
    chapter_number: int
    vocabulary_mastered_percent: float
    kanji_mastered_percent: float


class AnswerResult(OrmModel):
    status: str
    mastery_score: float
    attempts: int
    answered_at: datetime
