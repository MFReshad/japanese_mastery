"use client";

import Link from "next/link";
import { ArrowRight, Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Coverage } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { PracticeHistory } from "@/features/progress/PracticeHistory";

type Material = "vocabulary" | "kanji_examples" | "kanji";
type DetailStatus = "new" | "weak" | "mastered";
type ProgressDetailItem = { id: number; content: string; reading: string; meaning: string; status: DetailStatus; chapter_id: number; chapter_number: number; chapter_title: string; chapter_part: number | string | null; study_kind: "vocabulary" | "kanji"; study_source_id: string };
type ProgressDetailResult = { items: ProgressDetailItem[]; total: number; page: number; page_size: number };

export default function ProgressPage() {
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [bookId, setBookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [material, setMaterial] = useState<Material>("vocabulary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [detailStatus, setDetailStatus] = useState<DetailStatus | null>(null);
  useEffect(() => { api<Coverage[]>("/progress/books").then(setCoverage).catch(reason => setError(String(reason))).finally(() => setLoading(false)); }, []);

  const books = useMemo(() => Array.from(new Map(coverage.map(row => [row.book_id, row.book_title])).entries()).map(([id, title]) => ({id, title})), [coverage]);
  const chapters = sortCoverage(coverage.filter(row => !bookId || String(row.book_id) === bookId));
  const scoped = chapters.filter(row => !chapterId || String(row.chapter_id) === chapterId);
  const stats = aggregate(scoped, material);
  const scopeName = chapterId ? chapters.find(row => String(row.chapter_id) === chapterId)?.chapter_title : bookId ? books.find(book => String(book.id) === bookId)?.title : "All books";
  useEffect(() => { setDetailStatus(null); }, [bookId, chapterId, material]);

  const header = <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">Progress</p><h1 className="mt-1 text-3xl font-semibold">{showHistory ? "Practice history" : "Learning status"}</h1><p className="mt-2 text-stone-600">{showHistory ? "Review previous sessions, answers, and study sources." : "Choose exactly what you want to measure."}</p></div><button type="button" onClick={() => setShowHistory(current => !current)} className="min-h-11 rounded-lg border border-moss bg-white px-4 font-semibold text-moss hover:bg-moss hover:text-white">{showHistory ? "Learning status" : "History"}</button></header>;

  if (showHistory) return <div className="mx-auto max-w-5xl space-y-6 pb-12">{header}<PracticeHistory /></div>;
  if (loading) return <div className="mx-auto max-w-5xl space-y-6 pb-12">{header}<LoadingState className="h-96 animate-pulse rounded-2xl bg-stone-100" /></div>;

  return <div className="mx-auto max-w-5xl space-y-6 pb-12">
    {header}
    {error && <ErrorState className="rounded-xl border border-persimmon bg-white p-4 text-persimmon">{error}</ErrorState>}

    <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">Filters</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-medium">Book<select value={bookId} onChange={event => { setBookId(event.target.value); setChapterId(""); }} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="">All books</option>{books.map(book => <option key={book.id} value={book.id}>{book.title}</option>)}</select></label>
        <label className="text-sm font-medium">Chapter<select value={chapterId} onChange={event => setChapterId(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="">All chapters</option>{chapters.map(row => <option key={row.chapter_id} value={row.chapter_id}>Lesson {row.chapter_number}: {row.chapter_title}</option>)}</select></label>
        <label className="text-sm font-medium">Material<select value={material} onChange={event => setMaterial(event.target.value as Material)} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="vocabulary">Vocabulary words</option><option value="kanji_examples">Kanji example words</option><option value="kanji">Kanji characters</option></select></label>
      </div>
    </section>

    <section className="rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="border-b border-stone-200 p-5 sm:p-6"><p className="text-sm font-medium text-moss">{scopeName}</p><h2 className="mt-1 text-2xl font-semibold">{materialName(material)}</h2></div>
      <div className="grid md:grid-cols-2 md:divide-x md:divide-stone-200">
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between"><div><h3 className="font-semibold">{material === "kanji" ? "Example-word evidence" : "Your self-assessment"}</h3><p className="mt-1 text-sm text-stone-500">{material === "kanji" ? "Manual marks on this kanji’s example words" : "Based only on your ✓ and ✕ marks"}</p></div><span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{stats.reviewedPercent}% marked</span></div>
          <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-stone-100"><div className="bg-moss" style={{width: `${percentage(stats.known, stats.manualTotal)}%`}} /><div className="bg-persimmon" style={{width: `${percentage(stats.unknown, stats.manualTotal)}%`}} /></div>
          <div className="mt-5 grid grid-cols-3 gap-2"><Metric label="Known" value={stats.known} icon={<Check size={17} />} tone="known" /><Metric label="Unknown" value={stats.unknown} icon={<X size={17} />} tone="unknown" /><Metric label="Not marked" value={stats.unmarked} /></div>
          <p className="mt-4 text-xs text-stone-500">Total: {stats.manualTotal} {material === "vocabulary" ? "vocabulary words" : "kanji example words"}</p>
        </div>
        <div className="border-t border-stone-200 p-5 md:border-t-0 sm:p-6">
          <h3 className="font-semibold">Automatic practice result</h3><p className="mt-1 text-sm text-stone-500">Ratios use all {stats.practiceTotal} {materialName(material).toLocaleLowerCase()} in this selection</p>
          <div className="mt-5 grid grid-cols-2 gap-2"><Ratio label="Touched" value={stats.practiced} total={stats.practiceTotal} tone="neutral" /><Ratio label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} tone="neutral" selected={detailStatus === "new"} onClick={bookId ? () => setDetailStatus(current => current === "new" ? null : "new") : undefined} /><Ratio label="Weak" value={stats.weak} total={stats.practiceTotal} tone="weak" selected={detailStatus === "weak"} onClick={bookId ? () => setDetailStatus(current => current === "weak" ? null : "weak") : undefined} /><Ratio label="Mastered" value={stats.mastered} total={stats.practiceTotal} tone="mastered" selected={detailStatus === "mastered"} onClick={bookId ? () => setDetailStatus(current => current === "mastered" ? null : "mastered") : undefined} /></div>
          <div className="mt-5 h-3 overflow-hidden rounded-full bg-stone-100"><div className="h-full bg-moss" style={{width: `${stats.masteryPercent}%`}} /></div>
          <p className="mt-2 text-xs text-stone-500">Mastery: {stats.mastered}/{stats.practiceTotal} · {stats.masteryPercent}%</p>
          {material === "kanji" && <p className="mt-3 rounded-lg bg-stone-50 p-3 text-xs text-stone-600">Main kanji strength comes from example words. It becomes Weak when <strong>more than half of the practiced examples are weak</strong>, including when the only practiced example is weak. Direct Practice remains separate.</p>}
          {material === "kanji_examples" && <p className="mt-3 rounded-lg bg-stone-50 p-3 text-xs text-stone-600"><strong>{stats.exampleSetsMastered}/{stats.kanjiTotal} kanji</strong> have every example word mastered.</p>}
        </div>
      </div>
      <div className="grid gap-2 border-t border-stone-200 p-4 sm:grid-cols-3 sm:p-5"><Link href={`/practice?practice_type=${material === "vocabulary" ? "vocabulary" : material === "kanji_examples" ? "kanji_example_words" : "kanji"}${material === "kanji" ? "" : "&condition=unknown"}${bookId ? `&book_id=${bookId}` : ""}${chapterId ? `&chapter_id=${chapterId}` : ""}`} className="flex min-h-11 items-center justify-center rounded-lg border border-persimmon/40 text-sm font-semibold text-persimmon">{material === "kanji" ? "Practice all kanji" : "Practice ✕ unknown"}</Link><Link href={`/practice?practice_type=${material === "vocabulary" ? "vocabulary" : material === "kanji_examples" ? "kanji_example_words" : "kanji"}&condition=weak${bookId ? `&book_id=${bookId}` : ""}${chapterId ? `&chapter_id=${chapterId}` : ""}`} className="flex min-h-11 items-center justify-center rounded-lg bg-ink text-sm font-semibold text-white">Practice weak</Link><Link href={`/study?${new URLSearchParams({...(bookId ? {book: bookId} : {}), ...(chapterId ? {chapter: chapterId} : {}), kind: material === "vocabulary" ? "vocabulary" : "kanji"})}`} target="_blank" rel="noopener noreferrer" className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-stone-300 text-sm font-semibold">Open study <ArrowRight size={15} /></Link></div>
    </section>

    {bookId && detailStatus && <ProgressDetails bookId={bookId} chapterId={chapterId} material={material} status={detailStatus} />}

    <Breakdown rows={coverage} selectedBookId={bookId} material={material} />
  </div>;
}

function Breakdown({rows, selectedBookId, material}: {rows: Coverage[]; selectedBookId: string; material: Material}) {
  if (!selectedBookId) {
    const books = Array.from(new Map(rows.map(row => [row.book_id, row.book_title])).entries());
    return <section><h2 className="mb-3 text-lg font-semibold">Progress by book</h2><div className="grid gap-3 sm:grid-cols-2">{books.map(([id, title]) => { const stats = aggregate(rows.filter(row => row.book_id === id), material); return <BookRow key={id} title={title} stats={stats} />; })}</div></section>;
  }
  const chapterRows = sortCoverage(rows.filter(row => String(row.book_id) === selectedBookId));
  return <section><h2 className="mb-3 text-lg font-semibold">Progress by chapter</h2><div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">{chapterRows.map(row => <ChapterRow key={row.chapter_id} row={row} material={material} />)}</div></section>;
}

type Stats = {manualTotal: number; known: number; unknown: number; unmarked: number; reviewedPercent: number; practiceTotal: number; practiced: number; neverTouched: number; mastered: number; weak: number; masteryPercent: number; exampleSetsMastered: number; kanjiTotal: number};
function aggregate(rows: Coverage[], material: Material): Stats {
  const manualTotal = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_total : row.kanji_example_total), 0);
  const known = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_known : row.kanji_example_known), 0);
  const unknown = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_unknown : row.kanji_example_unknown), 0);
  const practiceTotal = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_total : material === "kanji_examples" ? row.kanji_example_total : row.kanji_total), 0);
  const practiced = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_practiced : material === "kanji_examples" ? row.kanji_example_practiced : row.kanji_practiced), 0);
  const mastered = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_mastered : material === "kanji_examples" ? row.kanji_example_mastered : row.kanji_mastered), 0);
  const weak = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_weak : material === "kanji_examples" ? row.kanji_example_weak : row.kanji_weak), 0);
  const exampleSetsMastered = rows.reduce((sum, row) => sum + row.kanji_example_sets_mastered, 0);
  const kanjiTotal = rows.reduce((sum, row) => sum + row.kanji_total, 0);
  return {manualTotal, known, unknown, unmarked: Math.max(manualTotal - known - unknown, 0), reviewedPercent: percentage(known + unknown, manualTotal), practiceTotal, practiced, neverTouched: Math.max(practiceTotal - practiced, 0), mastered, weak, masteryPercent: percentage(mastered, practiceTotal), exampleSetsMastered, kanjiTotal};
}

