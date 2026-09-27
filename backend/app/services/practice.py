from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.book import Chapter
from app.models.item import KanjiSource, VocabularySource
from app.models.practice import ItemProgress, PracticeAnswer, PracticeQuestion, PracticeSession
from app.schemas.practice import PracticeStartRequest
from app.services.mastery import record_answer
from app.services.practice_cache import practice_session_cache


VOCAB_QUESTIONS = ["japanese_to_meaning", "meaning_to_japanese", "japanese_to_reading"]


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


def _eligible_sources(db: Session, payload: PracticeStartRequest, item_type: str):
    model = VocabularySource if item_type == "vocabulary" else KanjiSource
    item_id = model.vocabulary_id if item_type == "vocabulary" else model.kanji_id
    stmt = select(model)
    if item_type == "kanji":
        if payload.question_count is None:
            stmt = stmt.options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples))
        else:
            stmt = stmt.options(joinedload(KanjiSource.kanji), joinedload(KanjiSource.examples))
    if payload.book_ids:
        stmt = stmt.where(model.book_id.in_(payload.book_ids))
    if payload.chapter_ids:
        stmt = stmt.where(model.chapter_id.in_(payload.chapter_ids))
    if payload.source_entry_ids:
        stmt = stmt.where(model.id.in_(payload.source_entry_ids))
    if payload.parts:
        if item_type == "vocabulary":
            stmt = stmt.join(Chapter, Chapter.id == model.chapter_id).where(Chapter.part.in_(payload.parts))
        else:
            stmt = stmt.where(model.part.in_(payload.parts))
    if payload.order_start is not None:
        stmt = stmt.where(model.item_order >= payload.order_start)
    if payload.order_end is not None:
        stmt = stmt.where(model.item_order <= payload.order_end)
    if payload.mode != "random":
        stmt = stmt.outerjoin(ItemProgress, and_(ItemProgress.item_type == item_type,
                                                ItemProgress.item_id == item_id))
        if payload.mode == "never_practiced":
            stmt = stmt.where(ItemProgress.id.is_(None))
        elif payload.mode == "weak":
            stmt = stmt.where(ItemProgress.status == "weak")
        elif payload.mode == "wrong":
            stmt = stmt.where(or_(ItemProgress.status == "weak", ItemProgress.last_result == "wrong"))
        elif payload.mode == "mastery_review":
            stmt = stmt.where(or_(ItemProgress.id.is_(None), ItemProgress.status != "mastered"))
        elif payload.mode in ("starred", "starred_priority"):
            stmt = stmt.where(ItemProgress.is_starred.is_(True))
    if payload.question_count is not None:
        if payload.mode == "starred_priority":
            stmt = stmt.order_by(
                case(
                    (ItemProgress.status == "weak", 0),
                    (ItemProgress.status == "learning", 1),
                    (ItemProgress.status == "new", 2),
                    (ItemProgress.status == "mastered", 3),
                    else_=4,
                ),
                model.book_id, model.chapter_id, model.item_order, model.id,
            )
        else:
            stmt = stmt.order_by(func.random())
        stmt = stmt.limit(payload.question_count)
    else:
        if payload.mode == "starred_priority":
            stmt = stmt.order_by(
                case(
                    (ItemProgress.status == "weak", 0),
                    (ItemProgress.status == "learning", 1),
                    (ItemProgress.status == "new", 2),
                    (ItemProgress.status == "mastered", 3),
                    else_=4,
                ),
                model.book_id, model.chapter_id, model.item_order, model.id,
            )
        else:
            stmt = stmt.order_by(model.book_id, model.chapter_id, model.item_order, model.id)
    return db.execute(stmt).unique().scalars().all()


def question_from_vocab(source: VocabularySource) -> QuestionDraft:
    question_type = random.choice(VOCAB_QUESTIONS)
    if question_type == "meaning_to_japanese":
        prompt = source.meaning_as_printed
        primary = source.expression_as_printed
        secondary = source.reading_as_printed
    elif question_type == "japanese_to_reading":
        prompt = source.expression_as_printed
        primary = source.reading_as_printed
        secondary = source.meaning_as_printed
    else:
        prompt = source.expression_as_printed
        primary = source.meaning_as_printed
        secondary = source.reading_as_printed
    return QuestionDraft("vocabulary", source.vocabulary_id, source.id, question_type, prompt, primary, secondary)


