from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, values):
        if not isinstance(values, dict) or not cls.__name__.endswith(
            ("Create", "Update", "In")
        ):
            return values
        nonnull = {
            "title",
            "book_id",
            "chapter_number",
            "sort_order",
            "item_order",
            "expression_as_printed",
            "reading_as_printed",
            "meaning_as_printed",
            "onyomi",
            "kunyomi",
            "examples",
            "meanings_as_printed",
        }
        for key, value in values.items():
            if (
                key
                in {"title", "expression", "character", "meaning", "meaning_as_printed"}
                and isinstance(value, str)
                and not value.strip()
            ):
                raise ValueError(f"{key} must not be blank")
            if value is None and key in nonnull:
                raise ValueError(f"{key} cannot be null")
            limit = (
                2000
                if key in {"notes", "note"}
                else 8
                if key == "character"
                else 80
                if key in {"source_page", "short_name"}
                else 120
                if key in {"source_section", "edition"}
                else 20
                if key == "jlpt_level"
                else 255
            )
            if (
                isinstance(value, str)
                and (
                    key not in {"meaning", "meaning_as_printed", "description"}
                    or cls.__name__ == "KanjiExampleIn"
                )
                and len(value) > limit
            ):
                raise ValueError(f"{key} exceeds {limit} characters")
            if key in {"book_id", "chapter_id"} and value is not None and value <= 0:
                raise ValueError(f"{key} must be positive")
            if (
                key in {"item_order", "chapter_number", "sort_order"}
                and value is not None
                and value < 0
            ):
                raise ValueError(f"{key} must be nonnegative")
        return values


class Timestamped(OrmModel):
    created_at: datetime
    updated_at: datetime
