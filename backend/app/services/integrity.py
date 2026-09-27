from sqlalchemy import select
from app.errors import InvalidOperation, NotFound
from app.models.book import Book, Chapter


def validate_ownership(db, book_id, chapter_id):
    if db.get(Book, book_id) is None:
        raise NotFound("Book not found")
    if chapter_id is not None:
        chapter = db.scalar(
            select(Chapter).where(Chapter.id == chapter_id).with_for_update()
        )
        if chapter is None or chapter.book_id != book_id:
            raise InvalidOperation("Chapter must belong to the selected book")


def meaning_fields(meaning, meanings=None):
    values = meanings if meanings is not None else meaning.split("/")
    values = [value.strip() for value in values if value.strip()]
    return {"meaning_as_printed": " / ".join(values), "meanings_as_printed": values}
