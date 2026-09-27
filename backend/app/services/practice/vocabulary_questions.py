from __future__ import annotations
import random
import re
from app.models.item import VocabularySource
from .types import QuestionDraft


def question_from_vocab(source: VocabularySource) -> QuestionDraft:
    expression = source.expression_as_printed.strip()
    reading = source.reading_as_printed.strip()
    meaning = source.meaning_as_printed.strip()
    prompt = expression
    if re.search(r"[\u3400-\u9fff]", expression) and reading and reading != expression:
        prompt += "\n" + reading
    candidates = []
    if meaning and expression and expression not in meaning:
        candidates.append(
            QuestionDraft(
                "vocabulary",
                source.vocabulary_id,
                source.id,
                "meaning_to_japanese",
                meaning,
                expression,
                reading or None,
            )
        )
    if (
        meaning
        and prompt
        and meaning not in prompt
        and (
            not re.search(r"[\u3400-\u9fff]", expression)
            or (reading and reading != expression)
        )
    ):
        candidates.append(
            QuestionDraft(
                "vocabulary",
                source.vocabulary_id,
                source.id,
                "japanese_to_meaning",
                prompt,
                meaning,
                reading or None,
            )
        )
    return random.choice(candidates) if candidates else None