function materialName(material: Material) { return material === "vocabulary" ? "Vocabulary words" : material === "kanji_examples" ? "Kanji example words" : "Kanji characters"; }

function sortCoverage(rows: Coverage[]) {
  return [...rows].sort((a, b) =>
    a.book_title.localeCompare(b.book_title, undefined, { numeric: true }) ||
    String(a.chapter_part ?? "").localeCompare(String(b.chapter_part ?? ""), undefined, { numeric: true }) ||
    a.chapter_number - b.chapter_number ||
    a.chapter_sort_order - b.chapter_sort_order ||
    a.chapter_id - b.chapter_id
  );
}

function Metric({label, value, icon, tone}: {label: string; value: number; icon?: React.ReactNode; tone?: "known" | "unknown"}) {
  return <div className={`rounded-xl p-3 ${tone === "known" ? "bg-green-50 text-moss" : tone === "unknown" ? "bg-red-50 text-persimmon" : "bg-stone-50 text-stone-600"}`}><span className="flex items-center gap-1 text-xs font-medium">{icon}{label}</span><strong className="mt-2 block text-2xl">{value}</strong></div>;
}

function BookRow({title, stats}: {title: string; stats: Stats}) {
  return <div className="rounded-xl border border-stone-200 bg-white p-4"><h3 className="font-semibold">{title}</h3><div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm"><BookMetric label="Touched" value={stats.practiced} total={stats.practiceTotal} /><BookMetric label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} /><BookMetric label="Weak" value={stats.weak} total={stats.practiceTotal} alert /><BookMetric label="Mastered" value={stats.mastered} total={stats.practiceTotal} good /></div><div className="mt-4 border-t border-stone-200 pt-3 text-xs text-stone-500">Self-assessment: ✓ {stats.known} known · ✕ {stats.unknown} unknown · {stats.unmarked} unmarked</div></div>;
}

