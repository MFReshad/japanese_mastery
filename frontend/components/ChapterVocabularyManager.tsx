"use client";

import { FormEvent, useEffect, useState } from "react";
import { DndContext, KeyboardSensor, PointerSensor, TouchSensor, closestCenter, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDown, ArrowUp, GripVertical, RotateCcw, Trash2, X } from "lucide-react";
import { api, Book, Chapter, invalidateLookups, VocabSource } from "@/lib/api";

export default function ChapterVocabularyManager({ books, chapters }: { books: Book[]; chapters: Chapter[] }) {
  const [bookId, setBookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [rows, setRows] = useState<VocabSource[]>([]);
  const [savedIds, setSavedIds] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState({ expression: "", reading: "", meaning: "" });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  async function reload(id = chapterId) {
    if (!id) { setRows([]); return; }
    const next = await api<VocabSource[]>(`/chapters/${id}/vocabulary-order`);
    setRows(next); setSavedIds(next.map((row) => row.id).join(","));
  }
  useEffect(() => { reload(chapterId).catch((error) => setMessage(String(error))); }, [chapterId]);
  const changed = rows.map((row) => row.id).join(",") !== savedIds;
  function move(index: number, delta: number) {
    const next = [...rows];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    setRows(next);
  }
  function finishDrag(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setRows((current) => {
      const from = current.findIndex((row) => row.id === active.id);
      const to = current.findIndex((row) => row.id === over.id);
      return from < 0 || to < 0 ? current : arrayMove(current, from, to);
    });
  }
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setMessage("");
    try { await action(); invalidateLookups(); await reload(); setMessage("Saved."); }
    catch (error) { setMessage(String(error)); }
    finally { setBusy(false); }
  }
  function chooseEdit(row: VocabSource) {
    setEditing(row.id);
    setDraft({ expression: row.expression_as_printed, reading: row.reading_as_printed, meaning: row.meaning_as_printed });
    setMessage("");
  }
  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing === null || busy) return;
    setBusy(true); setMessage("");
    try {
      const updated = await api<VocabSource>(`/vocabulary-sources/${editing}`, { method: "PATCH", body: JSON.stringify({ expression_as_printed: draft.expression, reading_as_printed: draft.reading, meaning_as_printed: draft.meaning }) });
      setRows((current) => current.map((row) => row.id === updated.id ? updated : row));
      setEditing(null);
      setMessage("Entry saved.");
    } catch (error) { setMessage(String(error)); }
    finally { setBusy(false); }
  }
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(() => api(`/chapters/${chapterId}/vocabulary-order`, { method: "POST", body: JSON.stringify({ expression: data.get("expression"), reading: data.get("reading"), meaning: data.get("meaning"), position: Number(data.get("position")) }) }));
    form.reset();
  }
  return <section className="border-t border-stone-200 pt-5 lg:col-span-2">
    <h2 className="mb-3 text-lg font-semibold">Chapter vocabulary order</h2>
    <div className="grid gap-2 sm:grid-cols-2"><select aria-label="Book" className="min-h-11 rounded border p-2" value={bookId} onChange={(e) => { setBookId(e.target.value); setChapterId(""); }}><option value="">Select book</option>{books.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}</select><select aria-label="Chapter" className="min-h-11 rounded border p-2" value={chapterId} onChange={(e) => setChapterId(e.target.value)}><option value="">Select chapter</option>{chapters.filter((chapter) => chapter.book_id === Number(bookId)).sort((a, b) => a.sort_order - b.sort_order).map((chapter) => <option key={chapter.id} value={chapter.id}>Lesson {chapter.chapter_number}: {chapter.title}</option>)}</select></div>
    {chapterId && <><div className="mt-3 flex flex-wrap items-center gap-2"><span className="mr-auto text-sm text-stone-600">{rows.length} entries</span><button disabled={!changed || busy} className="min-h-11 rounded bg-moss px-4 font-semibold text-white disabled:opacity-50" onClick={() => run(() => api(`/chapters/${chapterId}/vocabulary-order`, { method: "PUT", body: JSON.stringify({ source_ids: rows.map((row) => row.id) }) }))}>Save order</button><button disabled={busy} title="Reset to imported order" className="flex min-h-11 items-center gap-2 rounded border px-3 disabled:opacity-50" onClick={() => run(() => api(`/chapters/${chapterId}/vocabulary-order/reset`, { method: "POST" }))}><RotateCcw size={17} /> Reset to imported order</button></div>
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={finishDrag}><SortableContext items={rows.map((row) => row.id)} strategy={verticalListSortingStrategy}><ol className="mt-3 divide-y divide-stone-200 border-y border-stone-200">{rows.map((row, index) => <SortableRow key={row.id} row={row} index={index} count={rows.length} busy={busy} move={move} chooseEdit={chooseEdit} remove={() => { if (confirm(`Remove ${row.expression_as_printed} from this chapter?`)) run(() => api(`/vocabulary-sources/${row.id}`, { method: "DELETE" })); }} />)}</ol></SortableContext></DndContext>
    {editing !== null && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setEditing(null); }}><div role="dialog" aria-modal="true" aria-labelledby="edit-vocabulary-title" className="w-full max-w-lg rounded bg-white p-5 shadow-xl"><div className="mb-4 flex items-center justify-between"><h3 id="edit-vocabulary-title" className="text-lg font-semibold">Edit vocabulary</h3><button type="button" title="Close" aria-label="Close editor" disabled={busy} className="rounded p-2" onClick={() => setEditing(null)}><X size={20} /></button></div><form className="grid gap-3" onSubmit={saveEdit}><label className="text-sm font-medium">Expression<input autoFocus required className="mt-1 block w-full rounded border p-3" value={draft.expression} onChange={(e) => setDraft({ ...draft, expression: e.target.value })} /></label><label className="text-sm font-medium">Reading<input required className="mt-1 block w-full rounded border p-3" value={draft.reading} onChange={(e) => setDraft({ ...draft, reading: e.target.value })} /></label><label className="text-sm font-medium">Meaning<textarea required rows={3} className="mt-1 block w-full rounded border p-3" value={draft.meaning} onChange={(e) => setDraft({ ...draft, meaning: e.target.value })} /></label>{message && <p role="alert" className="text-sm text-persimmon">{message}</p>}<div className="flex justify-end gap-2"><button type="button" disabled={busy} className="min-h-11 rounded border px-4" onClick={() => setEditing(null)}>Cancel</button><button disabled={busy} className="min-h-11 rounded bg-moss px-4 font-semibold text-white disabled:opacity-50">Save entry</button></div></form></div></div>}
    <form className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5" onSubmit={add}><input name="expression" required className="rounded border p-3" placeholder="Expression" aria-label="Expression" /><input name="reading" required className="rounded border p-3" placeholder="Reading" aria-label="Reading" /><input name="meaning" required className="rounded border p-3" placeholder="Meaning" aria-label="Meaning" /><label className="flex items-center gap-2 text-sm">Position <input name="position" type="number" min="1" max={rows.length + 1} defaultValue={rows.length + 1} key={rows.length} required className="w-20 rounded border p-3" /></label><button disabled={busy || changed} className="min-h-11 rounded bg-ink px-4 font-semibold text-white disabled:opacity-50">Add vocabulary</button></form></>}
    {message && <p role="status" className="mt-2 text-sm text-persimmon">{message}</p>}
  </section>;
}