def _plain_reading(value: str) -> str | None:
    if not value or "." in value or "・" in value:
        return None
    hiragana = "".join(chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char for char in value.strip())
    return hiragana if re.fullmatch(r"[ぁ-ゖー]+", hiragana) else None


def _target_reading(character: str, word: str, word_reading: str,
                    printed_readings: list[str]) -> str | None:
    if word.count(character) != 1 or not word_reading:
        return None
    if not (word.startswith(character) or word.endswith(character)):
        return None
    candidates = {_plain_reading(reading) for reading in printed_readings}
    candidates.discard(None)
    matching = [reading for reading in candidates if
                (word.startswith(character) and word_reading.startswith(reading)) or
                (word.endswith(character) and word_reading.endswith(reading))]
    return matching[0] if len(matching) == 1 else None


def _clear_standalone_meaning(meanings: list[str]) -> bool:
    if not meanings:
        return False
    for value in meanings:
        for part in value.split("/"):
            part = part.strip()
            if not part or not any(char.isalnum() for char in part):
                return False
            if part.casefold() in {"?", "unknown", "n/a", "na", "none", "tbd", "todo", "placeholder"}:
                return False
            if (part[0], part[-1]) in {("(", ")"), ("[", "]"), ("{", "}"),
                                       ("（", "）"), ("［", "］"), ("【", "】")}:
                return False
            if part.endswith(("...", "…", "-", ":", ",", ";")):
                return False
            if re.search(r"\b(?:a|an|the|of|for|to|and|or|with)\s*$", part, re.IGNORECASE):
                return False
            if part.count("(") != part.count(")") or part.count("[") != part.count("]"):
                return False
    return True


def questions_from_kanji(source: KanjiSource) -> list[QuestionDraft]:
    character = source.kanji.character
    meanings = [value for value in (source.meanings_as_printed or [source.meaning_as_printed]) if value]
    readings = [*source.onyomi, *source.kunyomi]
    examples = [{"word": e.word, "reading": e.reading, "meaning": e.meaning}
                for e in sorted(source.examples, key=lambda e: e.sort_order)]
    context = {"kind": "kanji", "kanji": character, "meanings": meanings,
               "onyomi": source.onyomi, "kunyomi": source.kunyomi, "examples": examples}
    result = []

    def add(kind: str, prompt: str, answer: str, secondary: str | None, details: dict):
        if prompt and answer and answer.strip() not in prompt.strip():
            result.append(QuestionDraft("kanji", source.kanji_id, source.id, kind,
                                        prompt, answer, secondary, details))

    meaning = " / ".join(meanings)
    reading = " / ".join(readings)
    add("kanji_to_meaning", character, meaning, reading or None, context)
    add("kanji_to_reading", character, reading, meaning or None, context)
    if _clear_standalone_meaning(meanings):
        add("meaning_to_kanji", meaning, character, reading or None, context)
    for example in examples:
        word = (example["word"] or "").strip()
        if not word or word == character or word.count(character) != 1:
            continue
        word_reading = (example["reading"] or "").strip()
        target_reading = _target_reading(character, word, word_reading, readings)
        surrounding = word.replace(character, "", 1)
        base_prompt = f"{word}\nTarget kanji: {character}\nContext: {surrounding}\n"
        details = {"kind": "example", "kanji": character, "target_meaning": meaning,
                   "target_reading": target_reading, "onyomi": source.onyomi,
                   "kunyomi": source.kunyomi, **example}
        add("example_kanji_to_meaning", base_prompt + "What does the target kanji mean?",
            meaning, target_reading, details)
        if target_reading:
            add("example_kanji_to_reading", base_prompt + "How is the target kanji read here?",
                target_reading, meaning or None, details)
    return result


def question_from_kanji(source: KanjiSource) -> QuestionDraft:
    return random.choice(questions_from_kanji(source))


