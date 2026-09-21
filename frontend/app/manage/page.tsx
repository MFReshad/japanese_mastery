"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, Book, Chapter, getBooks, getChapters, invalidateLookups, KanjiSource, VocabSource } from "@/lib/api";
import ChapterVocabularyManager from "@/components/ChapterVocabularyManager";

export default function ManagePage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [importResult, setImportResult] = useState("");
  const reload = () => { getBooks().then(setBooks); getChapters().then(setChapters); };
  useEffect(reload, []);
  async function addBook(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = new FormData(e.currentTarget);
    await api("/books", { method: "POST", body: JSON.stringify(Object.fromEntries(form)) }); e.currentTarget.reset(); invalidateLookups(); reload();
  }
  async function addChapter(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = new FormData(e.currentTarget);
    await api("/chapters", { method: "POST", body: JSON.stringify({ book_id: Number(form.get("book_id")), chapter_number: Number(form.get("chapter_number")), title: form.get("title"), sort_order: Number(form.get("sort_order") || form.get("chapter_number")) }) }); e.currentTarget.reset(); invalidateLookups(); reload();
  }
  async function runImport(dryRun: boolean) {
    const res = await api<Record<string, unknown>>("/import", { method: "POST", body: JSON.stringify({ directory: "data/imports", dry_run: dryRun }) });
    setImportResult(JSON.stringify(res, null, 2)); invalidateLookups(); reload();
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded border border-stone-200 bg-white p-4"><h1 className="mb-3 text-xl font-semibold">Books</h1><form className="grid gap-2" onSubmit={addBook}><input name="title" required className="rounded border p-3" placeholder="Title" /><input name="short_name" required className="rounded border p-3" placeholder="Short name" /><input name="edition" className="rounded border p-3" placeholder="Edition" /><input name="jlpt_level" className="rounded border p-3" placeholder="JLPT level" /><button className="rounded bg-ink p-3 font-semibold text-white">Create book</button></form><List items={books.map((b) => `${b.title} · vocab ${b.vocabulary_count} · kanji ${b.kanji_count}`)} /></section>
      <section className="rounded border border-stone-200 bg-white p-4"><h1 className="mb-3 text-xl font-semibold">Chapters</h1><form className="grid gap-2" onSubmit={addChapter}><select name="book_id" required className="rounded border p-3">{books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}</select><input name="chapter_number" required type="number" className="rounded border p-3" placeholder="Chapter number" /><input name="sort_order" type="number" className="rounded border p-3" placeholder="Sort order" /><input name="title" required className="rounded border p-3" placeholder="Title" /><button className="rounded bg-ink p-3 font-semibold text-white">Create chapter</button></form><List items={chapters.map((c) => `Lesson ${c.chapter_number}: ${c.title}`)} /></section>
      <EntryForms books={books} chapters={chapters} />
      <SourceEditor books={books} chapters={chapters} />
      <ChapterVocabularyManager books={books} chapters={chapters} />
      <section className="rounded border border-stone-200 bg-white p-4 lg:col-span-2"><h1 className="mb-3 text-xl font-semibold">Import JSON</h1><div className="flex gap-2"><button className="rounded border border-moss px-4 py-3 font-semibold text-moss" onClick={() => runImport(true)}>Preview</button><button className="rounded bg-moss px-4 py-3 font-semibold text-white" onClick={() => runImport(false)}>Import</button></div>{importResult && <pre className="mt-3 overflow-auto rounded bg-stone-900 p-3 text-xs text-white">{importResult}</pre>}</section>
    </div>
  );
}

