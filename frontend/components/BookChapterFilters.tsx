import { Book, Chapter } from "@/lib/api";
import { sortChaptersByPart } from "@/lib/chapterSort";

type Props = { books: Book[]; chapters: Chapter[]; bookId: string; chapterId: string;
  onBookChange: (id: string) => void; onChapterChange: (id: string) => void; disabled?: boolean };
export function BookChapterFilters({ books, chapters, bookId, chapterId, onBookChange, onChapterChange, disabled }: Props) {
  const style = "min-h-11 rounded border border-stone-300 bg-white px-3";
  return <>
    <select aria-label="Book" disabled={disabled} className={style} value={bookId} onChange={event => onBookChange(event.target.value)}>
      <option value="">All books</option>{books.map(book => <option key={book.id} value={book.id}>{book.title}</option>)}
    </select>
    <select aria-label="Chapter" disabled={disabled} className={style} value={chapterId} onChange={event => onChapterChange(event.target.value)}>
      <option value="">All chapters</option>{sortChaptersByPart(chapters.filter(chapter => !bookId || chapter.book_id === Number(bookId))).map(chapter => <option key={chapter.id} value={chapter.id}>Lesson {chapter.chapter_number}: {chapter.title}</option>)}
    </select>
  </>;
}