def start_practice(db: Session, payload: PracticeStartRequest) -> tuple[PracticeSession, list[PracticeQuestion]]:
    drafts: list[QuestionDraft] = []
    if payload.practice_type in ("vocabulary", "mixed"):
        vocab = _eligible_sources(db, payload, "vocabulary")
        drafts.extend(question_from_vocab(source) for source in vocab)
    if payload.practice_type in ("kanji", "mixed"):
        kanji = _eligible_sources(db, payload, "kanji")
        drafts.extend(draft for source in kanji for draft in questions_from_kanji(source))
    if payload.mode != "starred_priority":
        random.shuffle(drafts)
    if payload.question_count is not None:
        drafts = drafts[:payload.question_count]
    session = PracticeSession(practice_type=payload.practice_type, mode=payload.mode, total_questions=len(drafts))
    db.add(session)
    db.flush()
    questions = [PracticeQuestion(session_id=session.id, position=index, **draft.__dict__)
                 for index, draft in enumerate(drafts)]
    db.add_all(questions)
    db.commit()
    practice_session_cache.store(questions)
    return session, questions


def _get_question(db: Session, session_id: int, question_id: int) -> PracticeQuestion:
    question = db.scalar(select(PracticeQuestion).where(
        PracticeQuestion.id == question_id, PracticeQuestion.session_id == session_id
    ).with_for_update())
    if question is None:
        raise HTTPException(404, "Question not found in session")
    if question.answered_at is not None:
        raise HTTPException(409, "Question already answered")
    previous_unanswered = db.scalar(select(PracticeQuestion.id).where(
        PracticeQuestion.session_id == session_id,
        PracticeQuestion.position < question.position,
        PracticeQuestion.answered_at.is_(None),
    ).limit(1))
    if previous_unanswered is not None:
        raise HTTPException(409, "Answer the current question first")
    return question


def _cached_question(db: Session, session_id: int, question_id: int):
    question = practice_session_cache.get(session_id, question_id)
    if question is None:
        persisted = db.scalar(select(PracticeQuestion).where(
            PracticeQuestion.id == question_id, PracticeQuestion.session_id == session_id
        ))
        if persisted is None:
            raise HTTPException(404, "Question not found in session")
        practice_session_cache.store([persisted])
        question = practice_session_cache.get(session_id, question_id)
    return question


def reveal_question(db: Session, session_id: int, question_id: int):
    question = _cached_question(db, session_id, question_id)
    if question.answered_at is not None:
        raise HTTPException(409, "Question already answered")
    practice_session_cache.reveal(session_id, question_id)
    return question


def answer_practice(db: Session, session_id: int, question_id: int, result: str, note: str | None = None):
    question = _cached_question(db, session_id, question_id)
    normalized_note = note.strip() if note and note.strip() else None
    if question.revealed_at is None and question.answered_at is None:
        raise HTTPException(409, "Reveal the answer before marking it")
    now = datetime.now(timezone.utc)
    claimed = db.execute(update(PracticeQuestion).where(
        PracticeQuestion.id == question_id, PracticeQuestion.session_id == session_id,
        PracticeQuestion.answered_at.is_(None),
    ).values(answered_at=now, revealed_at=question.revealed_at).returning(PracticeQuestion.id)).scalar_one_or_none()
    if claimed is None:
        existing = db.scalar(select(PracticeAnswer).where(
            PracticeAnswer.question_id == question_id, PracticeAnswer.session_id == session_id
        ))
        if existing and existing.result == result and existing.wrong_note == normalized_note:
            progress = db.scalar(select(ItemProgress).where(
                ItemProgress.item_type == existing.item_type, ItemProgress.item_id == existing.item_id
            ))
            return progress, existing.answered_at
        raise HTTPException(409, "Question already answered")
    answer = PracticeAnswer(
        question_id=question_id, session_id=session_id, item_type=question.item_type,
        item_id=question.item_id, source_entry_id=question.source_entry_id,
        question_type=question.question_type, result=result,
        wrong_note=normalized_note,
    )
    db.add(answer)
    db.execute(update(PracticeSession).where(PracticeSession.id == session_id).values(
        correct_count=PracticeSession.correct_count + (1 if result == "correct" else 0),
        wrong_count=PracticeSession.wrong_count + (1 if result == "wrong" else 0),
        completed_at=case(
            (PracticeSession.correct_count + PracticeSession.wrong_count + 1 >= PracticeSession.total_questions, now),
            else_=PracticeSession.completed_at,
        ),
    ))
    progress = record_answer(db, question.item_type, question.item_id, result)
    db.commit()
    practice_session_cache.answered(session_id, question_id, now)
    return progress, now