function ChapterRow({row, material}: {row: Coverage; material: Material}) {
  const stats = aggregate([row], material);
  const [detailStatus, setDetailStatus] = useState<DetailStatus | null>(null);
  const toggle = (status: DetailStatus) => setDetailStatus(current => current === status ? null : status);
  return <div className="border-b border-stone-200 p-4 last:border-0"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold">Lesson {row.chapter_number}: {row.chapter_title}</p><p className="text-xs text-stone-500">{stats.practiceTotal} total · ✓ {stats.known} · ✕ {stats.unknown} · unmarked {stats.unmarked}</p></div><span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{stats.reviewedPercent}% self-assessed</span></div><div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4"><Ratio label="Touched" value={stats.practiced} total={stats.practiceTotal} tone="neutral" compact /><Ratio label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} tone="neutral" compact selected={detailStatus === "new"} onClick={() => toggle("new")} /><Ratio label="Weak" value={stats.weak} total={stats.practiceTotal} tone="weak" compact selected={detailStatus === "weak"} onClick={() => toggle("weak")} /><Ratio label="Mastered" value={stats.mastered} total={stats.practiceTotal} tone="mastered" compact selected={detailStatus === "mastered"} onClick={() => toggle("mastered")} /></div>{detailStatus && <div className="mt-5 border-t border-stone-200 pt-5"><ProgressDetails bookId={String(row.book_id)} chapterId={String(row.chapter_id)} material={material} status={detailStatus} /></div>}</div>;
}

