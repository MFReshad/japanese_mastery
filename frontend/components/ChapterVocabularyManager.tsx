"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { DndContext, KeyboardSensor, PointerSensor, TouchSensor, closestCenter, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDown, ArrowUp, GripVertical, Plus, RotateCcw, Trash2 } from "lucide-react";
import { api, Book, Chapter, invalidateLookups, VocabSource } from "@/lib/api";
import { Badge, inputClass, Modal, primaryButton, secondaryButton } from "@/features/management/shared";

export default function ChapterVocabularyManager({ books, chapters, initialBookId = "", initialChapterId = "" }: { books: Book[]; chapters: Chapter[]; initialBookId?: string; initialChapterId?: string }) {
  const requestVersion = useRef(0);
  const currentChapter = useRef("");
  const [bookId, setBookId] = useState(initialBookId);
  const [chapterId, setChapterId] = useState(initialChapterId);
  const [rows, setRows] = useState<VocabSource[]>([]);
  const [savedIds, setSavedIds] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [identityAction, setIdentityAction] = useState("correction");
  const [draft, setDraft] = useState({ expression: "", reading: "", meaning: "", order: 1 });
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  currentChapter.current = chapterId;
  async function reload(id = chapterId) {
    const version = ++requestVersion.current;
    if (!id) { setRows([]); return; }
    const next = await api<VocabSource[]>(`/chapters/${id}/vocabulary-order`);
    if (version !== requestVersion.current || id !== currentChapter.current) return;
    setRows(next); setSavedIds(next.map((row) => row.id).join(","));
  }
  useEffect(() => { setEditing(null); setRows([]); reload(chapterId).catch((error) => setMessage(String(error))); }, [chapterId]);
  useEffect(() => { if (bookId) localStorage.setItem("manage-book", bookId); if (chapterId) localStorage.setItem("manage-vocabulary-chapter", chapterId); }, [bookId, chapterId]);
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
    if (busy) return;
    setBusy(true); setMessage("");
    try { await action(); invalidateLookups(); await reload(); setMessage("Saved."); }
    catch (error) { setMessage(String(error)); }
    finally { setBusy(false); }
  }
  function chooseEdit(row: VocabSource) {
    if (busy) return;
    setEditing(row.id);
    setDraft({ expression: row.expression_as_printed, reading: row.reading_as_printed, meaning: row.meaning_as_printed, order: rows.findIndex(item => item.id === row.id) + 1 });
    setMessage("");
  }
  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editing === null || busy) return;
    setBusy(true); setMessage("");
    try {
      const updated = await api<VocabSource>(`/vocabulary-sources/${editing}`, { method: "PATCH", body: JSON.stringify({ expression_as_printed: draft.expression, reading_as_printed: draft.reading, meaning_as_printed: draft.meaning, identity_action: identityAction }) });
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
    form.reset(); setAdding(false);
  }
  return <section>
    <div className="grid gap-2 sm:grid-cols-2"><select disabled={busy} aria-label="Book" className="min-h-11 rounded border p-2" value={bookId} onChange={(e) => { setBookId(e.target.value); setChapterId(""); }}><option value="">Select book</option>{books.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}</select><select disabled={busy} aria-label="Chapter" className="min-h-11 rounded border p-2" value={chapterId} onChange={(e) => setChapterId(e.target.value)}><option value="">Select chapter</option>{chapters.filter((chapter) => chapter.book_id === Number(bookId)).sort((a, b) => a.sort_order - b.sort_order).map((chapter) => <option key={chapter.id} value={chapter.id}>Lesson {chapter.chapter_number}: {chapter.title}</option>)}</select></div>
    {chapterId && <><div className="mt-4 flex flex-wrap items-center gap-2"><span className="mr-auto text-sm text-stone-600">{rows.length} entries in study order</span><button disabled={busy || changed} className={primaryButton} onClick={() => setAdding(true)}><Plus className="mr-2" size={17}/> Add vocabulary</button><button disabled={!changed || busy} className={primaryButton} onClick={() => run(() => api(`/chapters/${chapterId}/vocabulary-order`, { method: "PUT", body: JSON.stringify({ source_ids: rows.map((row) => row.id), expected_source_ids: savedIds ? savedIds.split(",").map(Number) : [] }) }))}>Save order</button><button disabled={busy} title="Reset to imported order" className={secondaryButton} onClick={() => run(() => api(`/chapters/${chapterId}/vocabulary-order/reset`, { method: "POST" }))}><RotateCcw className="mr-2" size={17} /> Reset to imported order</button></div>
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={finishDrag}><SortableContext items={rows.map((row) => row.id)} strategy={verticalListSortingStrategy}><ol className="mt-4 overflow-hidden rounded-2xl border border-stone-200 bg-white divide-y divide-stone-200">{rows.map((row, index) => <SortableRow key={row.id} row={row} index={index} count={rows.length} busy={busy} move={move} chooseEdit={chooseEdit} remove={() => { if (confirm(`Remove ${row.expression_as_printed} from this chapter?`)) run(() => api(`/vocabulary-sources/${row.id}`, { method: "DELETE" })); }} />)}</ol></SortableContext></DndContext>
    {editing !== null && <Modal title="Edit vocabulary" close={() => !busy && setEditing(null)}><form className="grid gap-3" onSubmit={saveEdit}><label className="text-sm font-medium">Expression<input autoFocus required className={inputClass} value={draft.expression} onChange={(e) => setDraft({ ...draft, expression: e.target.value })} /></label><label className="text-sm font-medium">Reading<input required className={inputClass} value={draft.reading} onChange={(e) => setDraft({ ...draft, reading: e.target.value })} /></label><label className="text-sm font-medium">Meaning<textarea required rows={3} className={inputClass} value={draft.meaning} onChange={(e) => setDraft({ ...draft, meaning: e.target.value })} /></label><label className="text-sm font-medium">Order<input type="number" disabled className={inputClass} value={draft.order}/></label><details className="rounded-lg border p-3"><summary className="cursor-pointer font-medium">Advanced / Source Info</summary><label className="mt-3 block text-sm">Edit type<select className={inputClass} value={identityAction} onChange={event => setIdentityAction(event.target.value)}><option value="correction">Correct printed text (keep mastery)</option><option value="relink">Replace with a different word (use its mastery)</option></select></label><SourceInfo row={rows.find(row => row.id === editing)} /></details>{message && <p role="alert" className="text-sm text-persimmon">{message}</p>}<div className="flex justify-end gap-2"><button type="button" disabled={busy} className={secondaryButton} onClick={() => setEditing(null)}>Cancel</button><button disabled={busy} className={primaryButton}>Save entry</button></div></form></Modal>}
    {adding && <Modal title="Add vocabulary" close={() => setAdding(false)}><form className="grid gap-3" onSubmit={add}><label className="text-sm font-medium">Expression<input autoFocus name="expression" required className={inputClass}/></label><label className="text-sm font-medium">Reading<input name="reading" required className={inputClass}/></label><label className="text-sm font-medium">Meaning<textarea name="meaning" required className={inputClass}/></label><label className="text-sm font-medium">Order<input name="position" type="number" min="1" max={rows.length + 1} defaultValue={rows.length + 1} required className={inputClass}/></label><div className="flex justify-end gap-2"><button type="button" className={secondaryButton} onClick={() => setAdding(false)}>Cancel</button><button disabled={busy} className={primaryButton}>Add vocabulary</button></div></form></Modal>}</>}
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
    <div className="min-w-0 flex-1 sm:grid sm:grid-cols-3 sm:gap-4"><div className="font-semibold">{row.expression_as_printed}<div className="font-normal text-stone-600">{row.reading_as_printed}</div></div><div className="break-words text-sm text-stone-600">{row.meaning_as_printed}</div><div className="mt-1 sm:mt-0"><Badge tone={row.manually_added ? "green" : row.updated_at !== row.created_at ? "amber" : "blue"}>{row.manually_added ? "Manually Added" : row.updated_at !== row.created_at ? "Manually Edited" : "Imported"}</Badge></div></div>
    <div className="flex shrink-0 items-center"><button title="Move up" aria-label={`Move ${row.expression_as_printed} up`} disabled={busy || index === 0} className="rounded p-1.5 disabled:opacity-30 sm:p-2" onClick={() => move(index, -1)}><ArrowUp size={18} /></button><button title="Move down" aria-label={`Move ${row.expression_as_printed} down`} disabled={busy || index === count - 1} className="rounded p-1.5 disabled:opacity-30 sm:p-2" onClick={() => move(index, 1)}><ArrowDown size={18} /></button><button className="min-h-10 px-1 text-sm text-moss sm:px-2" onClick={() => chooseEdit(row)}>Edit</button><button title="Remove from chapter" aria-label={`Remove ${row.expression_as_printed}`} className="rounded p-1.5 text-persimmon sm:p-2" onClick={remove}><Trash2 size={18} /></button></div>
  </li>;
}

function SourceInfo({ row }: { row?: VocabSource }) { if (!row) return null; return <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-stone-500">Source file</dt><dd>{row.source_file || "—"}</dd></div><div><dt className="text-stone-500">Source page</dt><dd>{row.source_page || "—"}</dd></div><div><dt className="text-stone-500">Source section</dt><dd>{row.source_section || "—"}</dd></div><div><dt className="text-stone-500">Source ID</dt><dd className="break-all">{row.source_id || "—"}</dd></div></dl>; }
