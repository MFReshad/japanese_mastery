from __future__ import annotations
import random
import re
from app.models.item import KanjiSource
from .types import QuestionDraft


def _plain_reading(value: str) -> str | None:
    if not value or "." in value or "・" in value:
        return None
    hiragana = "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
        for char in value.strip()
    )
    return hiragana if re.fullmatch(r"[ぁ-ゖー]+", hiragana) else None


def _target_reading(
    character: str, word: str, word_reading: str, printed_readings: list[str]
) -> str | None:
    if word.count(character) != 1 or not word_reading:
        return None
    if not (word.startswith(character) or word.endswith(character)):
        return None
    candidates = {_plain_reading(reading) for reading in printed_readings}
    candidates.discard(None)
    matching = [
        reading
        for reading in candidates
        if (word.startswith(character) and word_reading.startswith(reading))
        or (word.endswith(character) and word_reading.endswith(reading))
    ]
    return matching[0] if len(matching) == 1 else None


def _clear_standalone_meaning(meanings: list[str]) -> bool:
    if not meanings:
        return False
    for value in meanings:
        for part in value.split("/"):
            part = part.strip()
            if not part or not any(char.isalnum() for char in part):
                return False
            if part.casefold() in {
                "?",
                "unknown",
                "n/a",
                "na",
                "none",
                "tbd",
                "todo",
                "placeholder",
            }:
                return False
            if (part[0], part[-1]) in {
                ("(", ")"),
                ("[", "]"),
                ("{", "}"),
                ("（", "）"),
                ("［", "］"),
                ("【", "】"),
            }:
                return False
            if part.endswith(("...", "…", "-", ":", ",", ";")):
                return False
            if re.search(
                r"\b(?:a|an|the|of|for|to|and|or|with)\s*$", part, re.IGNORECASE
            ):
                return False
            if part.count("(") != part.count(")") or part.count("[") != part.count("]"):
                return False
    return True


def questions_from_kanji(source: KanjiSource) -> list[QuestionDraft]:
    character = source.kanji.character
    meanings = [
        value
        for value in (source.meanings_as_printed or [source.meaning_as_printed])
        if value
    ]
    readings = [*source.onyomi, *source.kunyomi]
    examples = [
        {"word": e.word, "reading": e.reading, "meaning": e.meaning}
        for e in sorted(source.examples, key=lambda e: e.sort_order)
    ]
    context = {
        "kind": "kanji",
        "kanji": character,
        "meanings": meanings,
        "onyomi": source.onyomi,
        "kunyomi": source.kunyomi,
        "examples": examples,
    }
    result = []

    def add(kind: str, prompt: str, answer: str, secondary: str | None, details: dict):
        if prompt and answer and answer.strip() not in prompt.strip():
            result.append(
                QuestionDraft(
                    "kanji",
                    source.kanji_id,
                    source.id,
                    kind,
                    prompt,
                    answer,
                    secondary,
                    details,
                )
            )

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
        details = {
            "kind": "example",
            "kanji": character,
            "target_meaning": meaning,
            "target_reading": target_reading,
            "onyomi": source.onyomi,
            "kunyomi": source.kunyomi,
            **example,
        }
        add(
            "example_kanji_to_meaning",
            base_prompt + "What does the target kanji mean?",
            meaning,
            target_reading,
            details,
        )
        if target_reading:
            add(
                "example_kanji_to_reading",
                base_prompt + "How is the target kanji read here?",
                target_reading,
                meaning or None,
                details,
            )
    return result


def question_from_kanji(source: KanjiSource) -> QuestionDraft:
    return random.choice(questions_from_kanji(source))
