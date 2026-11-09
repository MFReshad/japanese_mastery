"use client";

import Link from "next/link";
import { ArrowRight, Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Coverage } from "@/lib/api";

type Material = "vocabulary" | "kanji";

export default function ProgressPage() {
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [bookId, setBookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [material, setMaterial] = useState<Material>("vocabulary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { api<Coverage[]>("/progress/books").then(setCoverage).catch(reason => setError(String(reason))).finally(() => setLoading(false)); }, []);

  const books = useMemo(() => Array.from(new Map(coverage.map(row => [row.book_id, row.book_title])).entries()).map(([id, title]) => ({id, title})), [coverage]);
  const chapters = coverage.filter(row => !bookId || String(row.book_id) === bookId);
  const scoped = chapters.filter(row => !chapterId || String(row.chapter_id) === chapterId);
  const stats = aggregate(scoped, material);
  const scopeName = chapterId ? chapters.find(row => String(row.chapter_id) === chapterId)?.chapter_title : bookId ? books.find(book => String(book.id) === bookId)?.title : "All books";

  if (loading) return <div className="mx-auto h-96 max-w-5xl animate-pulse rounded-2xl bg-stone-100" />;

  return <div className="mx-auto max-w-5xl space-y-6 pb-12">
    <header><p className="text-sm font-semibold uppercase tracking-[0.14em] text-moss">Progress</p><h1 className="mt-1 text-3xl font-semibold">Learning status</h1><p className="mt-2 text-stone-600">Choose exactly what you want to measure.</p></header>
    {error && <p role="alert" className="rounded-xl border border-persimmon bg-white p-4 text-persimmon">{error}</p>}

    <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">Filters</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-medium">Book<select value={bookId} onChange={event => { setBookId(event.target.value); setChapterId(""); }} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="">All books</option>{books.map(book => <option key={book.id} value={book.id}>{book.title}</option>)}</select></label>
        <label className="text-sm font-medium">Chapter<select value={chapterId} onChange={event => setChapterId(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="">All chapters</option>{chapters.map(row => <option key={row.chapter_id} value={row.chapter_id}>Lesson {row.chapter_number}: {row.chapter_title}</option>)}</select></label>
        <label className="text-sm font-medium">Material<select value={material} onChange={event => setMaterial(event.target.value as Material)} className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3"><option value="vocabulary">Vocabulary words</option><option value="kanji">Kanji example words</option></select></label>
      </div>
    </section>

    <section className="rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="border-b border-stone-200 p-5 sm:p-6"><p className="text-sm font-medium text-moss">{scopeName}</p><h2 className="mt-1 text-2xl font-semibold">{material === "vocabulary" ? "Vocabulary words" : "Kanji example words"}</h2></div>
      <div className="grid md:grid-cols-2 md:divide-x md:divide-stone-200">
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between"><div><h3 className="font-semibold">Your self-assessment</h3><p className="mt-1 text-sm text-stone-500">Based only on your ✓ and ✕ marks</p></div><span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{stats.reviewedPercent}% marked</span></div>
          <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-stone-100"><div className="bg-moss" style={{width: `${percentage(stats.known, stats.manualTotal)}%`}} /><div className="bg-persimmon" style={{width: `${percentage(stats.unknown, stats.manualTotal)}%`}} /></div>
          <div className="mt-5 grid grid-cols-3 gap-2"><Metric label="Known" value={stats.known} icon={<Check size={17} />} tone="known" /><Metric label="Unknown" value={stats.unknown} icon={<X size={17} />} tone="unknown" /><Metric label="Not marked" value={stats.unmarked} /></div>
          <p className="mt-4 text-xs text-stone-500">Total: {stats.manualTotal} {material === "vocabulary" ? "vocabulary words" : "kanji example words"}</p>
        </div>
        <div className="border-t border-stone-200 p-5 md:border-t-0 sm:p-6">
          <h3 className="font-semibold">Automatic practice result</h3><p className="mt-1 text-sm text-stone-500">Ratios use all {stats.practiceTotal} {material === "vocabulary" ? "vocabulary words" : "kanji characters"} in this selection</p>
          <div className="mt-5 grid grid-cols-2 gap-2"><Ratio label="Touched" value={stats.practiced} total={stats.practiceTotal} tone="neutral" /><Ratio label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} tone="neutral" /><Ratio label="Weak" value={stats.weak} total={stats.practiceTotal} tone="weak" /><Ratio label="Mastered" value={stats.mastered} total={stats.practiceTotal} tone="mastered" /></div>
          <div className="mt-5 h-3 overflow-hidden rounded-full bg-stone-100"><div className="h-full bg-moss" style={{width: `${stats.masteryPercent}%`}} /></div>
          <p className="mt-2 text-xs text-stone-500">Mastery: {stats.mastered}/{stats.practiceTotal} · {stats.masteryPercent}%</p>
        </div>
      </div>
      <div className="grid gap-2 border-t border-stone-200 p-4 sm:grid-cols-3 sm:p-5"><Link href={`/practice?practice_type=${material === "vocabulary" ? "vocabulary" : "kanji_example_words"}&condition=unknown${bookId ? `&book_id=${bookId}` : ""}${chapterId ? `&chapter_id=${chapterId}` : ""}`} className="flex min-h-11 items-center justify-center rounded-lg border border-persimmon/40 text-sm font-semibold text-persimmon">Practice ✕ unknown</Link><Link href={`/practice?practice_type=${material === "vocabulary" ? "vocabulary" : "kanji_example_words"}&condition=weak${bookId ? `&book_id=${bookId}` : ""}${chapterId ? `&chapter_id=${chapterId}` : ""}`} className="flex min-h-11 items-center justify-center rounded-lg bg-ink text-sm font-semibold text-white">Practice weak</Link><Link href={`/study?${new URLSearchParams({...(bookId ? {book: bookId} : {}), ...(chapterId ? {chapter: chapterId} : {}), kind: material})}`} className="flex min-h-11 items-center justify-center gap-2 rounded-lg border border-stone-300 text-sm font-semibold">Open study <ArrowRight size={15} /></Link></div>
    </section>

    <Breakdown rows={coverage} selectedBookId={bookId} material={material} />
  </div>;
}

function Breakdown({rows, selectedBookId, material}: {rows: Coverage[]; selectedBookId: string; material: Material}) {
  if (!selectedBookId) {
    const books = Array.from(new Map(rows.map(row => [row.book_id, row.book_title])).entries());
    return <section><h2 className="mb-3 text-lg font-semibold">Progress by book</h2><div className="grid gap-3 sm:grid-cols-2">{books.map(([id, title]) => { const stats = aggregate(rows.filter(row => row.book_id === id), material); return <BookRow key={id} title={title} stats={stats} />; })}</div></section>;
  }
  const chapterRows = rows.filter(row => String(row.book_id) === selectedBookId);
  return <section><h2 className="mb-3 text-lg font-semibold">Progress by chapter</h2><div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">{chapterRows.map(row => <ChapterRow key={row.chapter_id} row={row} material={material} />)}</div></section>;
}

type Stats = {manualTotal: number; known: number; unknown: number; unmarked: number; reviewedPercent: number; practiceTotal: number; practiced: number; neverTouched: number; mastered: number; weak: number; masteryPercent: number};
function aggregate(rows: Coverage[], material: Material): Stats {
  const manualTotal = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_total : row.kanji_example_total), 0);
  const known = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_known : row.kanji_example_known), 0);
  const unknown = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_unknown : row.kanji_example_unknown), 0);
  const practiceTotal = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_total : row.kanji_total), 0);
  const practiced = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_practiced : row.kanji_practiced), 0);
  const mastered = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_mastered : row.kanji_mastered), 0);
  const weak = rows.reduce((sum, row) => sum + (material === "vocabulary" ? row.vocabulary_weak : row.kanji_weak), 0);
  return {manualTotal, known, unknown, unmarked: Math.max(manualTotal - known - unknown, 0), reviewedPercent: percentage(known + unknown, manualTotal), practiceTotal, practiced, neverTouched: Math.max(practiceTotal - practiced, 0), mastered, weak, masteryPercent: percentage(mastered, practiceTotal)};
}

