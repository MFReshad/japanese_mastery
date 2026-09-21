"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronLeft, ChevronRight, Play } from "lucide-react";
import { api, StudyDetail, StudyKind } from "@/lib/api";

export function StudyDetailView({ kind, sourceId }: { kind: StudyKind; sourceId: string }) {
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setDetail(null); setError("");
    api<StudyDetail>(`/study/${kind}/${encodeURIComponent(sourceId)}`)
      .then((value) => { if (active) setDetail(value); })
      .catch((reason) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [kind, sourceId]);

  if (error) return <p role="alert" className="mx-auto max-w-3xl py-12 text-persimmon">{error}</p>;
  if (!detail) return <p className="mx-auto max-w-3xl py-12 text-stone-500">Loading...</p>;

  const backQuery = new URLSearchParams({ book: String(detail.book_id), kind });
  if (detail.chapter_id !== null) backQuery.set("chapter", String(detail.chapter_id));
  if (detail.part !== null) backQuery.set("part", String(detail.part));
  const backHref = `/study?${backQuery}`;
  const practiceQuery = new URLSearchParams({ practice_type: kind, book_id: String(detail.book_id), source_entry_id: String(detail.source_entry_id) });
  if (detail.chapter_id !== null) practiceQuery.set("chapter_id", String(detail.chapter_id));
  const chapterQuery = new URLSearchParams({ practice_type: kind, book_id: String(detail.book_id) });
  if (detail.chapter_id !== null) chapterQuery.set("chapter_id", String(detail.chapter_id));
  const meanings = detail.meanings_as_printed.length ? detail.meanings_as_printed : [detail.meaning_as_printed];
  const previous = detail.previous_source_id ? `/study/${kind}/${encodeURIComponent(detail.previous_source_id)}` : null;
  const next = detail.next_source_id ? `/study/${kind}/${encodeURIComponent(detail.next_source_id)}` : null;
  const nextChapter = detail.next_chapter;

  return <article className="mx-auto max-w-3xl pb-40 sm:pb-12">
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 text-sm">
      <Link href={backHref} className="inline-flex min-h-10 items-center gap-2 font-medium text-moss"><ArrowLeft size={17} /> Back to chapter</Link>
      <span className="text-stone-500">{detail.position} / {detail.lesson_count}</span>
    </div>

    <header className="border-b border-stone-300 pb-7">
      <p className="mb-3 text-sm font-medium text-moss">{detail.book_title}{detail.part !== null ? ` · Part ${detail.part}` : ""}{detail.chapter_number !== null ? ` · Lesson ${detail.chapter_number}` : ""}</p>
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0 flex-1">
          {kind === "kanji" ? <h1 lang="ja" className="text-8xl font-semibold leading-none text-ink sm:text-9xl">{detail.character}</h1>
            : <><h1 lang="ja" className="break-words text-5xl font-semibold leading-tight text-ink sm:text-6xl">{detail.expression_as_printed}</h1><p lang="ja" className="mt-3 break-words text-2xl text-stone-600">{detail.reading_as_printed || "Reading not listed"}</p></>}
        </div>
        <div className="text-right text-sm text-stone-500">
          <p>{detail.chapter_title}</p>
          <p>Item {detail.item_order}</p>
          {kind === "kanji" && detail.entry_number_as_printed !== null && detail.entry_number_as_printed !== undefined && <p>Entry {detail.entry_number_as_printed}</p>}
          {kind === "kanji" && detail.stroke_count_as_printed !== null && detail.stroke_count_as_printed !== undefined && <p>{detail.stroke_count_as_printed} strokes</p>}
        </div>
      </div>
      {kind === "kanji" && <p className={`mt-5 inline-block border-l-2 pl-3 text-sm ${detail.uncertain ? "border-persimmon text-persimmon" : "border-stone-300 text-stone-500"}`}>{detail.uncertain ? "Uncertain source transcription" : "No uncertainty flagged"}</p>}
    </header>

    <section className="py-7">
      <h2 className="mb-3 text-sm font-semibold uppercase text-stone-500">Meanings</h2>
      <ul className="space-y-2">{meanings.map((meaning, index) => <li key={`${index}-${meaning}`} className="break-words text-xl leading-relaxed">{meaning}</li>)}</ul>
    </section>

    {kind === "kanji" && <>
      <div className="grid gap-6 border-y border-stone-200 py-7 sm:grid-cols-2">
        <ReadingList label="Onyomi" readings={detail.onyomi_as_printed ?? []} />
        <ReadingList label="Kunyomi" readings={detail.kunyomi_as_printed ?? []} />
      </div>
      <section className="py-7">
        <div className="mb-4 flex items-baseline justify-between gap-3"><h2 className="text-sm font-semibold uppercase text-stone-500">Examples</h2><span className="text-sm text-stone-500">{detail.examples?.length ?? 0}</span></div>
        {detail.examples?.length ? <div className="grid gap-3 sm:grid-cols-2">{detail.examples.map((example, index) => <div key={`${index}-${example.word}`} className="rounded border border-stone-200 bg-white p-4">
          <p lang="ja" className="break-words text-2xl font-semibold">{example.word}</p>
          <p lang="ja" className="mt-1 break-words text-base text-moss">{example.reading}</p>
          <p className="mt-3 break-words text-stone-700">{example.meaning}</p>
        </div>)}</div> : <p className="text-stone-500">No examples in this source.</p>}
      </section>
    </>}

    {detail.notes && <section className="border-t border-stone-200 py-6"><h2 className="mb-2 text-sm font-semibold uppercase text-stone-500">Notes</h2><p className="whitespace-pre-wrap break-words leading-relaxed">{detail.notes}</p></section>}
    {(detail.source_page !== null || detail.source_book_page !== null && detail.source_book_page !== undefined) && <div className="border-t border-stone-200 py-5 text-sm text-stone-500">
      {detail.source_page !== null && <span>Source page {detail.source_page}</span>}
      {detail.source_page !== null && detail.source_book_page !== null && detail.source_book_page !== undefined && <span> · </span>}
      {detail.source_book_page !== null && detail.source_book_page !== undefined && <span>Book page {detail.source_book_page}</span>}
    </div>}

    <div className="flex flex-wrap gap-3 border-t border-stone-200 py-6">
      <Link href={`/practice?${practiceQuery}`} className="inline-flex min-h-11 items-center gap-2 bg-moss px-4 font-medium text-white"><Play size={17} /> Practice this item</Link>
      {detail.chapter_id !== null && <Link href={`/practice?${chapterQuery}`} className="inline-flex min-h-11 items-center gap-2 border border-moss px-4 font-medium text-moss"><Play size={17} /> Practice this chapter</Link>}
    </div>

    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-stone-300 bg-paper/95 p-3 backdrop-blur sm:static sm:mt-5 sm:bg-transparent sm:p-0">
      <nav aria-label="Study item navigation" className="grid grid-cols-2">
        {previous ? <Link href={previous} className="inline-flex min-h-12 items-center gap-2 font-medium text-moss"><ChevronLeft size={20} /> Previous</Link> : <span />}
        {next ? <Link href={next} className="inline-flex min-h-12 items-center justify-end gap-2 font-medium text-moss">Next <ChevronRight size={20} /></Link> : <span />}
      </nav>
      {nextChapter && <Link href={`/study/${kind}/${encodeURIComponent(nextChapter.first_source_id)}`}
        className="mt-1 flex min-h-12 items-center justify-between gap-3 border-t border-stone-200 px-1 font-medium text-moss">
        <span>Next Chapter <span className="ml-1 text-sm font-normal text-stone-600">{nextChapter.part !== null ? `Part ${nextChapter.part} · ` : ""}Lesson {nextChapter.chapter_number}</span></span>
        <ChevronRight size={20} className="shrink-0" />
      </Link>}
    </div>
  </article>;
}

function ReadingList({ label, readings }: { label: string; readings: string[] }) {
  return <section><h2 className="mb-3 text-sm font-semibold uppercase text-stone-500">{label}</h2>
    {readings.length ? <ul className="flex flex-wrap gap-2">{readings.map((reading, index) => <li key={`${index}-${reading}`} lang="ja" className="rounded border border-stone-300 bg-white px-3 py-2 text-lg">{reading}</li>)}</ul>
      : <p className="text-stone-500">Not listed</p>}
  </section>;
}
