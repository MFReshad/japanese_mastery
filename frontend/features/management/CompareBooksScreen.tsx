"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Star } from "lucide-react";
import Link from "next/link";
import { api, Book, getActiveBooks } from "@/lib/api";
import { ManageHeader } from "./shared";

type Kind = "vocabulary" | "kanji";
type Direction = "asc" | "desc";
type CompareItem = {
  match_key: string; source_id: string; source_entry_id: number; book_id: number;
  chapter_id: number | null; chapter_number: number | null; chapter_title: string | null;
  part: number | string | null; item_order: number; display: string; reading?: string;
  meaning: string; is_important?: boolean; onyomi?: string[]; kunyomi?: string[];
  examples?: { id: number; word: string; reading: string; meaning: string; is_important?: boolean }[];
};
type CompareResult = { kind: Kind; book_ids: number[]; items: CompareItem[] };
type MatchRow = { key: string; label: string; cells: Map<number, CompareItem[]> };

export default function CompareBooksScreen() {
  const [books, setBooks] = useState<Book[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [kind, setKind] = useState<Kind>("vocabulary");
  const [sortMode, setSortMode] = useState<"lesson" | "alphabetical">("lesson");
  const [sortBookId, setSortBookId] = useState<number | null>(null);
  const [direction, setDirection] = useState<Direction>("asc");
  const [items, setItems] = useState<CompareItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { getActiveBooks().then(setBooks).catch(reason => setError(String(reason))); }, []);
  useEffect(() => {
    if (!selected.length) { setItems([]); return; }
    let active = true;
    const query = new URLSearchParams({ kind });
    selected.forEach(id => query.append("book_ids", String(id)));
    setLoading(true); setError("");
    api<CompareResult>(`/library/compare?${query}`).then(result => { if (active) setItems(result.items); })
      .catch(reason => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [kind, selected]);

  const selectedBooks = books.filter(book => selected.includes(book.id));
  const rows = useMemo(() => {
    const grouped = new Map<string, MatchRow>();
    for (const item of items) {
      const row = grouped.get(item.match_key) ?? { key: item.match_key, label: item.display, cells: new Map<number, CompareItem[]>() };
      row.cells.set(item.book_id, [...(row.cells.get(item.book_id) ?? []), item]);
      grouped.set(item.match_key, row);
    }
    const result = Array.from(grouped.values());
    const factor = direction === "asc" ? 1 : -1;
    return result.sort((a, b) => {
      if (sortMode === "alphabetical") return factor * a.label.localeCompare(b.label, "ja", { numeric: true });
      const reference = sortBookId ?? selected[0];
      const left = a.cells.get(reference)?.[0];
      const right = b.cells.get(reference)?.[0];
      if (left && right) return factor * (lessonRank(left) - lessonRank(right) || left.item_order - right.item_order || a.label.localeCompare(b.label, "ja"));
      if (left) return -1;
      if (right) return 1;
      return a.label.localeCompare(b.label, "ja", { numeric: true });
    });
  }, [items, direction, selected, sortBookId, sortMode]);

  function toggleBook(id: number) {
    setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
    if (sortBookId === id) setSortBookId(null);
  }
  function sortByBook(id: number) {
    setSortMode("lesson");
    if (sortBookId === id) setDirection(current => current === "asc" ? "desc" : "asc");
    else { setSortBookId(id); setDirection("asc"); }
  }
  async function toggleVocabularyStar(item: CompareItem) {
    const next = !item.is_important;
    setItems(current => current.map(entry => entry.match_key === item.match_key ? {...entry, is_important: next} : entry));
    try {
      await api(`/library/items/vocabulary/${item.source_entry_id}/star`, {method: "PATCH", body: JSON.stringify({is_starred: next})});
    } catch (reason) {
      setItems(current => current.map(entry => entry.match_key === item.match_key ? {...entry, is_important: item.is_important} : entry));
      setError(`Could not save the vocabulary star: ${String(reason)}`);
    }
  }
  async function toggleExampleStar(exampleId: number, currentValue: boolean) {
    const next = !currentValue;
    setItems(current => current.map(item => ({...item, examples: item.examples?.map(example => example.id === exampleId ? {...example, is_important: next} : example)})));
    try {
      await api(`/kanji-examples/${exampleId}/important`, {method: "PATCH", body: JSON.stringify({is_important: next})});
    } catch (reason) {
      setItems(current => current.map(item => ({...item, examples: item.examples?.map(example => example.id === exampleId ? {...example, is_important: currentValue} : example)})));
      setError(`Could not save the example star: ${String(reason)}`);
    }
  }

  return <div><ManageHeader title="Compare books" description="Match every vocabulary word or kanji across selected books. Missing entries stay blank." />
    <section className="mb-5 space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap gap-2"><button className={`rounded-lg px-4 py-2 font-medium ${kind === "vocabulary" ? "bg-ink text-white" : "border border-stone-300"}`} onClick={() => setKind("vocabulary")}>Vocabulary</button><button className={`rounded-lg px-4 py-2 font-medium ${kind === "kanji" ? "bg-ink text-white" : "border border-stone-300"}`} onClick={() => setKind("kanji")}>Kanji</button></div>
      <fieldset><legend className="mb-2 text-sm font-semibold">Books (choose several)</legend><div className="flex flex-wrap gap-2">{books.map(book => <label key={book.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${selected.includes(book.id) ? "border-moss bg-moss/10 text-moss" : "border-stone-300"}`}><input type="checkbox" className="mr-2 accent-moss" checked={selected.includes(book.id)} onChange={() => toggleBook(book.id)} />{book.title}</label>)}</div></fieldset>
      <label className="block max-w-xs text-sm font-medium">Sort rows<select className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3" value={sortMode} onChange={event => { setSortMode(event.target.value as "lesson" | "alphabetical"); setDirection("asc"); }}><option value="lesson">Lesson order</option><option value="alphabetical">Alphabetical</option></select></label>
    </section>
    {error && <p role="alert" className="mb-4 text-persimmon">{error}</p>}
    {!selected.length ? <div className="rounded-2xl border border-dashed border-stone-300 p-12 text-center text-stone-500">Choose one or more books to create the comparison.</div> : loading ? <div className="h-72 animate-pulse rounded-2xl bg-stone-100" /> : <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white"><table className="min-w-full border-collapse"><thead><tr>{selectedBooks.map(book => <th key={book.id} className="sticky top-0 min-w-72 border-b border-r border-stone-200 bg-stone-50 p-4 text-left last:border-r-0"><button className="flex w-full items-center justify-between gap-3" onClick={() => sortByBook(book.id)}><span>{book.title}</span>{sortMode === "lesson" && (sortBookId ?? selected[0]) === book.id ? direction === "asc" ? <ArrowUp size={17} /> : <ArrowDown size={17} /> : null}</button><span className="mt-1 block text-xs font-normal text-stone-500">Click to sort by this book’s lessons</span></th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.key} className="align-top">{selectedBooks.map(book => <td key={book.id} className="border-b border-r border-stone-100 p-4 last:border-r-0">{row.cells.get(book.id)?.map(item => <ItemCell key={item.source_entry_id} item={item} kind={kind} toggleVocabularyStar={toggleVocabularyStar} toggleExampleStar={toggleExampleStar} />) ?? <span className="text-stone-300">—</span>}</td>)}</tr>)}</tbody></table>{rows.length === 0 && <p className="p-12 text-center text-stone-500">The selected books contain no {kind} entries.</p>}</div>}
  </div>;
}

function ItemCell({ item, kind, toggleVocabularyStar, toggleExampleStar }: { item: CompareItem; kind: Kind; toggleVocabularyStar: (item: CompareItem) => void; toggleExampleStar: (id: number, current: boolean) => void }) {
  const importantVocabulary = kind === "vocabulary" && item.is_important;
  return <div className="group relative mb-3 rounded-lg p-2 -m-2 transition hover:bg-moss/5 hover:ring-1 hover:ring-moss/30 focus-within:ring-2 focus-within:ring-moss">
    <Link href={`/study/${kind}/${encodeURIComponent(item.source_id)}`} target="_blank" rel="noopener noreferrer" aria-label={`Open ${item.display} in Study`} className="absolute inset-0 z-0 rounded-lg" />
    {kind === "vocabulary" && <button type="button" onClick={() => toggleVocabularyStar(item)} aria-label={item.is_important ? `Remove ${item.display} from important vocabulary` : `Mark ${item.display} as important vocabulary`} title={item.is_important ? "Remove important mark" : "Mark as important"} className={`absolute right-2 top-2 z-20 flex min-h-9 min-w-9 items-center justify-center rounded border bg-white ${item.is_important ? "border-amber-400 text-amber-600" : "border-stone-300 text-stone-500"}`}><Star size={17} fill={item.is_important ? "currentColor" : "none"} /></button>}
    <div className={`pointer-events-none relative z-10 ${kind === "vocabulary" ? "pr-11" : ""}`}>
    <div className={importantVocabulary ? "inline-block rounded-md bg-amber-100 px-2 py-1 text-amber-950" : ""}>
      <div className={kind === "kanji" ? "text-3xl font-semibold" : "text-lg font-semibold"}>{item.display}</div>
      {item.reading && <div className={importantVocabulary ? "text-sm text-amber-800" : "text-sm text-moss"}>{item.reading}</div>}
      <div className={importantVocabulary ? "mt-1 text-sm text-amber-900" : "mt-1 text-sm text-stone-600"}>{item.meaning}</div>
    </div>
    <div className="mt-2 text-xs font-medium text-stone-500">{item.part != null ? `Part ${item.part} · ` : ""}{item.chapter_number != null ? `Lesson ${item.chapter_number}` : "No chapter"}{item.chapter_title ? ` · ${item.chapter_title}` : ""}</div>
    {kind === "kanji" && Boolean(item.examples?.length) && <div className="mt-3 border-t border-stone-100 pt-2"><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-400">Examples</div>{item.examples?.map((example, index) => <div key={`${example.word}-${index}`} className="relative py-1 pr-11 text-sm"><div className={example.is_important ? "inline-block rounded-md bg-amber-100 px-2 py-1 text-amber-950" : ""}><div><span className="font-medium">{example.word}</span> <span className={example.is_important ? "text-amber-800" : "text-moss"}>{example.reading}</span></div><div className={example.is_important ? "text-amber-900" : "text-stone-500"}>{example.meaning}</div></div><button type="button" onClick={() => toggleExampleStar(example.id, example.is_important ?? false)} aria-label={example.is_important ? `Remove ${example.word} from important examples` : `Mark ${example.word} as an important example`} title={example.is_important ? "Remove important mark" : "Mark as important"} className={`pointer-events-auto absolute right-0 top-1 z-20 flex min-h-8 min-w-8 items-center justify-center rounded border bg-white ${example.is_important ? "border-amber-400 text-amber-600" : "border-stone-300 text-stone-500"}`}><Star size={15} fill={example.is_important ? "currentColor" : "none"} /></button></div>)}</div>}
    </div>
  </div>;
}

function lessonRank(item: CompareItem) {
  const part = Number(item.part ?? 0);
  return (Number.isFinite(part) ? part : 0) * 1_000_000 + (item.chapter_number ?? 9999) * 1_000;
}
