"use client";
import { useLookupRefresh } from "@/features/useLookupRefresh";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, BookOpen, ChevronRight, Play } from "lucide-react";
import { api, Book, Chapter, getActiveBooks, getChapters, StudyKind, StudyListItem, StudyNextChapter } from "@/lib/api";

export default function StudyPage() {
  return <Suspense fallback={<main className="py-12">Loading...</main>}><StudyHome /></Suspense>;
}

function StudyHome() {
  const params = useSearchParams();
  const [lookupsReady, setLookupsReady] = useState(false);
  const [books, setBooks] = useState<Book[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  useLookupRefresh(setBooks, setChapters);
  const [bookId, setBookId] = useState(params.get("book") ?? "");
  const [part, setPart] = useState(params.get("part") ?? "");
  const [chapterId, setChapterId] = useState(params.get("chapter") ?? "");
  const [kind, setKind] = useState<StudyKind>(params.get("kind") === "kanji" ? "kanji" : "vocabulary");
  const [items, setItems] = useState<StudyListItem[]>([]);
  const [nextChapter, setNextChapter] = useState<StudyNextChapter | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getActiveBooks(), getChapters()]).then(([loadedBooks, loadedChapters]) => {
      setLookupsReady(true);
      setBooks(loadedBooks);
      setChapters(loadedChapters);
      if (!loadedBooks.some((book) => String(book.id) === bookId) && loadedBooks.length) {
        const first = loadedBooks.find((book) => !book.is_demo) ?? loadedBooks[0];
        setBookId(String(first.id));
        if (first.vocabulary_count === 0 && first.kanji_count > 0) setKind("kanji");
      }
    }).catch((reason) => setError(String(reason)));
  }, []);

  const selectedBook = books.find((book) => String(book.id) === bookId);
  const bookChapters = useMemo(() => chapters.filter((chapter) => String(chapter.book_id) === bookId).sort((a, b) =>
    String(a.part ?? "").localeCompare(String(b.part ?? ""), undefined, { numeric: true }) ||
    a.sort_order - b.sort_order || a.chapter_number - b.chapter_number || a.id - b.id), [chapters, bookId]);
  const parts = useMemo(() => Array.from(new Set(bookChapters.map((chapter) => chapter.part).filter((value) => value !== null))).map(String), [bookChapters]);
  const visibleChapters = useMemo(() => bookChapters.filter((chapter) => !part || String(chapter.part) === part), [bookChapters, part]);
  const selectedChapter = visibleChapters.find((chapter) => String(chapter.id) === chapterId);

  useEffect(() => {
    if (lookupsReady && chapterId && !selectedChapter) setChapterId("");
  }, [chapterId, selectedChapter, lookupsReady]);

  useEffect(() => {
    if (lookupsReady && bookId && !chapterId && visibleChapters.length) setChapterId(String(visibleChapters[0].id));
  }, [bookId, chapterId, visibleChapters, lookupsReady]);

  useEffect(() => {
    if (!bookId || !chapterId) { setItems([]); setNextChapter(null); return; }
    let active = true;
    setLoading(true);
    setItems([]);
    setError("");
    setNextChapter(null);
    Promise.all([
      api<StudyListItem[]>(`/study/items?book_id=${bookId}&chapter_id=${chapterId}&kind=${kind}`),
      api<StudyNextChapter | null>(`/study/next-chapter?book_id=${bookId}&chapter_id=${chapterId}&kind=${kind}`),
    ])
      .then(([rows, following]) => { if (active) { setItems(rows); setNextChapter(following); } })
      .catch((reason) => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [bookId, chapterId, kind]);

  useEffect(() => {
    const restore = () => {
      const url = new URLSearchParams(window.location.search);
      setBookId(url.get("book") ?? ""); setChapterId(url.get("chapter") ?? "");
      setPart(url.get("part") ?? ""); setKind(url.get("kind") === "kanji" ? "kanji" : "vocabulary");
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (!lookupsReady || !selectedChapter) return;
    const url = new URL(window.location.href);
    for (const [key, value] of Object.entries({book: bookId, chapter: chapterId, part, kind})) {
      if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    }
    window.history.replaceState(window.history.state, "", url);
  }, [lookupsReady, selectedChapter, bookId, chapterId, part, kind]);

  function selectBook(id: string) {
    setBookId(id); setPart(""); setChapterId(""); setItems([]);
    const book = books.find((entry) => String(entry.id) === id);
    if (book?.vocabulary_count === 0 && book.kanji_count > 0) setKind("kanji");
  }

  const practiceHref = selectedChapter ? `/practice?practice_type=${kind}&book_id=${bookId}&chapter_id=${chapterId}` : "/practice";

  return <div className="mx-auto max-w-4xl pb-12">
    <header className="mb-6 border-b border-stone-300 pb-5">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-moss"><BookOpen size={18} /> Study</div>
      <h1 className="text-3xl font-semibold text-ink sm:text-4xl">{selectedBook?.title ?? "Study"}</h1>
    </header>

    <div className="grid gap-3 border-b border-stone-200 pb-5 sm:grid-cols-3">
      <label className="block text-sm font-medium text-stone-600">Book
        <select className="mt-1 block min-h-12 w-full border border-stone-300 bg-white px-3 text-ink" value={bookId} onChange={(event) => selectBook(event.target.value)}>
          <option value="">Select book</option>{books.map((book) => <option value={book.id} key={book.id}>{book.title}</option>)}
        </select>
      </label>
      {parts.length > 0 && <label className="block text-sm font-medium text-stone-600">Part
        <select className="mt-1 block min-h-12 w-full border border-stone-300 bg-white px-3 text-ink" value={part} onChange={(event) => { setPart(event.target.value); setChapterId(""); }}>
          <option value="">All parts</option>{parts.map((value) => <option key={value} value={value}>Part {value}</option>)}
        </select>
      </label>}
      <label className="block text-sm font-medium text-stone-600">Lesson
        <select className="mt-1 block min-h-12 w-full border border-stone-300 bg-white px-3 text-ink" value={chapterId} onChange={(event) => setChapterId(event.target.value)}>
          <option value="">Select lesson</option>{visibleChapters.map((chapter) => <option value={chapter.id} key={chapter.id}>{chapter.part !== null ? `Part ${chapter.part} · ` : ""}Lesson {chapter.chapter_number}: {chapter.title}</option>)}
        </select>
      </label>
    </div>

    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
      <div className="flex border-b border-stone-300" role="tablist" aria-label="Study type">
        {(["vocabulary", "kanji"] as const).map((value) => <button key={value} role="tab" aria-selected={kind === value} onClick={() => setKind(value)} className={`min-h-11 border-b-2 px-4 font-medium capitalize ${kind === value ? "border-moss text-moss" : "border-transparent text-stone-500"}`}>{value}</button>)}
      </div>
      {selectedChapter && <Link href={practiceHref} className="inline-flex min-h-11 items-center gap-2 px-2 font-medium text-moss"><Play size={17} /> Practice this chapter</Link>}
    </div>

    {selectedChapter && <div className="mt-6 flex items-end justify-between gap-4 border-b border-stone-300 pb-3">
      <div><p className="text-sm text-stone-500">{selectedChapter.part !== null ? `Part ${selectedChapter.part} · ` : ""}Lesson {selectedChapter.chapter_number}</p><h2 className="text-2xl font-semibold">{selectedChapter.title}</h2></div>
      <span className="shrink-0 text-sm text-stone-500">{loading ? "..." : `${items.length} ${kind === "kanji" ? "kanji" : "words"}`}</span>
    </div>}
    {error && <p role="alert" className="mt-5 text-persimmon">{error}</p>}
    {!selectedChapter && <p className="py-12 text-center text-stone-500">Select a lesson to begin.</p>}
    {selectedChapter && !loading && items.length === 0 && !error && <p className="py-12 text-center text-stone-500">No {kind} in this lesson.</p>}
    {selectedChapter && loading && <div aria-label="Loading lesson" className="mt-4 space-y-3">{Array.from({ length: 5 }, (_, index) => <div key={index} className="h-20 animate-pulse bg-stone-100" />)}</div>}
    <div className="divide-y divide-stone-200">
      {items.map((item) => <Link href={`/study/${kind}/${encodeURIComponent(item.source_id)}`} key={item.source_id} className="group flex min-h-24 items-center gap-4 py-4 hover:bg-white/60">
        <span className="w-9 shrink-0 text-right text-sm tabular-nums text-stone-400">{item.item_order}</span>
        {kind === "kanji" ? <>
          <span className="w-16 shrink-0 text-center text-5xl font-semibold leading-none text-ink">{item.character}</span>
          <span className="min-w-0 flex-1"><span className="block break-words font-medium">{item.meaning}</span><span className="mt-1 block break-words text-sm text-stone-600">{[...(item.onyomi ?? []), ...(item.kunyomi ?? [])].join(" · ") || "No readings listed"}</span><span className="mt-1 block text-xs text-stone-500">{item.example_count ?? 0} examples</span></span>
        </> : <span className="min-w-0 flex-1"><span className="block break-words text-xl font-semibold">{item.expression}</span><span className="block break-words text-sm text-stone-600">{item.reading}</span><span className="mt-1 block break-words">{item.meaning}</span></span>}
        <ArrowRight size={19} className="shrink-0 text-stone-400 group-hover:text-moss" />
      </Link>)}
    </div>
    {selectedChapter && nextChapter && !loading && <div className="mt-6 border-t border-stone-300 pt-5">
      <Link href={`/study?${new URLSearchParams({ book: bookId, chapter: String(nextChapter.chapter_id), kind, ...(nextChapter.part !== null ? { part: String(nextChapter.part) } : {}) })}`}
        onClick={() => { setPart(nextChapter.part === null ? "" : String(nextChapter.part)); setChapterId(String(nextChapter.chapter_id)); window.scrollTo({ top: 0, behavior: "smooth" }); }}
        className="flex min-h-14 w-full items-center justify-between gap-3 border border-moss bg-white px-4 font-medium text-moss sm:w-auto sm:min-w-64">
        <span>Next Chapter <span className="ml-1 text-sm font-normal text-stone-600">{nextChapter.part !== null ? `Part ${nextChapter.part} · ` : ""}Lesson {nextChapter.chapter_number}</span></span>
        <ChevronRight size={20} className="shrink-0" />
      </Link>
    </div>}
  </div>;
}