function SourceEditor({ books, chapters }: { books: Book[]; chapters: Chapter[] }) {
  const [bookId, setBookId] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [kind, setKind] = useState<"vocabulary" | "kanji">("kanji");
  const [items, setItems] = useState<(VocabSource | KanjiSource)[]>([]);
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState({ meaning: "", onyomi: "", kunyomi: "", examples: "[]", uncertain: false, notes: "" });
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!bookId || !chapterId) { setItems([]); return; }
    let active = true;
    setItems([]);
    api<(VocabSource | KanjiSource)[]>(`/${kind}-sources?book_id=${bookId}&${chapterId === "unassigned" ? "unassigned=true" : `chapter_id=${chapterId}`}`).then((rows) => { if (active) setItems(rows); }).catch((err) => { if (active) setMessage(String(err)); });
    setSelected("");
    return () => { active = false; };
  }, [bookId, chapterId, kind]);
  function choose(id: string) {
    setSelected(id);
    const item = items.find((entry) => entry.id === Number(id));
    if (!item) return;
    const kanji = kind === "kanji" ? item as KanjiSource : null;
    setDraft({ meaning: item.meaning_as_printed, onyomi: kanji?.onyomi.join(", ") || "", kunyomi: kanji?.kunyomi.join(", ") || "",
      examples: JSON.stringify(kanji?.examples || [], null, 2), uncertain: kanji?.uncertain || false, notes: item.notes || "" });
    setMessage("");
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      const payload: Record<string, unknown> = { meaning_as_printed: draft.meaning, notes: draft.notes };
      if (kind === "kanji") {
        const examples = JSON.parse(draft.examples);
        if (!Array.isArray(examples) || examples.some((entry) => !entry.word || !entry.reading || !entry.meaning)) throw new Error("Examples must be an array of word, reading, and meaning objects.");
        Object.assign(payload, { onyomi: draft.onyomi.split(",").map((v) => v.trim()).filter(Boolean), kunyomi: draft.kunyomi.split(",").map((v) => v.trim()).filter(Boolean), examples, uncertain: draft.uncertain });
      }
      await api(`/${kind}-sources/${selected}`, { method: "PATCH", body: JSON.stringify(payload) });
      setMessage("Saved. Source ID and provenance remain unchanged.");
    } catch (err) { setMessage(String(err)); }
  }
  return <section className="border-t border-stone-200 pt-4 lg:col-span-2">
    <h2 className="mb-3 text-lg font-semibold">Edit source entry</h2>
    <div className="grid gap-2 sm:grid-cols-4">
      <select aria-label="Entry type" className="border p-2" value={kind} onChange={(e) => setKind(e.target.value as "vocabulary" | "kanji")}><option value="kanji">Kanji</option><option value="vocabulary">Vocabulary</option></select>
      <select aria-label="Book" className="border p-2" value={bookId} onChange={(e) => { setBookId(e.target.value); setChapterId(""); }}><option value="">Select book</option>{books.map((book) => <option key={book.id} value={book.id}>{book.title}</option>)}</select>
      <select aria-label="Chapter" className="border p-2" value={chapterId} onChange={(e) => setChapterId(e.target.value)}><option value="">Select chapter</option><option value="unassigned">Unassigned</option>{chapters.filter((chapter) => chapter.book_id === Number(bookId)).map((chapter) => <option key={chapter.id} value={chapter.id}>Lesson {chapter.chapter_number}: {chapter.title}</option>)}</select>
      <select aria-label="Source entry" className="border p-2" value={selected} onChange={(e) => choose(e.target.value)}><option value="">Select entry</option>{items.map((item) => <option key={item.id} value={item.id}>{kind === "kanji" ? (item as KanjiSource).character : (item as VocabSource).expression} · {item.source_id || item.id}</option>)}</select>
    </div>
    {selected && <form className="mt-3 grid gap-2" onSubmit={save}>
      <label>Meaning<textarea className="block w-full border p-2" value={draft.meaning} onChange={(e) => setDraft({ ...draft, meaning: e.target.value })} /></label>
      {kind === "kanji" && <><label>Onyomi<input className="block w-full border p-2" value={draft.onyomi} onChange={(e) => setDraft({ ...draft, onyomi: e.target.value })} /></label><label>Kunyomi<input className="block w-full border p-2" value={draft.kunyomi} onChange={(e) => setDraft({ ...draft, kunyomi: e.target.value })} /></label><label>Examples (JSON)<textarea className="block w-full border p-2 font-mono text-sm" rows={7} value={draft.examples} onChange={(e) => setDraft({ ...draft, examples: e.target.value })} /></label><label className="flex items-center gap-2"><input type="checkbox" checked={draft.uncertain} onChange={(e) => setDraft({ ...draft, uncertain: e.target.checked })} />Uncertain</label></>}
      <label>Notes<textarea className="block w-full border p-2" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label><button className="w-fit bg-moss px-4 py-2 text-white">Save changes</button>
    </form>}
    {message && <p role="status" className="mt-2 text-sm">{message}</p>}
  </section>;
}

function EntryForms({ books, chapters }: { books: Book[]; chapters: Chapter[] }) {
  async function addKanji(e: FormEvent<HTMLFormElement>) { e.preventDefault(); const f = new FormData(e.currentTarget); await api("/kanji-sources", { method: "POST", body: JSON.stringify({ book_id: Number(f.get("book_id")), chapter_id: Number(f.get("chapter_id")), item_order: Number(f.get("item_order")), character: f.get("character"), meaning: f.get("meaning"), onyomi: String(f.get("onyomi") || "").split(/[,\s]+/).filter(Boolean), kunyomi: String(f.get("kunyomi") || "").split(/[,\s]+/).filter(Boolean), examples: [] }) }); invalidateLookups(); e.currentTarget.reset(); }
  return <section className="rounded border border-stone-200 bg-white p-4 lg:col-span-2"><h1 className="mb-3 text-xl font-semibold">Kanji</h1><EntryForm books={books} chapters={chapters} onSubmit={addKanji} fields={["character", "meaning", "onyomi", "kunyomi"]} /></section>;
}

function EntryForm({ books, chapters, fields, onSubmit }: { books: Book[]; chapters: Chapter[]; fields: string[]; onSubmit: (e: FormEvent<HTMLFormElement>) => void }) {
  return <form className="grid gap-2" onSubmit={onSubmit}><select name="book_id" required className="rounded border p-3">{books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}</select><select name="chapter_id" required className="rounded border p-3">{chapters.map((c) => <option key={c.id} value={c.id}>Lesson {c.chapter_number}: {c.title}</option>)}</select><input name="item_order" required type="number" className="rounded border p-3" placeholder="Order" />{fields.map((field) => <input key={field} name={field} required={!["notes", "onyomi", "kunyomi"].includes(field)} className="rounded border p-3" placeholder={field} />)}<button className="rounded bg-ink p-3 font-semibold text-white">Save</button></form>;
}

function List({ items }: { items: string[] }) {
  return <div className="mt-3 space-y-1 text-sm text-stone-600">{items.map((item, index) => <div key={index} className="rounded bg-stone-50 p-2">{item}</div>)}</div>;
}
