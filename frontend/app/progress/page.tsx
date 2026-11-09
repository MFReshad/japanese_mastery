"use client";

import { useEffect, useState } from "react";
import { api, Coverage, Progress } from "@/lib/api";

export default function ProgressPage() {
  const [progress, setProgress] = useState<Progress[]>([]);
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api<Progress[]>("/progress"), api<Coverage[]>("/progress/books")]).then(([p, c]) => { setProgress(p); setCoverage(c); }).catch((reason) => setError(String(reason))).finally(() => setLoading(false)); }, []);
  const vocabularyLacking = [...coverage].sort((a, b) => lackingScore(b, "vocabulary") - lackingScore(a, "vocabulary"));
  const kanjiLacking = [...coverage].sort((a, b) => lackingScore(b, "kanji") - lackingScore(a, "kanji"));
  return (
    <div className="space-y-6">
      {loading && <div aria-label="Loading progress" className="space-y-3"><div className="h-36 animate-pulse bg-stone-100" /><div className="h-64 animate-pulse bg-stone-100" /></div>}
      {error && <p role="alert" className="text-persimmon">{error}</p>}
      {!loading && <>
      <div className="grid gap-3 md:grid-cols-2">
        {progress.map((p) => <section key={p.item_type} className="rounded border border-stone-200 bg-white p-4"><h2 className="mb-3 text-xl font-semibold capitalize">{p.item_type}</h2><div className="grid grid-cols-2 gap-2 text-sm">{["total", "new", "learning", "weak", "mastered"].map((k) => <div key={k} className="rounded bg-stone-50 p-3"><div className="text-stone-500">{k}</div><div className="text-2xl font-semibold">{p[k as keyof Progress]}</div></div>)}</div></section>)}
      </div>
      <section className="rounded border border-stone-200 bg-white p-4">
        <h2 className="mb-3 text-xl font-semibold">Most Lacking Chapters</h2>
        <div className="grid gap-5 lg:grid-cols-2"><LackingList title="Vocabulary" rows={vocabularyLacking} kind="vocabulary" /><LackingList title="Kanji example words" rows={kanjiLacking} kind="kanji" /></div>
      </section>
      <section className="rounded border border-stone-200 bg-white p-4">
        <h2 className="mb-3 text-xl font-semibold">Book Coverage</h2>
        <div className="space-y-2">{coverage.map((c) => <div key={`${c.book_id}-${c.chapter_id}`} className="grid gap-2 rounded bg-stone-50 p-3 sm:grid-cols-3"><div><b>{c.book_title}</b><br />Lesson {c.chapter_number}: {c.chapter_title}</div><div>Vocabulary: {c.vocabulary_mastered_percent}%</div><div>Kanji: {c.kanji_mastered_percent}%</div></div>)}</div>
      </section>
      </>}
    </div>
  );
}

function lackingScore(row: Coverage, kind: "vocabulary" | "kanji") {
  if (kind === "vocabulary") return row.vocabulary_total ? (row.vocabulary_unknown + row.vocabulary_weak) / row.vocabulary_total : 0;
  return row.kanji_example_total ? (row.kanji_example_unknown + row.kanji_weak) / row.kanji_example_total : 0;
}

function LackingList({title, rows, kind}: {title: string; rows: Coverage[]; kind: "vocabulary" | "kanji"}) {
  return <div><h3 className="mb-2 font-semibold">{title}</h3><div className="space-y-2">{rows.slice(0, 10).map(row => <a key={row.chapter_id} href={`/study?book=${row.book_id}&chapter=${row.chapter_id}&kind=${kind}`} className="block rounded bg-stone-50 p-3 hover:bg-stone-100"><div className="flex justify-between gap-3"><span><b>{row.book_title}</b> · Lesson {row.chapter_number}</span><b>{Math.round(lackingScore(row, kind) * 100)}%</b></div><p className="mt-1 text-sm text-stone-600">{row.chapter_title} · {kind === "vocabulary" ? `${row.vocabulary_unknown} ✕, ${row.vocabulary_weak} weak` : `${row.kanji_example_unknown} ✕ examples, ${row.kanji_weak} weak kanji`}</p></a>)}</div></div>;
}