function Metric({label, value, icon, tone}: {label: string; value: number; icon?: React.ReactNode; tone?: "known" | "unknown"}) {
  return <div className={`rounded-xl p-3 ${tone === "known" ? "bg-green-50 text-moss" : tone === "unknown" ? "bg-red-50 text-persimmon" : "bg-stone-50 text-stone-600"}`}><span className="flex items-center gap-1 text-xs font-medium">{icon}{label}</span><strong className="mt-2 block text-2xl">{value}</strong></div>;
}

function BookRow({title, stats}: {title: string; stats: Stats}) {
  return <div className="rounded-xl border border-stone-200 bg-white p-4"><h3 className="font-semibold">{title}</h3><div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm"><BookMetric label="Touched" value={stats.practiced} total={stats.practiceTotal} /><BookMetric label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} /><BookMetric label="Weak" value={stats.weak} total={stats.practiceTotal} alert /><BookMetric label="Mastered" value={stats.mastered} total={stats.practiceTotal} good /></div><div className="mt-4 border-t border-stone-200 pt-3 text-xs text-stone-500">Self-assessment: ✓ {stats.known} known · ✕ {stats.unknown} unknown · {stats.unmarked} unmarked</div></div>;
}

function ChapterRow({row, material}: {row: Coverage; material: Material}) {
  const stats = aggregate([row], material);
  return <div className="border-b border-stone-200 p-4 last:border-0"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold">Lesson {row.chapter_number}: {row.chapter_title}</p><p className="text-xs text-stone-500">{stats.practiceTotal} total · ✓ {stats.known} · ✕ {stats.unknown} · unmarked {stats.unmarked}</p></div><span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{stats.reviewedPercent}% self-assessed</span></div><div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4"><Ratio label="Touched" value={stats.practiced} total={stats.practiceTotal} tone="neutral" compact /><Ratio label="Never touched" value={stats.neverTouched} total={stats.practiceTotal} tone="neutral" compact /><Ratio label="Weak" value={stats.weak} total={stats.practiceTotal} tone="weak" compact /><Ratio label="Mastered" value={stats.mastered} total={stats.practiceTotal} tone="mastered" compact /></div></div>;
}

function Ratio({label, value, total, tone, compact = false}: {label: string; value: number; total: number; tone: "neutral" | "weak" | "mastered"; compact?: boolean}) {
  const percent = percentage(value, total);
  const style = tone === "weak" ? "bg-red-50 text-persimmon" : tone === "mastered" ? "bg-green-50 text-moss" : "bg-stone-50 text-ink";
  return <div className={`rounded-lg ${compact ? "p-2" : "p-3"} ${style}`}><span className="block text-xs font-medium opacity-70">{label}</span><strong className={`${compact ? "text-base" : "text-xl"}`}>{value}/{total}</strong><span className="ml-1 text-xs font-semibold">{percent}%</span></div>;
}

function BookMetric({label, value, total, alert = false, good = false}: {label: string; value: number; total: number; alert?: boolean; good?: boolean}) {
  return <div><div className="flex justify-between gap-2"><span className="text-stone-600">{label}</span><strong className={alert ? "text-persimmon" : good ? "text-moss" : ""}>{percentage(value, total)}%</strong></div><p className="text-xs text-stone-400">{value} of {total}</p></div>;
}

function percentage(value: number, total: number) { return total ? Math.round(value / total * 100) : 0; }
