from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.book import Book, Chapter
from app.repositories.items import create_kanji_source, create_vocabulary_source
from app.schemas.items import KanjiExampleIn, KanjiSourceCreate, VocabularySourceCreate


def seed_demo(db: Session) -> None:
    if db.scalar(select(Book).where(Book.short_name == "DEMO")):
        return
    book = Book(title="Demo Japanese Book", short_name="DEMO", edition="MVP", jlpt_level="N5", description="Demo records for local testing.", is_demo=True)
    db.add(book)
    db.flush()
    chapters = [
        Chapter(book_id=book.id, chapter_number=1, title="Greetings", sort_order=1),
        Chapter(book_id=book.id, chapter_number=2, title="Daily Life", sort_order=2),
    ]
    db.add_all(chapters)
    db.flush()
    vocab = [
        ("日本", "にほん", "Japan"), ("学生", "がくせい", "student"), ("先生", "せんせい", "teacher"), ("食べる", "たべる", "to eat"),
        ("飲む", "のむ", "to drink"), ("行く", "いく", "to go"), ("見る", "みる", "to see"), ("聞く", "きく", "to listen"),
        ("大きい", "おおきい", "big"), ("小さい", "ちいさい", "small"),
    ]
    for index, (expression, reading, meaning) in enumerate(vocab, start=1):
        create_vocabulary_source(db, VocabularySourceCreate(book_id=book.id, chapter_id=chapters[0 if index <= 5 else 1].id, item_order=index, expression=expression, reading=reading, meaning=meaning, source_section="demo"))
    kanji = [
        ("日", "day / sun", ["ニチ", "ジツ"], ["ひ"]), ("本", "book / origin", ["ホン"], ["もと"]), ("学", "study", ["ガク"], ["まな.ぶ"]),
        ("生", "life", ["セイ", "ショウ"], ["い.きる"]), ("先", "previous", ["セン"], ["さき"]), ("食", "eat / food", ["ショク"], ["た.べる"]),
        ("飲", "drink", ["イン"], ["の.む"]), ("行", "go", ["コウ"], ["い.く"]), ("見", "see", ["ケン"], ["み.る"]), ("聞", "hear", ["ブン"], ["き.く"]),
    ]
    for index, (character, meaning, onyomi, kunyomi) in enumerate(kanji, start=1):
        create_kanji_source(db, KanjiSourceCreate(book_id=book.id, chapter_id=chapters[0 if index <= 5 else 1].id, item_order=index, character=character, meaning=meaning, onyomi=onyomi, kunyomi=kunyomi, examples=[KanjiExampleIn(word=character, reading="/".join(kunyomi), meaning=meaning)]))
    db.commit()
