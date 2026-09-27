from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock

from app.models.practice import PracticeQuestion


@dataclass
class CachedQuestion:
    session_id: int
    question_id: int
    item_type: str
    item_id: int
    source_entry_id: int
    question_type: str
    answer_primary: str
    answer_secondary: str | None
    reveal_context: dict | None
    last_access: float


class PracticeSessionCache:
    def __init__(self, ttl_seconds: int = 24 * 60 * 60, max_questions: int = 10_000):
        self._lock = RLock()
        self._questions: dict[tuple[int, int], CachedQuestion] = {}
        self._ttl_seconds = ttl_seconds
        self._max_questions = max_questions

    def store(self, questions: list[PracticeQuestion]) -> None:
        with self._lock:
            now = time.monotonic()
            for question in questions:
                self._questions[(question.session_id, question.id)] = CachedQuestion(
                    session_id=question.session_id,
                    question_id=question.id,
                    item_type=question.item_type,
                    item_id=question.item_id,
                    source_entry_id=question.source_entry_id,
                    question_type=question.question_type,
                    answer_primary=question.answer_primary,
                    answer_secondary=question.answer_secondary,
                    reveal_context=question.reveal_context,
                    last_access=now,
                )
            if len(self._questions) > self._max_questions:
                expired = [
                    key
                    for key, value in self._questions.items()
                    if now - value.last_access > self._ttl_seconds
                ]
                for key in expired:
                    del self._questions[key]
                excess = len(self._questions) - self._max_questions
                if excess > 0:
                    oldest = sorted(
                        self._questions,
                        key=lambda key: self._questions[key].last_access,
                    )
                    for key in oldest[:excess]:
                        del self._questions[key]

    def get(self, session_id: int, question_id: int) -> CachedQuestion | None:
        with self._lock:
            key = (session_id, question_id)
            question = self._questions.get(key)
            if (
                question
                and time.monotonic() - question.last_access <= self._ttl_seconds
            ):
                question.last_access = time.monotonic()
                return question
            self._questions.pop(key, None)
            return None

    def clear(self) -> None:
        with self._lock:
            self._questions.clear()


practice_session_cache = PracticeSessionCache()
