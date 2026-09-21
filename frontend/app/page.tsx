"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Progress } from "@/lib/api";

export default function HomePage() {
  const [progress, setProgress] = useState<Progress[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api<Progress[]>("/progress").then(setProgress).catch(() => setProgress([])).finally(() => setLoading(false)); }, []);
  const vocab = progress.find((p) => p.item_type === "vocabulary");
  const kanji = progress.find((p) => p.item_type === "kanji");
  const weak = progress.reduce((sum, p) => sum + p.weak, 0);
  const never = progress.reduce((sum, p) => sum + p.new, 0);
  return (
    <div className="space-y-6">
      {loading ? <section aria-label="Loading overview" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="h-24 animate-pulse rounded border border-stone-200 bg-stone-100" />)}</section> : <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total Vocabulary" value={vocab?.total ?? 0} />
        <Stat label="Total Kanji" value={kanji?.total ?? 0} />
        <Stat label="Weak Items" value={weak} accent />
        <Stat label="Never Practiced" value={never} />
      </section>}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Action href="/practice" label="Start Practice" />
        <Action href="/practice?mode=wrong" label="Wrong Items" />
        <Action href="/practice?mode=weak" label="Weak Items" />
        <Action href="/library" label="Library" />
        <Action href="/manage" label="Manage Data" />
      </section>
      <section className="rounded border border-stone-200 bg-white p-4">
        <h1 className="mb-3 text-xl font-semibold">No-gap Review</h1>
        <div className="grid gap-3 sm:grid-cols-4">
          <Action href="/practice?mode=never_practiced" label="Never Practiced" compact />
          <Action href="/practice?mode=weak" label="Weak" compact />
          <Action href="/practice?mode=wrong" label="Frequently Wrong" compact />
          <Action href="/practice?mode=mastery_review" label="Not Mastered" compact />
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, accent = false }: { label: string; value: number; accent?: boolean }) {
  return <div className="rounded border border-stone-200 bg-white p-4"><div className="text-sm text-stone-500">{label}</div><div className={`text-3xl font-semibold ${accent ? "text-persimmon" : ""}`}>{value}</div></div>;
}

function Action({ href, label, compact = false }: { href: string; label: string; compact?: boolean }) {
  return <Link href={href} className={`rounded bg-moss text-center font-medium text-white hover:bg-ink ${compact ? "px-3 py-3 text-sm" : "px-4 py-5"}`}>{label}</Link>;
}
