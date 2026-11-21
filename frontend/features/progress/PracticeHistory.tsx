"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, PracticeHistoryAnswer, PracticeHistoryDetail, PracticeHistoryPage, PracticeHistorySession } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";

const pageSize = 50;
type AnswerSortKey = "position" | "question" | "source" | "content" | "result" | "note" | "study";
type SortDirection = "asc" | "desc";

export function PracticeHistory() {
  const [sessions, setSessions] = useState<PracticeHistorySession[]>([]);
  const [total, setTotal] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, PracticeHistoryDetail>>({});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [detailLoading, setDetailLoading] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<PracticeHistoryPage>(`/practice/history?limit=${pageSize}&offset=0`)
      .then(page => { setSessions(page.sessions); setTotal(page.total); })
      .catch(reason => setError(String(reason)))
      .finally(() => setLoading(false));
  }, []);

  async function loadMore() {
    setLoadingMore(true); setError("");
    try {
      const page = await api<PracticeHistoryPage>(`/practice/history?limit=${pageSize}&offset=${sessions.length}`);
      setSessions(current => [...current, ...page.sessions]);
      setTotal(page.total);
    } catch (reason) { setError(String(reason)); }
    finally { setLoadingMore(false); }
  }

  async function toggle(sessionId: number) {
    if (expanded === sessionId) { setExpanded(null); return; }
    setExpanded(sessionId);
    if (details[sessionId]) return;
    setDetailLoading(sessionId); setError("");
    try {
      const detail = await api<PracticeHistoryDetail>(`/practice/history/${sessionId}`);
      setDetails(current => ({...current, [sessionId]: detail}));
    } catch (reason) { setError(String(reason)); }
    finally { setDetailLoading(null); }
  }

  if (loading) return <LoadingState label="Loading practice history" className="h-72 animate-pulse rounded-2xl bg-stone-100" />;

  return <section className="space-y-4">
    {error && <ErrorState className="rounded-xl border border-persimmon bg-white p-4 text-persimmon">{error}</ErrorState>}
    {!sessions.length ? <EmptyState className="rounded-2xl border border-dashed border-stone-300 p-12 text-center text-stone-500">No practice sessions yet.</EmptyState> :
      <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
        <table className="w-full min-w-[52rem] text-left text-sm">
          <thead className="bg-stone-50 text-xs font-semibold uppercase tracking-wide text-stone-500"><tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Setup</th><th className="px-4 py-3">Questions</th><th className="px-4 py-3">Correct</th><th className="px-4 py-3">Wrong</th><th className="px-4 py-3">Status</th></tr></thead>
          <tbody>{sessions.map(session => <HistoryRows key={session.session_id} session={session} open={expanded === session.session_id} detail={details[session.session_id]} loading={detailLoading === session.session_id} toggle={() => void toggle(session.session_id)} />)}</tbody>
        </table>
      </div>}
    {sessions.length < total && <div className="text-center"><button disabled={loadingMore} onClick={() => void loadMore()} className="min-h-11 rounded-lg border border-stone-300 bg-white px-5 font-semibold disabled:opacity-50">{loadingMore ? "Loading…" : `Load more (${sessions.length} of ${total})`}</button></div>}
  </section>;
}

function HistoryRows({session, open, detail, loading, toggle}: {session: PracticeHistorySession; open: boolean; detail?: PracticeHistoryDetail; loading: boolean; toggle: () => void}) {
  const answered = session.correct_count + session.wrong_count;
  const status = session.completed_at ? "Completed" : answered ? "In progress" : "Not started";
  return <>
    <tr tabIndex={0} aria-expanded={open} onClick={toggle} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); } }} className="cursor-pointer border-t border-stone-100 hover:bg-stone-50 focus:bg-stone-50 focus:outline-none">
      <td className="px-4 py-4 font-medium">{formatDate(session.started_at)}</td>
      <td className="px-4 py-4"><div className="font-medium capitalize">{label(session.practice_type)}</div><div className="text-xs text-stone-500">{setupSummary(session)}</div></td>
      <td className="px-4 py-4">{answered}/{session.total_questions}</td>
      <td className="px-4 py-4 font-semibold text-moss">{session.correct_count}</td>
      <td className="px-4 py-4 font-semibold text-persimmon">{session.wrong_count}</td>
      <td className="px-4 py-4"><span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{status}</span></td>
    </tr>
    {open && <tr><td colSpan={6} className="border-t border-stone-200 bg-stone-50 p-4 sm:p-5">{loading ? <LoadingState label="Loading session details" className="h-40 animate-pulse rounded-xl bg-stone-100" /> : detail ? <SessionDetail detail={detail} /> : null}</td></tr>}
  </>;
}

