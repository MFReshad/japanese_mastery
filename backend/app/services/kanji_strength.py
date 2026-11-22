from __future__ import annotations


def effective_kanji_status(
    direct_status: str | None,
    direct_attempts: int,
    example_statuses: list[str],
) -> str:
    """Combine direct character practice with its source example-word evidence."""
    example_total = len(example_statuses)
    example_weak = example_statuses.count("weak")
    example_mastered = example_statuses.count("mastered")
    example_practiced = sum(status != "new" for status in example_statuses)

    if (direct_attempts > 0 and direct_status == "weak") or (
        example_total > 0 and example_weak * 2 > example_total
    ):
        return "weak"
    if (direct_attempts > 0 and direct_status == "mastered") or (
        example_total > 0 and example_mastered == example_total
    ):
        return "mastered"
    if direct_attempts > 0 or example_practiced > 0:
        return "learning"
    return "new"