function Ratio({label, value, total, tone, compact = false, onClick, selected = false}: {label: string; value: number; total: number; tone: "neutral" | "weak" | "mastered"; compact?: boolean; onClick?: () => void; selected?: boolean}) {
  const percent = percentage(value, total);
  const style = tone === "weak" ? "bg-red-50 text-persimmon" : tone === "mastered" ? "bg-green-50 text-moss" : "bg-stone-50 text-ink";
  const className = `w-full rounded-lg text-left ${compact ? "p-2" : "p-3"} ${style} ${onClick ? "cursor-pointer transition hover:ring-2 hover:ring-moss/30" : ""} ${selected ? "ring-2 ring-moss" : ""}`;
  const content = <><span className="block text-xs font-medium opacity-70">{label}</span><strong className={`${compact ? "text-base" : "text-xl"}`}>{value}/{total}</strong><span className="ml-1 text-xs font-semibold">{percent}%</span></>;
  return onClick ? <button type="button" aria-pressed={selected} onClick={onClick} className={className}>{content}</button> : <div className={className}>{content}</div>;
}

function ProgressDetails({bookId, chapterId, material, status}: {bookId: string; chapterId: string; material: Material; status: DetailStatus}) {
  const [result, setResult] = useState<ProgressDetailResult>({items: [], total: 0, page: 1, page_size: 50});
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { const timer = setTimeout(() => setDebouncedSearch(search), 250); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({book_id: bookId, material, status, page: String(page), page_size: "50"});
    if (chapterId) query.set("chapter_id", chapterId);
    if (debouncedSearch) query.set("search", debouncedSearch);
    setLoading(true); setError("");
    api<ProgressDetailResult>(`/progress/items?${query}`).then(data => { if (active) setResult(data); }).catch(reason => { if (active) setError(String(reason)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [bookId, chapterId, material, status, debouncedSearch, page]);
  useEffect(() => { setPage(1); }, [bookId, chapterId, material, status, debouncedSearch]);
  const lastPage = Math.max(1, Math.ceil(result.total / result.page_size));
  const title = status === "new" ? "Never touched" : status === "weak" ? "Weak" : "Mastered";
  return <section className="space-y-3"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">{title} content</h2><p className="text-sm text-stone-500">{result.total} matching {materialName(material).toLowerCase()}</p></div><input aria-label="Filter progress details" value={search} onChange={event => setSearch(event.target.value)} placeholder="Filter content…" className="min-h-11 rounded-lg border border-stone-300 bg-white px-3 sm:w-72" /></div>{error && <ErrorState className="rounded-xl border border-persimmon bg-white p-4 text-persimmon">{error}</ErrorState>}{loading ? <LoadingState className="h-40 animate-pulse rounded-xl bg-stone-100" /> : <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white"><table className="w-full min-w-[46rem] text-left text-sm"><thead className="bg-stone-100 text-xs font-semibold uppercase tracking-wide text-stone-500"><tr><th className="px-4 py-3">Content</th><th className="px-4 py-3">Meaning</th><th className="px-4 py-3">Lesson</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Study</th></tr></thead><tbody>{result.items.map(item => <tr key={`${material}-${item.id}`} className="border-t border-stone-100"><td className="px-4 py-3"><span className="font-semibold">{item.content}</span>{item.reading && <span className="ml-2 text-moss">{item.reading}</span>}</td><td className="px-4 py-3 text-stone-600">{item.meaning}</td><td className="px-4 py-3"><span className="font-medium">{item.chapter_part != null ? `Part ${item.chapter_part} · ` : ""}Lesson {item.chapter_number}</span><span className="block text-xs text-stone-500">{item.chapter_title}</span></td><td className="px-4 py-3 capitalize">{item.status}</td><td className="px-4 py-3 text-right"><Link target="_blank" rel="noopener noreferrer" href={`/study/${item.study_kind}/${encodeURIComponent(item.study_source_id)}`} className="inline-flex min-h-9 items-center gap-1 rounded-lg border border-moss px-3 font-semibold text-moss">Study <ArrowRight size={15} /></Link></td></tr>)}</tbody></table>{result.items.length === 0 && <EmptyState className="p-8 text-center text-stone-500">No matching content.</EmptyState>}</div>}{lastPage > 1 && <nav aria-label="Progress detail pages" className="flex items-center justify-center gap-4"><button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)} className="min-h-10 rounded border px-3 disabled:opacity-40">Previous</button><span className="text-sm">{page} / {lastPage}</span><button type="button" disabled={page >= lastPage} onClick={() => setPage(value => value + 1)} className="min-h-10 rounded border px-3 disabled:opacity-40">Next</button></nav>}</section>;
}

function BookMetric({label, value, total, alert = false, good = false}: {label: string; value: number; total: number; alert?: boolean; good?: boolean}) {
  return <div><div className="flex justify-between gap-2"><span className="text-stone-600">{label}</span><strong className={alert ? "text-persimmon" : good ? "text-moss" : ""}>{percentage(value, total)}%</strong></div><p className="text-xs text-stone-400">{value} of {total}</p></div>;
}

function percentage(value: number, total: number) { return total ? Math.round(value / total * 100) : 0; }
