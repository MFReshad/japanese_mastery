"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronLeft, ChevronRight, Star } from "lucide-react";
import { api, Book, Chapter, getBooks, getChapters } from "@/lib/api";

type LibraryItem = {
  id: number; source_id: string; item_order: number; book_id: number; chapter_id: number | null;
  meaning_as_printed: string; status: string; expression_as_printed?: string;
  reading_as_printed?: string; character?: string; onyomi?: string[]; kunyomi?: string[];
  is_starred: boolean;
};
type LibraryPageResult = { items: LibraryItem[]; total: number; page: number; page_size: number };
type LibraryFilter = "all" | "new" | "learning" | "weak" | "mastered" | "starred";

export default function LibraryPage() {
  const [type, setType] = useState<"vocabulary" | "kanji">("vocabulary");
  const [books, setBooks] = useState<Book[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [bookId, setBookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [statusFilter, setStatusFilter] = useState<LibraryFilter>("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<LibraryPageResult>({ items: [], total: 0, page: 1, page_size: 50 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { Promise.all([getBooks(), getChapters()]).then(([loadedBooks, loadedChapters]) => {
    setBooks(loadedBooks); setChapters(loadedChapters);
  }).catch((reason) => setError(String(reason))); }, []);
  useEffect(() => { const timer = setTimeout(() => setDebouncedSearch(search), 250); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    let active = true;
    const qs = new URLSearchParams({ kind: type, page: String(page), page_size: "50" });
    if (bookId) qs.set("book_id", bookId);
    if (chapterId) qs.set("chapter_id", chapterId);
    if (statusFilter !== "all") qs.set("status", statusFilter);
    if (debouncedSearch) qs.set("search", debouncedSearch);
    setLoading(true); setError("");
    api<LibraryPageResult>(`/library/items?${qs}`).then((data) => { if (active) setResult(data); })
      .catch((reason) => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [type, bookId, chapterId, statusFilter, debouncedSearch, page]);

  const visibleChapters = useMemo(() => chapters.filter((chapter) => !bookId || chapter.book_id === Number(bookId)), [chapters, bookId]);
  const lastPage = Math.max(1, Math.ceil(result.total / result.page_size));
  function toggleStar(item: LibraryItem) {
    const next = !item.is_starred;
    setResult((current) => ({ ...current, items: current.items.map((entry) => entry.id === item.id ? { ...entry, is_starred: next } : entry) }));
    api(`/library/items/${type}/${item.id}/star`, { method: "PATCH", body: JSON.stringify({ is_starred: next }) })
      .catch((reason) => {
        setResult((current) => ({ ...current, items: current.items.map((entry) => entry.id === item.id ? { ...entry, is_starred: item.is_starred } : entry) }));
        setError(String(reason));
      });
  }
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center gap-2">
      <Segment value={type} setValue={(value) => { setType(value); setPage(1); }} />
      <select aria-label="Book" className="min-h-11 rounded border border-stone-300 bg-white px-3" value={bookId} onChange={(event) => { setBookId(event.target.value); setChapterId(""); setPage(1); }}><option value="">All books</option>{books.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}</select>
      <select aria-label="Chapter" className="min-h-11 rounded border border-stone-300 bg-white px-3" value={chapterId} onChange={(event) => { setChapterId(event.target.value); setPage(1); }}><option value="">All chapters</option>{visibleChapters.map((chapter) => <option key={chapter.id} value={chapter.id}>Lesson {chapter.chapter_number}: {chapter.title}</option>)}</select>
      <select aria-label="Status or star filter" className="min-h-11 rounded border border-stone-300 bg-white px-3" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value as LibraryFilter); setPage(1); }}>
        <option value="all">All</option><option value="new">New</option><option value="learning">Learning</option><option value="weak">Weak</option><option value="mastered">Mastered</option><option value="starred">Starred</option>
      </select>
      <input aria-label="Search library" className="min-h-11 min-w-0 flex-1 rounded border border-stone-300 bg-white px-3 sm:max-w-xs" placeholder="Search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
    </div>
    {error && <p role="alert" className="text-persimmon">{error}</p>}
    {loading ? <div className="grid gap-3 md:grid-cols-2" aria-label="Loading library">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-32 animate-pulse rounded border border-stone-200 bg-stone-100" />)}</div> : <>
      <div className="text-sm text-stone-600">{result.total} {type === "kanji" ? "kanji entries" : "vocabulary entries"}</div>
      <div className="grid gap-3 md:grid-cols-2">{result.items.map((item) => <article key={item.id} className="rounded border border-stone-200 bg-white p-4"><div className="flex items-start justify-between gap-3"><h2 className={`${type === "kanji" ? "text-5xl" : "text-2xl"} font-semibold`}>{type === "kanji" ? item.character : item.expression_as_printed}</h2><div className="flex shrink-0 items-center gap-2"><button type="button" aria-label={item.is_starred ? "Unstar item" : "Star item"} title={item.is_starred ? "Unstar item" : "Star item"} className="flex min-h-9 min-w-9 items-center justify-center rounded border border-stone-200 text-moss hover:bg-stone-50" onClick={() => toggleStar(item)}><Star size={18} fill={item.is_starred ? "currentColor" : "none"} /></button><Status status={item.status} /></div></div>{type === "vocabulary" && <p className="text-lg text-stone-600">{item.reading_as_printed}</p>}<p className="mt-2">{item.meaning_as_printed}</p>{type === "kanji" && <><p className="text-sm text-stone-600">On: {item.onyomi?.join(" / ") || "-"}</p><p className="text-sm text-stone-600">Kun: {item.kunyomi?.join(" / ") || "-"}</p></>}<Link href={`/study/${type}/${encodeURIComponent(item.source_id)}`} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-moss">Study <ArrowRight size={15} /></Link></article>)}</div>
      {result.total === 0 && <p className="py-10 text-center text-stone-500">No matching entries.</p>}
      {lastPage > 1 && <nav aria-label="Library pages" className="flex items-center justify-center gap-4 pb-6"><button aria-label="Previous page" disabled={page <= 1} className="flex min-h-11 items-center gap-1 rounded border px-3 disabled:opacity-40" onClick={() => setPage(page - 1)}><ChevronLeft size={18} /> Previous</button><span className="text-sm">{page} / {lastPage}</span><button aria-label="Next page" disabled={page >= lastPage} className="flex min-h-11 items-center gap-1 rounded border px-3 disabled:opacity-40" onClick={() => setPage(page + 1)}>Next <ChevronRight size={18} /></button></nav>}
    </>}
  </div>;
}

function Segment({ value, setValue }: { value: "vocabulary" | "kanji"; setValue: (value: "vocabulary" | "kanji") => void }) {
  return <div className="flex rounded border border-stone-300 bg-white p-1"><button className={`rounded px-3 py-2 ${value === "vocabulary" ? "bg-ink text-white" : ""}`} onClick={() => setValue("vocabulary")}>Vocabulary</button><button className={`rounded px-3 py-2 ${value === "kanji" ? "bg-ink text-white" : ""}`} onClick={() => setValue("kanji")}>Kanji</button></div>;
}

function Status({ status }: { status: string }) {
  return <span className="rounded bg-stone-100 px-2 py-1 text-xs uppercase text-stone-600">{status}</span>;
}
