from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDraft:
    item_type: str
    item_id: int
    source_entry_id: int
    question_type: str
    prompt: str
    answer_primary: str
    answer_secondary: str | None
    reveal_context: dict | None = None
