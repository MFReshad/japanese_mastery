from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.practice import ItemProgress


def get_or_create_progress(db: Session, item_type: str, item_id: int) -> ItemProgress:
    # The unique constraint arbitrates first creation; the lock serializes every
    # subsequent read-modify-write, including stars, across workers/sessions.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(
        insert(ItemProgress)
        .values(item_type=item_type, item_id=item_id)
        .on_conflict_do_nothing(index_elements=["item_type", "item_id"])
    )
    return db.scalar(
        select(ItemProgress)
        .where(ItemProgress.item_type == item_type, ItemProgress.item_id == item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