function SessionDetail({detail}: {detail: PracticeHistoryDetail}) {
  const [search, setSearch] = useState("");
  const [result, setResult] = useState("all");
  const [content, setContent] = useState("all");
  const [book, setBook] = useState("all");
  const [chapter, setChapter] = useState("all");
  const [sort, setSort] = useState<{key: AnswerSortKey; direction: SortDirection}>({key: "position", direction: "asc"});
  const snapshot = detail.session.filter_snapshot;
  const books = unique(detail.answers, row => row.book_id, row => row.book_title);
  const chapters = unique(detail.answers.filter(row => book === "all" || String(row.book_id) === book), row => row.chapter_id, row => row.chapter_number == null ? row.chapter_title : `Lesson ${row.chapter_number}: ${row.chapter_title ?? ""}`);
  const bookNames = snapshot ? snapshot.book_ids.map(id => books.find(([value]) => value === String(id))?.[1] ?? `Book #${id}`) : [];
  const chapterNames = snapshot ? snapshot.chapter_ids.map(id => chapters.find(([value]) => value === String(id))?.[1] ?? `Lesson #${id}`) : [];
  const filtered = useMemo(() => detail.answers.filter(row => {
    const haystack = `${row.prompt} ${row.answer_primary} ${row.answer_secondary ?? ""} ${row.book_title ?? ""} ${row.chapter_title ?? ""} ${row.question_type}`.toLocaleLowerCase();
    return (!search || haystack.includes(search.toLocaleLowerCase())) && (result === "all" || (result === "unanswered" ? row.result === null : row.result === result)) && (content === "all" || row.item_type === content) && (book === "all" || String(row.book_id) === book) && (chapter === "all" || String(row.chapter_id) === chapter);
  }), [detail.answers, search, result, content, book, chapter]);
  const sorted = useMemo(() => [...filtered].sort((left, right) => {
    const comparison = compareSortValues(answerSortValue(left, sort.key), answerSortValue(right, sort.key));
    if (comparison !== 0) return sort.direction === "asc" ? comparison : -comparison;
    return left.position - right.position;
  }), [filtered, sort]);

  function changeSort(key: AnswerSortKey) {
    setSort(current => current.key === key
      ? {key, direction: current.direction === "asc" ? "desc" : "asc"}
      : {key, direction: "asc"});
  }

  return <div className="space-y-4" onClick={event => event.stopPropagation()}>
    <div className="grid gap-3 rounded-xl border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"><Info label="Practice content" value={label(detail.session.practice_type)} /><Info label="Quick preset" value={label(detail.session.mode)} /><Info label="Questions" value={snapshot ? `${snapshot.question_count == null ? "All" : snapshot.question_count} requested · ${detail.session.total_questions} generated` : `${detail.session.total_questions} generated · request not recorded`} /><Info label="Detailed filters" value={snapshot ? snapshot.conditions.length ? snapshot.conditions.map(label).join(", ") : "None" : "Not recorded"} /><Info label="Books" value={snapshot ? bookNames.length ? bookNames.join(", ") : "All books" : "Not recorded"} /><Info label="Chapters" value={snapshot ? chapterNames.length ? chapterNames.join(", ") : "All chapters" : "Not recorded"} /></div>
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5"><input aria-label="Search history details" placeholder="Filter questions…" value={search} onChange={event => setSearch(event.target.value)} className="min-h-11 rounded-lg border border-stone-300 bg-white px-3" /><Filter label="Result" value={result} setValue={setResult} options={[["all","All results"],["correct","Correct"],["wrong","Wrong"],["unanswered","Unanswered"]]} /><Filter label="Content" value={content} setValue={setContent} options={[["all","All content"],["vocabulary","Vocabulary"],["kanji","Kanji"],["kanji_example","Kanji examples"]]} /><Filter label="Book" value={book} setValue={value => { setBook(value); setChapter("all"); }} options={[["all","All books"], ...books]} /><Filter label="Lesson" value={chapter} setValue={setChapter} options={[["all","All lessons"], ...chapters]} /></div>
    <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white"><table className="w-full min-w-[64rem] text-left text-sm"><thead className="bg-stone-100 text-xs font-semibold uppercase tracking-wide text-stone-500"><tr><SortableHeader label="#" sortKey="position" sort={sort} onSort={changeSort} /><SortableHeader label="Question / answer" sortKey="question" sort={sort} onSort={changeSort} /><SortableHeader label="Book / lesson" sortKey="source" sort={sort} onSort={changeSort} /><SortableHeader label="Content" sortKey="content" sort={sort} onSort={changeSort} /><SortableHeader label="Result" sortKey="result" sort={sort} onSort={changeSort} /><SortableHeader label="Note" sortKey="note" sort={sort} onSort={changeSort} /><SortableHeader label="Study" sortKey="study" sort={sort} onSort={changeSort} /></tr></thead><tbody>{sorted.map(row => <AnswerRow key={row.question_id} row={row} />)}</tbody></table>{!sorted.length && <EmptyState className="p-8 text-center text-stone-500">No questions match these filters.</EmptyState>}</div>
  </div>;
}

