from sqlalchemy import String, cast, func


def part_matches(column, values):
    # JSON scalars only. Trim the JSON string quotes; numeric/string part labels
    # share one UI representation. No PostgreSQL JSON equality operator needed.
    return func.trim(cast(column, String), '"').in_([str(value) for value in values])
