"use client";

import { useEffect, useState } from "react";
import { api, Coverage, Progress } from "@/lib/api";

export default function ProgressPage() {
  const [progress, setProgress] = useState<Progress[]>([]);
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api<Progress[]>("/progress"), api<Coverage[]>("/progress/books")]).then(([p, c]) => { setProgress(p); setCoverage(c); }).catch((reason) => setError(String(reason))).finally(() => setLoading(false)); }, []);
  return (
    <div className="space-y-6">
      {loading && <div aria-label="Loading progress" className="space-y-3"><div className="h-36 animate-pulse bg-stone-100" /><div className="h-64 animate-pulse bg-stone-100" /></div>}
      {error && <p role="alert" className="text-persimmon">{error}</p>}
      {!loading && <>
      <div className="grid gap-3 md:grid-cols-2">
        {progress.map((p) => <section key={p.item_type} className="rounded border border-stone-200 bg-white p-4"><h2 className="mb-3 text-xl font-semibold capitalize">{p.item_type}</h2><div className="grid grid-cols-2 gap-2 text-sm">{["total", "new", "learning", "weak", "mastered"].map((k) => <div key={k} className="rounded bg-stone-50 p-3"><div className="text-stone-500">{k}</div><div className="text-2xl font-semibold">{p[k as keyof Progress]}</div></div>)}</div></section>)}
      </div>
      <section className="rounded border border-stone-200 bg-white p-4">
        <h2 className="mb-3 text-xl font-semibold">Book Coverage</h2>
        <div className="space-y-2">{coverage.map((c) => <div key={`${c.book_id}-${c.chapter_id}`} className="grid gap-2 rounded bg-stone-50 p-3 sm:grid-cols-3"><div><b>{c.book_title}</b><br />Lesson {c.chapter_number}: {c.chapter_title}</div><div>Vocabulary: {c.vocabulary_mastered_percent}%</div><div>Kanji: {c.kanji_mastered_percent}%</div></div>)}</div>
      </section>
      </>}
    </div>
  );
}
