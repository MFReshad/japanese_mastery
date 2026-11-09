from app.models.item import VocabularySource, KanjiSource
from app.schemas.items import VocabularySourceRead, KanjiSourceRead, KanjiExampleIn


def vocab_out(source: VocabularySource, status: str = "new") -> VocabularySourceRead:
    return VocabularySourceRead.model_validate(
        {
            "id": source.id,
            "source_id": source.source_id,
            "vocabulary_id": source.vocabulary_id,
            "book_id": source.book_id,
            "chapter_id": source.chapter_id,
            "item_order": source.item_order,
            "original_item_order": source.original_item_order,
            "manually_added": source.manually_added,
            "manually_reordered": source.manually_reordered,
            "expression_as_printed": source.expression_as_printed,
            "reading_as_printed": source.reading_as_printed,
            "meaning_as_printed": source.meaning_as_printed,
            "notes": source.notes,
            "source_file": source.source_file,
            "source_page": source.source_page,
            "source_section": source.source_section,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            "expression": source.vocabulary.expression,
            "reading": source.vocabulary.reading,
            "status": status,
            "knowledge_status": source.knowledge_status,
        }
    )


def kanji_out(source: KanjiSource, status: str = "new") -> KanjiSourceRead:
    return KanjiSourceRead.model_validate(
        {
            "id": source.id,
            "source_id": source.source_id,
            "kanji_id": source.kanji_id,
            "book_id": source.book_id,
            "chapter_id": source.chapter_id,
            "item_order": source.item_order,
            "meaning_as_printed": source.meaning_as_printed,
            "onyomi": source.onyomi,
            "kunyomi": source.kunyomi,
            "notes": source.notes,
            "uncertain": source.uncertain,
            "source_file": source.source_file,
            "source_page": source.source_page,
            "source_section": source.source_section,
            "extraction_batch": source.extraction_batch,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            "character": source.kanji.character,
            "examples": [
                KanjiExampleIn.model_validate(example) for example in source.examples
            ],
            "status": status,
        }
    )
