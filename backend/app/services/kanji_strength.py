from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import Numeric, and_, case, cast, func, select
from sqlalchemy.orm import aliased

from app.models.item import KanjiExample, KanjiSource
from app.models.practice import ItemProgress


STATUSES = ("new", "learning", "weak", "mastered")


@dataclass(frozen=True)
class KanjiStrength:
    status: str
    total_examples: int
    practiced_examples: int
    weak_examples: int
    mastered_examples: int
    unpracticed_examples: int
    weakness_percent: float
    direct_status: str
    direct_attempts: int

    def as_dict(self) -> dict:
        return asdict(self)


def calculate_kanji_strength(
    *, direct_status: str | None, direct_attempts: int, example_statuses: list[str]
) -> KanjiStrength:
    total = len(example_statuses)
    practiced = sum(status != "new" for status in example_statuses)
    weak = example_statuses.count("weak")
    mastered = example_statuses.count("mastered")
    direct = direct_status if direct_attempts > 0 and direct_status in STATUSES else "new"

    if total == 0:
        status = direct
    elif practiced == 0:
        status = "new"
    elif weak / practiced > 0.5:
        status = "weak"
    elif practiced == total and mastered / practiced >= 0.9:
        status = "mastered"
    else:
        status = "learning"

    return KanjiStrength(
        status=status,
        total_examples=total,
        practiced_examples=practiced,
        weak_examples=weak,
        mastered_examples=mastered,
        unpracticed_examples=total - practiced,
        weakness_percent=round(weak / practiced * 100, 1) if practiced else 0.0,
        direct_status=direct,
        direct_attempts=direct_attempts,
    )


def status_expression(*, direct_attempts, direct_status, total, practiced, weak, mastered):
    """Authoritative SQL equivalent of calculate_kanji_strength."""
    return case(
        (total == 0, case((direct_attempts > 0, direct_status), else_="new")),
        (practiced == 0, "new"),
        (weak * 2 > practiced, "weak"),
        (and_(practiced == total, mastered * 10 >= practiced * 9), "mastered"),
        else_="learning",
    )


def kanji_strength_subquery():
    direct = aliased(ItemProgress)
    example_progress = aliased(ItemProgress)
    direct_attempts = func.coalesce(func.max(direct.attempts), 0)
    direct_status = func.coalesce(func.max(direct.status), "new")
    total = func.count(func.distinct(KanjiExample.canonical_id))
    practiced = func.count(func.distinct(KanjiExample.canonical_id)).filter(example_progress.attempts > 0)
    weak = func.count(func.distinct(KanjiExample.canonical_id)).filter(and_(example_progress.attempts > 0, example_progress.status == "weak"))
    mastered = func.count(func.distinct(KanjiExample.canonical_id)).filter(and_(example_progress.attempts > 0, example_progress.status == "mastered"))
    status = status_expression(direct_attempts=direct_attempts, direct_status=direct_status, total=total, practiced=practiced, weak=weak, mastered=mastered)
    return (
        select(
            KanjiSource.id.label("source_id"),
            status.label("status"),
            total.label("total_examples"),
            practiced.label("practiced_examples"),
            weak.label("weak_examples"),
            mastered.label("mastered_examples"),
            (total - practiced).label("unpracticed_examples"),
            case((practiced > 0, func.round(cast(weak * 100.0 / practiced, Numeric), 1)), else_=0.0).label("weakness_percent"),
            case((direct_attempts > 0, direct_status), else_="new").label("direct_status"),
            direct_attempts.label("direct_attempts"),
        )
        .outerjoin(direct, and_(direct.item_type == "kanji", direct.item_id == KanjiSource.kanji_id))
        .outerjoin(KanjiExample, KanjiExample.kanji_source_id == KanjiSource.id)
        .outerjoin(example_progress, and_(example_progress.item_type == "kanji_example", example_progress.item_id == KanjiExample.canonical_id))
        .group_by(KanjiSource.id)
        .subquery()
    )