function SortableHeader({label: text, sortKey, sort, onSort}: {label: string; sortKey: AnswerSortKey; sort: {key: AnswerSortKey; direction: SortDirection}; onSort: (key: AnswerSortKey) => void}) {
  const active = sort.key === sortKey;
  return <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"} className="p-0"><button type="button" onClick={() => onSort(sortKey)} className="flex w-full items-center gap-1 px-3 py-3 text-left hover:bg-stone-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-moss"><span>{text}</span><span aria-hidden="true" className={active ? "text-ink" : "text-stone-400"}>{active ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</span><span className="sr-only">{active ? `Sorted ${sort.direction === "asc" ? "ascending" : "descending"}; activate to sort ${sort.direction === "asc" ? "descending" : "ascending"}` : "Activate to sort ascending"}</span></button></th>;
}

function AnswerRow({row}: {row: PracticeHistoryAnswer}) {
  return <tr className="border-t border-stone-100 align-top"><td className="px-3 py-3 text-stone-500">{row.position + 1}</td><td className="max-w-sm px-3 py-3"><div className="flex flex-wrap items-center gap-2"><div className="whitespace-pre-line font-medium">{row.prompt}</div>{row.main_kanji && <span className="inline-flex items-center rounded-md bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-600">Main kanji <span lang="ja" className="ml-1 text-base text-ink">{row.main_kanji}</span></span>}</div><div className="mt-1 whitespace-pre-line text-moss">{row.answer_primary}{row.answer_secondary ? ` · ${row.answer_secondary}` : ""}</div></td><td className="px-3 py-3"><div>{row.book_title ?? "Source removed"}</div><div className="text-xs text-stone-500">{row.chapter_number != null ? `Lesson ${row.chapter_number}` : "No lesson"}{row.chapter_title ? ` · ${row.chapter_title}` : ""}</div></td><td className="px-3 py-3 capitalize"><div>{label(row.item_type)}</div><div className="text-xs text-stone-500">{label(row.question_type)}</div></td><td className={`px-3 py-3 font-semibold capitalize ${row.result === "correct" ? "text-moss" : row.result === "wrong" ? "text-persimmon" : "text-stone-400"}`}>{row.result ?? "Unanswered"}</td><td className="max-w-xs px-3 py-3 text-stone-600">{row.wrong_note ?? "—"}</td><td className="px-3 py-3">{row.study_kind && row.study_source_id ? <Link target="_blank" rel="noopener noreferrer" href={`/study/${row.study_kind}/${encodeURIComponent(row.study_source_id)}`} className="inline-flex min-h-9 items-center rounded-lg border border-moss px-3 font-semibold text-moss">Study</Link> : <span className="text-stone-400">Unavailable</span>}</td></tr>;
}

function answerSortValue(row: PracticeHistoryAnswer, key: AnswerSortKey): string | number | null {
  if (key === "position") return row.position;
  if (key === "question") return `${row.prompt} ${row.answer_primary} ${row.answer_secondary ?? ""}`;
  if (key === "source") return `${row.book_title ?? ""} ${row.chapter_number ?? ""} ${row.chapter_title ?? ""}`;
  if (key === "content") return `${label(row.item_type)} ${label(row.question_type)}`;
  if (key === "result") return row.result;
  if (key === "note") return row.wrong_note;
  return row.study_kind && row.study_source_id ? 1 : 0;
}

function compareSortValues(left: string | number | null, right: string | number | null) {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right), undefined, {numeric: true, sensitivity: "base"});
}

function Filter({label: ariaLabel, value, setValue, options}: {label: string; value: string; setValue: (value: string) => void; options: string[][]}) { return <select aria-label={ariaLabel} value={value} onChange={event => setValue(event.target.value)} className="min-h-11 rounded-lg border border-stone-300 bg-white px-3">{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>; }
function Info({label: title, value}: {label: string; value: string}) { return <div><div className="text-xs font-semibold uppercase tracking-wide text-stone-500">{title}</div><div className="mt-1 font-medium capitalize">{value}</div></div>; }
function unique(rows: PracticeHistoryAnswer[], id: (row: PracticeHistoryAnswer) => number | null, text: (row: PracticeHistoryAnswer) => string | null) { return Array.from(new Map(rows.filter(row => id(row) != null).map(row => [String(id(row)), text(row) ?? "Unknown"])).entries()); }
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"}).format(new Date(value)); }
function label(value: string) { const labels: Record<string,string> = {random:"Random", never_practiced:"New", mastery_review:"Not mastered", starred_priority:"Starred — weakest first", vocab_word_to_meaning:"Vocab word → meaning", vocab_meaning_to_word:"Vocab meaning → word", kanji_example:"Kanji example", kanji_example_words:"Kanji example words"}; return labels[value] ?? value.replaceAll("_", " "); }
function setupSummary(session: PracticeHistorySession) { const snapshot = session.filter_snapshot; if (!snapshot) return `${label(session.mode)} · filters not recorded`; const scope = snapshot.chapter_ids.length ? `${snapshot.chapter_ids.length} chapter${snapshot.chapter_ids.length === 1 ? "" : "s"}` : snapshot.book_ids.length ? `${snapshot.book_ids.length} book${snapshot.book_ids.length === 1 ? "" : "s"}` : "All books"; return `${label(session.mode)} · ${scope}${snapshot.conditions.length ? ` · ${snapshot.conditions.map(label).join(", ")}` : ""}`; }
