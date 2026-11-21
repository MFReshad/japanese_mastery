"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Settings, Star, X } from "lucide-react";
import Link from "next/link";
import { api, Book, getActiveBooks } from "@/lib/api";
import { ManageHeader } from "./ManageHeader";

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
type ViewSettings = { star: boolean; kanjiExamples: boolean; mainWord: boolean; reading: boolean; meaning: boolean; lesson: boolean; mainWordSize: number };
type ToggleSetting = Exclude<keyof ViewSettings, "mainWordSize">;

const defaultViewSettings: ViewSettings = { star: true, kanjiExamples: true, mainWord: true, reading: true, meaning: true, lesson: true, mainWordSize: 30 };
const viewSettingsKey = "compare-content-view-v1";

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
  const [draggedBookId, setDraggedBookId] = useState<number | null>(null);
  const [dragOverBookId, setDragOverBookId] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [viewSettings, setViewSettings] = useState<ViewSettings>(defaultViewSettings);
  const selectedBookQuery = [...selected].sort((a, b) => a - b).join(",");

  useEffect(() => { getActiveBooks().then(setBooks).catch(reason => setError(String(reason))); }, []);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(viewSettingsKey) || "null") as Partial<ViewSettings> | null;
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
      {settingsOpen && <ViewSettingsPanel value={viewSettings} toggle={toggleViewSetting} changeMainWordSize={changeMainWordSize} reset={resetSettings} close={() => setSettingsOpen(false)} />}
      <fieldset><legend className="mb-2 text-sm font-semibold">Books (choose several)</legend><div className="flex flex-wrap gap-2">{books.map(book => <label key={book.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm ${selected.includes(book.id) ? "border-moss bg-moss/10 text-moss" : "border-stone-300"}`}><input type="checkbox" className="mr-2 accent-moss" checked={selected.includes(book.id)} onChange={() => toggleBook(book.id)} />{book.title}</label>)}</div></fieldset>
      <label className="block max-w-xs text-sm font-medium">Sort rows<select className="mt-1 min-h-11 w-full rounded-lg border border-stone-300 bg-white px-3" value={sortMode} onChange={event => { setSortMode(event.target.value as "lesson" | "alphabetical"); setDirection("asc"); }}><option value="lesson">Lesson order</option><option value="alphabetical">Alphabetical</option></select></label>
    </section>
    {error && <p role="alert" className="mb-4 text-persimmon">{error}</p>}
    {!selected.length ? <div className="rounded-2xl border border-dashed border-stone-300 p-12 text-center text-stone-500">Choose one or more books to create the comparison.</div> : loading ? <div className="h-72 animate-pulse rounded-2xl bg-stone-100" /> : <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white"><div className="w-full" style={{minWidth: `${selectedBooks.length * 18}rem`}}><div className="grid" style={{gridTemplateColumns: `repeat(${selectedBooks.length}, minmax(18rem, 1fr))`}}>{selectedBooks.map(book => <div key={book.id} draggable onDragStart={event => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(book.id)); setDraggedBookId(book.id); }} onDragEnter={() => setDragOverBookId(book.id)} onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }} onDrop={event => { event.preventDefault(); moveBook(book.id); setDraggedBookId(null); setDragOverBookId(null); }} onDragEnd={() => { setDraggedBookId(null); setDragOverBookId(null); }} className={`cursor-grab select-none border-b border-r border-stone-200 bg-stone-50 p-4 last:border-r-0 active:cursor-grabbing ${draggedBookId === book.id ? "opacity-50" : ""} ${dragOverBookId === book.id && draggedBookId !== book.id ? "bg-moss/10 ring-2 ring-inset ring-moss" : ""}`}><button className="flex w-full items-center justify-between gap-3 text-left" onClick={() => sortByBook(book.id)}><span className="font-semibold">{book.title}</span>{sortMode === "lesson" && (sortBookId ?? selected[0]) === book.id ? direction === "asc" ? <ArrowUp size={17} /> : <ArrowDown size={17} /> : null}</button><span className="mt-1 block text-xs text-stone-500">Drag to reorder · Click to sort lessons</span></div>)}</div>{rows.map(row => <div key={row.key} className="grid" style={{gridTemplateColumns: `repeat(${selectedBooks.length}, minmax(18rem, 1fr))`}}>{selectedBooks.map(book => <div key={book.id} className="min-h-24 border-b border-r border-stone-100 p-4 last:border-r-0">{row.cells.get(book.id)?.map(item => <ItemCell key={item.source_entry_id} item={item} kind={kind} settings={viewSettings} toggleVocabularyStar={toggleVocabularyStar} toggleExampleStar={toggleExampleStar} />) ?? <span className="text-stone-300">—</span>}</div>)}</div>)}</div>{rows.length === 0 && <p className="p-12 text-center text-stone-500">The selected books contain no {kind} entries.</p>}</div>}
  </div>;
}

function ItemCell({ item, kind, settings, toggleVocabularyStar, toggleExampleStar }: { item: CompareItem; kind: Kind; settings: ViewSettings; toggleVocabularyStar: (item: CompareItem) => void; toggleExampleStar: (id: number, current: boolean) => void }) {
  const importantVocabulary = kind === "vocabulary" && item.is_important;
  return <div className="group relative isolate mb-3 rounded-lg p-2 -m-2 transition hover:bg-moss/5 hover:ring-1 hover:ring-moss/30 focus-within:ring-2 focus-within:ring-moss">
    <Link href={`/study/${kind}/${encodeURIComponent(item.source_id)}`} target="_blank" rel="noopener noreferrer" aria-label={`Open ${item.display} in Study`} className="absolute inset-0 z-0 rounded-lg" />
    {kind === "vocabulary" && settings.star && <button type="button" onClick={() => toggleVocabularyStar(item)} aria-label={item.is_important ? `Remove ${item.display} from important vocabulary` : `Mark ${item.display} as important vocabulary`} title={item.is_important ? "Remove important mark" : "Mark as important"} className={`absolute right-2 top-2 z-20 flex min-h-9 min-w-9 items-center justify-center rounded border bg-white ${item.is_important ? "border-amber-400 text-amber-600" : "border-stone-300 text-stone-500"}`}><Star size={17} fill={item.is_important ? "currentColor" : "none"} /></button>}
    <div className={`pointer-events-none relative z-10 ${kind === "vocabulary" && settings.star ? "pr-11" : ""}`}>
    <div className={`w-full ${importantVocabulary ? "rounded-md bg-amber-100 px-2 py-2 text-amber-950" : ""}`}>
      {kind === "vocabulary" ? <>{settings.mainWord && <div className="font-semibold" style={{fontSize: `${settings.mainWordSize}px`}}>{item.display}</div>}{settings.reading && item.reading && <div className={importantVocabulary ? "text-sm text-amber-800" : "text-sm text-moss"}>{item.reading}</div>}</> : settings.mainWord && <div className="font-semibold" style={{fontSize: `${settings.mainWordSize}px`}}>{item.display}</div>}
      {settings.meaning && <div className={importantVocabulary ? "mt-1 text-sm text-amber-900" : "mt-1 text-sm text-stone-600"}>{item.meaning}</div>}
    </div>
    {settings.lesson && <div className="mt-2 text-xs font-medium text-stone-500">{item.part != null ? `Part ${item.part} · ` : ""}{item.chapter_number != null ? `Lesson ${item.chapter_number}` : "No chapter"}{item.chapter_title ? ` · ${item.chapter_title}` : ""}</div>}
    {kind === "kanji" && settings.kanjiExamples && Boolean(item.examples?.length) && <div className="mt-3 border-t border-stone-100 pt-2"><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-400">Examples</div>{item.examples?.map((example, index) => <div key={`${example.word}-${index}`} className={`relative py-1 ${settings.star ? "pr-11" : ""} text-sm`}><div className={`w-full ${example.is_important ? "rounded-md bg-amber-100 px-2 py-2 text-amber-950" : ""}`}><div className="grid grid-cols-2 gap-4">{settings.mainWord && <span className="font-medium">{example.word}</span>}{settings.reading && <span className={example.is_important ? "text-amber-800" : "text-moss"}>{example.reading}</span>}</div>{settings.meaning && <div className={example.is_important ? "mt-1 text-amber-900" : "mt-1 text-stone-500"}>{example.meaning}</div>}</div>{settings.star && <button type="button" onClick={() => toggleExampleStar(example.id, example.is_important ?? false)} aria-label={example.is_important ? `Remove ${example.word} from important examples` : `Mark ${example.word} as an important example`} title={example.is_important ? "Remove important mark" : "Mark as important"} className={`pointer-events-auto absolute right-0 top-1 z-20 flex min-h-8 min-w-8 items-center justify-center rounded border bg-white ${example.is_important ? "border-amber-400 text-amber-600" : "border-stone-300 text-stone-500"}`}><Star size={15} fill={example.is_important ? "currentColor" : "none"} /></button>}</div>)}</div>}
    </div>
  </div>;
}

function ViewSettingsPanel({value, toggle, changeMainWordSize, reset, close}: {value: ViewSettings; toggle: (key: ToggleSetting) => void; changeMainWordSize: (size: number) => void; reset: () => void; close: () => void}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const options: [ToggleSetting, string][] = [["star", "Star"], ["kanjiExamples", "Kanji examples"], ["mainWord", "Main word"], ["reading", "Reading"], ["meaning", "Meaning"], ["lesson", "Lesson"]];
  return <div className="fixed bottom-20 right-6 z-30 max-h-[calc(100vh-7rem)] w-96 max-w-[calc(100%_-_3rem)] overflow-y-auto rounded-xl border border-stone-200 bg-white p-4 shadow-2xl"><button type="button" onClick={close} aria-label="Close content view settings" title="Close" className="absolute right-3 top-3 flex min-h-9 min-w-9 items-center justify-center rounded-lg text-stone-500 hover:bg-stone-100 hover:text-ink"><X size={18} /></button><div className="pr-12"><h2 className="font-semibold">Content view</h2><p className="mt-1 text-sm text-stone-500">Changes are applied automatically.</p></div><div className="mt-4 space-y-2">{options.map(([key, label]) => <button key={key} type="button" role="switch" aria-checked={value[key]} onClick={() => toggle(key)} className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-2 text-left hover:bg-stone-50"><span className="text-sm font-medium">{label}</span><span aria-hidden="true" className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${value[key] ? "bg-moss" : "bg-stone-300"}`}><span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${value[key] ? "translate-x-[1.375rem]" : "translate-x-0.5"}`} /></span></button>)}</div>{advancedOpen && <div className="mt-4 rounded-lg bg-stone-50 p-3"><div className="flex items-center justify-between gap-3"><label htmlFor="main-word-size" className="text-sm font-medium">Main word size</label><output htmlFor="main-word-size" className="text-sm tabular-nums text-stone-500">{value.mainWordSize}px</output></div><input id="main-word-size" type="range" min="12" max="48" step="1" value={value.mainWordSize} onChange={event => changeMainWordSize(Number(event.target.value))} className="mt-3 w-full accent-moss" /></div>}<div className="mt-4 flex justify-end gap-2 border-t border-stone-200 pt-4"><button type="button" onClick={() => setAdvancedOpen(current => !current)} aria-expanded={advancedOpen} className="min-h-10 rounded-lg border border-stone-300 bg-white px-4 text-sm font-semibold">Advanced</button><button type="button" onClick={reset} className="min-h-10 rounded-lg border border-stone-300 bg-white px-4 text-sm font-semibold">Reset</button></div></div>;
}

function lessonRank(item: CompareItem) {
  const part = Number(item.part ?? 0);
  return (Number.isFinite(part) ? part : 0) * 1_000_000 + (item.chapter_number ?? 9999) * 1_000;
}