function SortableRow({ row, index, count, busy, move, chooseEdit, remove }: {
  row: VocabSource; index: number; count: number; busy: boolean;
  move: (index: number, delta: number) => void;
  chooseEdit: (row: VocabSource) => void; remove: () => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: row.id, disabled: busy });
  return <li ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, zIndex: isDragging ? 10 : undefined }} className={`relative flex min-h-16 items-center gap-1 bg-white py-2 sm:gap-2 ${isDragging ? "shadow-md" : ""}`}>
    <button ref={setActivatorNodeRef} type="button" title="Drag to reorder" aria-label={`Drag ${row.expression_as_printed} to reorder`} className="flex h-11 w-9 shrink-0 touch-none items-center justify-center rounded text-stone-500 focus-visible:outline-2 focus-visible:outline-moss" {...attributes} {...listeners}><GripVertical size={20} /></button>
    <span className="w-7 shrink-0 text-sm text-stone-500">{index + 1}</span>
    <div className="min-w-0 flex-1"><div className="font-semibold">{row.expression_as_printed} <span className="font-normal text-stone-600">{row.reading_as_printed}</span></div><div className="break-words text-sm text-stone-600">{row.meaning_as_printed}</div>{row.manually_added && <span className="text-xs text-moss">Added manually</span>}</div>
    <div className="flex shrink-0 items-center"><button title="Move up" aria-label={`Move ${row.expression_as_printed} up`} disabled={busy || index === 0} className="rounded p-1.5 disabled:opacity-30 sm:p-2" onClick={() => move(index, -1)}><ArrowUp size={18} /></button><button title="Move down" aria-label={`Move ${row.expression_as_printed} down`} disabled={busy || index === count - 1} className="rounded p-1.5 disabled:opacity-30 sm:p-2" onClick={() => move(index, 1)}><ArrowDown size={18} /></button><button className="min-h-10 px-1 text-sm text-moss sm:px-2" onClick={() => chooseEdit(row)}>Edit</button><button title="Remove from chapter" aria-label={`Remove ${row.expression_as_printed}`} className="rounded p-1.5 text-persimmon sm:p-2" onClick={remove}><Trash2 size={18} /></button></div>
  </li>;
}
