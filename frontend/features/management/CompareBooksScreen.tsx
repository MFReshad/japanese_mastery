"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Settings } from "lucide-react";
import { api, Book, getActiveBooks } from "@/lib/api";
import { ManageHeader } from "./ManageHeader";
import { CompareItemCell } from "./CompareItemCell";
import { CompareViewSettingsPanel } from "./CompareViewSettingsPanel";
import type { CompareItem, CompareKind, CompareResult, CompareViewSettings, MatchRow, ToggleSetting } from "./compareTypes";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";

type Direction = "asc" | "desc";

const defaultViewSettings: CompareViewSettings = { star: true, kanjiExamples: true, mainWord: true, reading: true, meaning: true, lesson: true, mainWordSize: 30 };
const viewSettingsKey = "compare-content-view-v1";

export default function CompareBooksScreen() {
  const [books, setBooks] = useState<Book[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [kind, setKind] = useState<CompareKind>("vocabulary");
  const [sortMode, setSortMode] = useState<"lesson" | "alphabetical">("lesson");
  const [sortBookId, setSortBookId] = useState<number | null>(null);
  const [direction, setDirection] = useState<Direction>("asc");
  const [items, setItems] = useState<CompareItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [draggedBookId, setDraggedBookId] = useState<number | null>(null);
  const [dragOverBookId, setDragOverBookId] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [viewSettings, setViewSettings] = useState<CompareViewSettings>(defaultViewSettings);
  const selectedBookQuery = [...selected].sort((a, b) => a - b).join(",");

  useEffect(() => { getActiveBooks().then(setBooks).catch(reason => setError(String(reason))); }, []);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(viewSettingsKey) || "null") as Partial<CompareViewSettings> | null;
      if (saved) {
        const next = {...defaultViewSettings, ...saved};
        setViewSettings(next);
      }
    } catch { localStorage.removeItem(viewSettingsKey); }
  }, []);
  useEffect(() => {
    if (!selectedBookQuery) { setItems([]); return; }
    let active = true;
    const query = new URLSearchParams({ kind });
    selectedBookQuery.split(",").forEach(id => query.append("book_ids", id));
    setLoading(true); setError("");
    api<CompareResult>(`/library/compare?${query}`).then(result => { if (active) setItems(result.items); })
      .catch(reason => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [kind, selectedBookQuery]);

  const selectedBooks = selected.map(id => books.find(book => book.id === id)).filter((book): book is Book => Boolean(book));
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
  function moveBook(targetId: number) {
    if (draggedBookId === null || draggedBookId === targetId) return;
    setSelected(current => {
      const from = current.indexOf(draggedBookId);
      const to = current.indexOf(targetId);
      if (from < 0 || to < 0) return current;
      const reordered = [...current];
      reordered.splice(from, 1);
      reordered.splice(to, 0, draggedBookId);
      return reordered;
    });
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
  function toggleSettings() {
    setSettingsOpen(current => !current);
  }
  function toggleViewSetting(key: ToggleSetting) {
    const next = {...viewSettings, [key]: !viewSettings[key]};
    setViewSettings(next);
    localStorage.setItem(viewSettingsKey, JSON.stringify(next));
  }
  function changeMainWordSize(size: number) {
    const next = {...viewSettings, mainWordSize: size};
    setViewSettings(next);
    localStorage.setItem(viewSettingsKey, JSON.stringify(next));
  }
  function resetSettings() {
    setViewSettings(defaultViewSettings);
    localStorage.setItem(viewSettingsKey, JSON.stringify(defaultViewSettings));
  }

  return <div><ManageHeader title="Compare books" description="Match every vocabulary word or kanji across selected books. Missing entries stay blank." />
    <section className="relative mb-5 space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap gap-2"><button className={`rounded-lg px-4 py-2 font-medium ${kind === "vocabulary" ? "bg-ink text-white" : "border border-stone-300"}`} onClick={() => setKind("vocabulary")}>Vocabulary</button><button className={`rounded-lg px-4 py-2 font-medium ${kind === "kanji" ? "bg-ink text-white" : "border border-stone-300"}`} onClick={() => setKind("kanji")}>Kanji</button></div>
      <button type="button" onClick={toggleSettings} aria-label="Content view settings" title="Content view settings" className="fixed bottom-6 right-6 z-30 flex min-h-12 min-w-12 items-center justify-center rounded-full border border-stone-300 bg-white text-stone-600 shadow-lg hover:border-moss hover:text-moss"><Settings size={21} /></button>
      {settingsOpen && <CompareViewSettingsPanel value={viewSettings} toggle={toggleViewSetting} changeMainWordSize={changeMainWordSize} reset={resetSettings} close={() => setSettingsOpen(false)} />}
      <fieldset><legend className="mb-2 text-sm font-semibold">Books (choose several)</legend><div className="flex flex-wrap gap-2">{books.map(book => <label key={book.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${selected.includes(book.id) ? "border-moss bg-moss/10 text-moss" : "border-stone-300"}`}><input type="checkbox" className="mr-2 accent-moss" checked={selected.includes(book.id)} onChange={() => toggleBook(book.id)} />{book.title}</label>)}</div></fieldset>
      <label className="block max-w-xs text-sm font-medium">Sort rows<select className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3" value={sortMode} onChange={event => { setSortMode(event.target.value as "lesson" | "alphabetical"); setDirection("asc"); }}><option value="lesson">Lesson order</option><option value="alphabetical">Alphabetical</option></select></label>
    </section>
    {error && <ErrorState className="mb-4 text-persimmon">{error}</ErrorState>}
    {!selected.length ? <div className="rounded-2xl border border-dashed border-stone-300 p-12 text-center text-stone-500">Choose one or more books to create the comparison.</div> : loading ? <LoadingState className="h-72 animate-pulse rounded-2xl bg-stone-100" /> : <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white"><div className="w-full" style={{minWidth: `${selectedBooks.length * 18}rem`}}><div className="grid" style={{gridTemplateColumns: `repeat(${selectedBooks.length}, minmax(18rem, 1fr))`}}>{selectedBooks.map(book => <div key={book.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(book.id)); setDraggedBookId(book.id); }} onDragEnter={() => setDragOverBookId(book.id)} onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }} onDrop={event => { event.preventDefault(); moveBook(book.id); setDraggedBookId(null); setDragOverBookId(null); }} onDragEnd={() => { setDraggedBookId(null); setDragOverBookId(null); }} className={`cursor-grab select-none border-b border-r border-stone-200 bg-stone-50 p-4 last:border-r-0 active:cursor-grabbing ${draggedBookId === book.id ? "opacity-50" : ""} ${dragOverBookId === book.id && draggedBookId !== book.id ? "bg-moss/10 ring-2 ring-inset ring-moss" : ""}`}><button className="flex w-full items-center justify-between gap-3 text-left" onClick={() => sortByBook(book.id)}><span className="font-semibold">{book.title}</span>{sortMode === "lesson" && (sortBookId ?? selected[0]) === book.id ? direction === "asc" ? <ArrowUp size={17} /> : <ArrowDown size={17} /> : null}</button><span className="mt-1 block text-xs text-stone-500">Drag to reorder · Click to sort lessons</span></div>)}</div>{rows.map(row => <div key={row.key} className="grid" style={{gridTemplateColumns: `repeat(${selectedBooks.length}, minmax(18rem, 1fr))`}}>{selectedBooks.map(book => <div key={book.id} className="min-h-24 border-b border-r border-stone-100 p-4 last:border-r-0">{row.cells.get(book.id)?.map(item => <CompareItemCell key={item.source_entry_id} item={item} kind={kind} settings={viewSettings} toggleVocabularyStar={toggleVocabularyStar} toggleExampleStar={toggleExampleStar} />) ?? <span className="text-stone-300">—</span>}</div>)}</div>)}</div>{rows.length === 0 && <EmptyState className="p-12 text-center text-stone-500">The selected books contain no {kind} entries.</EmptyState>}</div>}
  </div>;
}

function lessonRank(item: CompareItem) {
  const part = Number(item.part ?? 0);
  return (Number.isFinite(part) ? part : 0) * 1_000_000 + (item.chapter_number ?? 9999) * 1_000;
}
