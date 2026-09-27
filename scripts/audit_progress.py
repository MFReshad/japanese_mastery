"""Read-only progress duplicate audit. Never prints credentials or note contents."""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from app.db.session import SessionLocal

with SessionLocal() as db:
    rows = (
        db.execute(
            text("""SELECT item_type, item_id, count(*) AS row_count,
        sum(attempts) AS reported_attempts, sum(correct_count) AS reported_correct,
        sum(wrong_count) AS reported_wrong FROM item_progress
        GROUP BY item_type, item_id HAVING count(*) > 1""")
        )
        .mappings()
        .all()
    )
    print(json.dumps([dict(row) for row in rows], indent=2))
    raise SystemExit(2 if rows else 0)
