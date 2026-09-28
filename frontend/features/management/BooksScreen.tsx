"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api, Book, getBooks, invalidateLookups } from "@/lib/api";
import { Badge, inputClass, ManageHeader, Modal, primaryButton, secondaryButton } from "./shared";
const empty = { title: "", short_name: "", edition: "", jlpt_level: "", description: "", is_active: true };
export default function BooksScreen() {
  const [books, setBooks] = useState<Book[]>([]); const [editing, setEditing] = useState<Book | "new" | null>(null); const [draft, setDraft] = useState(empty); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false);
  const load = () => getBooks().then(setBooks).catch(error => setMessage(String(error)));
  useEffect(() => { load(); }, []);
  function open(book?: Book) { setEditing(book ?? "new"); setDraft(book ? { title: book.title, short_name: book.short_name ?? "", edition: book.edition ?? "", jlpt_level: book.jlpt_level ?? "", description: book.description ?? "", is_active: book.is_active } : empty); }
  async function save(event: FormEvent) { event.preventDefault(); setBusy(true); try { await api(editing === "new" ? "/books" : `/books/${(editing as Book).id}`, { method: editing === "new" ? "POST" : "PATCH", body: JSON.stringify({ ...draft, short_name: draft.short_name || null }) }); invalidateLookups(); await load(); setEditing(null); setMessage("Book saved."); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } }
  async function toggle(book: Book) { setBusy(true); try { await api(`/books/${book.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !book.is_active }) }); invalidateLookups(); await load(); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } }
  return <div><ManageHeader title="Books" description="Manage book metadata and choose which books are active."><button className={primaryButton} onClick={() => open()}><Plus className="mr-2" size={18} /> Add book</button></ManageHeader>
    {message && <p role="status" className="mb-4 rounded-lg bg-stone-100 p-3 text-sm">{message}</p>}
    <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white"><div className="hidden grid-cols-[minmax(12rem,2fr)_1fr_1fr_1fr_1fr_2fr] gap-4 border-b bg-stone-50 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-stone-500 md:grid"><span>Book</span><span>Status</span><span>Chapters</span><span>Vocabulary</span><span>Kanji</span><span>Actions</span></div>{books.map(book => <article key={book.id} className="grid gap-3 border-b border-stone-100 p-5 last:border-0 md:grid-cols-[minmax(12rem,2fr)_1fr_1fr_1fr_1fr_2fr] md:items-center"><div><h2 className="font-semibold">{book.title}</h2><p className="text-sm text-stone-500">{[book.edition, book.jlpt_level].filter(Boolean).join(" · ") || book.short_name}</p></div><div><Badge tone={book.is_active ? "green" : "neutral"}>{book.is_active ? "Active" : "Inactive"}</Badge></div><p><span className="md:hidden text-stone-500">Chapters: </span>{book.chapter_count}</p><p><span className="md:hidden text-stone-500">Vocabulary: </span>{book.vocabulary_count.toLocaleString()}</p><p><span className="md:hidden text-stone-500">Kanji: </span>{book.kanji_count.toLocaleString()}</p><div className="flex flex-wrap gap-2"><button className={secondaryButton} onClick={() => open(book)}>Edit</button><button disabled={busy} className={secondaryButton} onClick={() => toggle(book)}>Mark {book.is_active ? "inactive" : "active"}</button><Link className={secondaryButton} href={`/manage/chapters?book=${book.id}`}>View chapters</Link></div></article>)}</div>
    {editing && <Modal title={editing === "new" ? "Add book" : "Edit book"} close={() => setEditing(null)}>
      <form className="grid gap-4" onSubmit={save}>
        <label className="text-sm font-medium">Title<input autoFocus required className={inputClass} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
        <label className="text-sm font-medium">Short name <span className="font-normal text-stone-500">(optional)</span><input className={inputClass} value={draft.short_name} onChange={e => setDraft({ ...draft, short_name: e.target.value })} /></label>
        <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Edition<input className={inputClass} value={draft.edition} onChange={e => setDraft({ ...draft, edition: e.target.value })} /></label><label className="text-sm font-medium">JLPT level<input className={inputClass} value={draft.jlpt_level} onChange={e => setDraft({ ...draft, jlpt_level: e.target.value })} /></label></div>
        <label className="text-sm font-medium">Description<textarea rows={3} className={inputClass} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={draft.is_active} onChange={e => setDraft({ ...draft, is_active: e.target.checked })} />Active</label>
        <div className="flex justify-end gap-2"><button type="button" className={secondaryButton} onClick={() => setEditing(null)}>Cancel</button><button disabled={busy} className={primaryButton}>Save book</button></div>
      </form>
    </Modal>}
  </div>;
}
