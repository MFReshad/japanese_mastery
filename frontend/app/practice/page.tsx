"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, Book, Chapter, getBooks, getCachedBooks, getCachedChapters, getCachedChaptersByBook, getChapters, getChaptersByBook, Question, RevealedAnswer } from "@/lib/api";

type PendingAnswer = { session_id: number; question_id: number; result: "correct" | "wrong"; note?: string };
const pendingKey = "practice-pending-answers";

export default function PracticePage() {
  return (
    <Suspense fallback={<div className="rounded border border-stone-200 bg-white p-4">Loading practice...</div>}>
      <PracticeContent />
    </Suspense>
  );
}

function PracticeContent() {
  const params = useSearchParams();
  const [books, setBooks] = useState<Book[]>(() => getCachedBooks());
  const [chapters, setChapters] = useState<Chapter[]>(() => {
    const cached = getCachedChapters();
    const initialBookId = params.get("book_id");
    return cached.length || !initialBookId ? cached : getCachedChaptersByBook(Number(initialBookId));
  });
  const [practiceType, setPracticeType] = useState(params.get("practice_type") ?? "mixed");
  const [mode, setMode] = useState(params.get("mode") ?? "random");
  const [bookId, setBookId] = useState(params.get("book_id") ?? "");
  const [chapterId, setChapterId] = useState(params.get("chapter_id") ?? "");
  const sourceEntryId = params.get("source_entry_id");
  const [count, setCount] = useState(sourceEntryId ? "1" : chapterId ? "All" : "10");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [reveal, setReveal] = useState<{ questionId: number; answer: RevealedAnswer } | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestInFlight = useRef(false);
  const sessionInProgress = useRef(false);
  const pending = useRef<PendingAnswer[]>([]);
  const draining = useRef(false);
  const submitted = useRef(new Set<number>());
  const [pendingCount, setPendingCount] = useState(0);
  const [saveWarning, setSaveWarning] = useState("");
  useEffect(() => {
    getBooks().then(setBooks);
    if (bookId) {
      getChaptersByBook(Number(bookId)).then(setChapters);
    } else {
      getChapters().then(setChapters);
    }
  }, []);
  useEffect(() => {
    try { pending.current = JSON.parse(sessionStorage.getItem(pendingKey) || "[]") as PendingAnswer[]; } catch { pending.current = []; }
    setPendingCount(pending.current.length);
    void drainQueue();
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (pending.current.length) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);
  function persistQueue() {
    sessionStorage.setItem(pendingKey, JSON.stringify(pending.current));
    setPendingCount(pending.current.length);
  }
  async function drainQueue() {
    if (draining.current) return;
    draining.current = true;
    try {
      while (pending.current.length) {
        const item = pending.current[0];
        let saved = false;
        for (let attempt = 0; attempt < 4 && !saved; attempt++) {
          try {
            await api("/practice/answer", { method: "POST", body: JSON.stringify(item) });
            saved = true;
          } catch (reason) {
            if (attempt === 3) {
              setSaveWarning(`An answer could not be saved. Retry when the connection is available. ${String(reason)}`);
            } else {
              await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
            }
          }
        }
        if (!saved) break;
        pending.current.shift();
        persistQueue();
        setSaveWarning("");
      }
    } finally { draining.current = false; }
  }
  const currentQuestion = questions[index];
  const shown = reveal?.questionId === currentQuestion?.question_id;
  const sessionActive = sessionId !== null && Boolean(currentQuestion);
  async function start() {
    if (requestInFlight.current || sessionInProgress.current || sessionActive || pending.current.length) return;
    requestInFlight.current = true; setBusy(true); setError("");
    try {
      const res = await api<{ session_id: number; questions: Question[] }>("/practice/start", { method: "POST", body: JSON.stringify({ practice_type: practiceType, mode, book_ids: bookId ? [Number(bookId)] : [], chapter_ids: chapterId ? [Number(chapterId)] : [], source_entry_ids: sourceEntryId ? [Number(sourceEntryId)] : [], question_count: count === "All" ? null : Number(count) }) });
      sessionInProgress.current = res.questions.length > 0;
      submitted.current.clear();
      setSessionId(res.session_id); setQuestions(res.questions); setIndex(0); setReveal(null); setNoteOpen(false); setNote("");
    } catch (reason) { setError(String(reason)); }
    finally { requestInFlight.current = false; setBusy(false); }
  }
  async function showAnswer() {
    if (!currentQuestion || !sessionId || requestInFlight.current || shown) return;
    requestInFlight.current = true; setBusy(true); setError("");
    try {
      const answer = await api<RevealedAnswer>(`/practice/questions/${currentQuestion.question_id}/reveal`, { method: "POST", body: JSON.stringify({ session_id: sessionId }) });
      setReveal({ questionId: currentQuestion.question_id, answer });
    } catch (reason) { setError(String(reason)); }
    finally { requestInFlight.current = false; setBusy(false); }
  }
  function answer(result: "correct" | "wrong") {
    if (!currentQuestion || !sessionId || !shown || submitted.current.has(currentQuestion.question_id)) return;
    submitted.current.add(currentQuestion.question_id);
    pending.current.push({ session_id: sessionId, question_id: currentQuestion.question_id, result, note: note.trim() || undefined });
    persistQueue();
    const nextIndex = index + 1;
    if (nextIndex >= questions.length) sessionInProgress.current = false;
    setIndex(nextIndex); setReveal(null); setNoteOpen(false); setNote("");
    void drainQueue();
  }
  return (
    <div className="space-y-4">
      <section className="grid gap-2 rounded border border-stone-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Select value={practiceType} onChange={setPracticeType} options={["vocabulary", "kanji", "mixed"]} disabled={sessionActive || busy} />
        <Select value={mode} onChange={setMode} options={["random", "wrong", "weak", "never_practiced", "mastery_review", "starred", "starred_priority"]} disabled={sessionActive || busy} />
        <select disabled={sessionActive || busy} className="min-h-11 rounded border border-stone-300 px-3" value={bookId} onChange={(e) => {
          const nextBookId = e.target.value;
          setBookId(nextBookId); setChapterId("");
          if (nextBookId) {
            const cached = getCachedChaptersByBook(Number(nextBookId));
            if (cached.length) setChapters((current) => mergeChapters(current, cached));
            getChaptersByBook(Number(nextBookId)).then((loaded) => setChapters((current) => mergeChapters(current, loaded)));
          } else {
            getChapters().then(setChapters);
          }
        }}><option value="">All books</option>{books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}</select>
        <select disabled={sessionActive || busy} className="min-h-11 rounded border border-stone-300 px-3" value={chapterId} onChange={(e) => setChapterId(e.target.value)}><option value="">All chapters</option>{chapters.filter((c) => !bookId || c.book_id === Number(bookId)).map((c) => <option key={c.id} value={c.id}>Lesson {c.chapter_number}</option>)}</select>
        <select disabled={sessionActive || busy} className="min-h-11 rounded border border-stone-300 px-3" value={count} onChange={(e) => setCount(e.target.value)}>{["1", "10", "20", "30", "50", "All"].map((v) => <option key={v}>{v}</option>)}</select>
        <button disabled={sessionActive || busy} className="min-h-12 rounded bg-ink px-4 font-semibold text-white disabled:opacity-50 sm:col-span-2 lg:col-span-5" onClick={start}>{sessionActive ? "Session in progress" : busy ? "Please wait..." : sessionId ? "New session" : "Start"}</button>
      </section>
      {error && <p role="alert" className="text-persimmon">{error}</p>}
      {saveWarning && <div role="alert" className="flex items-center gap-3 text-sm text-persimmon"><span>{saveWarning}</span><button className="underline" onClick={() => void drainQueue()}>Retry</button></div>}
      {currentQuestion ? (
        <section className="flex min-h-[420px] flex-col items-center justify-center rounded border border-stone-200 bg-white p-6 text-center">
          <div className="mb-4 text-sm text-stone-500">{index + 1} / {questions.length} · {currentQuestion.question_type.replaceAll("_", " ")}</div>
          <QuestionPrompt question={currentQuestion} />
          {shown ? <RevealDetails answer={reveal.answer} /> : <button disabled={busy} className="mb-8 min-h-14 rounded bg-moss px-8 font-semibold text-white disabled:opacity-50" onClick={showAnswer}>Show answer</button>}
          {shown && <div className="w-full max-w-md space-y-3">
            {noteOpen ? <label className="block text-left text-sm font-medium">Note (optional)<textarea autoFocus className="mt-1 w-full rounded border border-stone-300 p-3" rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /></label> : <button type="button" className="min-h-11 text-sm font-medium text-ink underline underline-offset-4" onClick={() => setNoteOpen(true)}>Add note</button>}
            <div className="grid grid-cols-2 gap-3"><button className="min-h-14 rounded border border-persimmon font-semibold text-persimmon" onClick={() => answer("wrong")}>Wrong</button><button className="min-h-14 rounded bg-moss font-semibold text-white" onClick={() => answer("correct")}>Correct</button></div>
          </div>}
        </section>
      ) : questions.length ? <p className="rounded border border-stone-200 bg-white p-4">{pendingCount ? `Saving ${pendingCount} answer${pendingCount === 1 ? "" : "s"}...` : "Session complete."}</p> : null}
    </div>
  );
}

function QuestionPrompt({ question }: { question: Question }) {
  if (!question.question_type.startsWith("example_kanji_")) {
    return <div className="mb-8 break-words text-5xl font-semibold sm:text-7xl">{question.prompt}</div>;
  }
  const [word, target, context, instruction] = question.prompt.split("\n");
  return <div className="mb-8 w-full max-w-lg space-y-3 break-words">
    <div className="text-4xl font-semibold sm:text-5xl">{word}</div>
    <div className="text-base text-stone-600">{target}<br />{context}</div>
    <div className="pt-2 text-xl font-medium">{instruction}</div>
  </div>;
}

function RevealDetails({ answer }: { answer: RevealedAnswer }) {
  const context = answer.context;
  if (!context) return <div className="mb-8 space-y-2"><div className="text-3xl font-semibold text-moss">{answer.answer_primary}</div>{answer.answer_secondary && <div className="text-xl text-stone-600">{answer.answer_secondary}</div>}</div>;
  return <div className="mb-8 w-full max-w-xl space-y-4 text-left">
    {context.kind === "kanji" ? <><div className="text-center text-6xl font-semibold">{context.kanji}</div><p><strong>Meaning</strong> {context.meanings?.join(" / ") || "—"}</p><p><strong>Onyomi</strong> {context.onyomi?.join(" / ") || "—"}</p><p><strong>Kunyomi</strong> {context.kunyomi?.join(" / ") || "—"}</p>{Boolean(context.examples?.length) && <div><h3 className="mb-2 font-semibold">Examples</h3><div className="space-y-2">{context.examples?.map((example, i) => <div key={i} className="rounded border border-stone-200 p-3"><strong>{example.word}</strong> · {example.reading} · {example.meaning}</div>)}</div></div>}</> : <><div className="text-4xl font-semibold">{context.kanji}</div><p><strong>Target meaning</strong> {context.target_meaning}</p>{context.target_reading && <p><strong>Target reading</strong> {context.target_reading}</p>}<p><strong>Onyomi</strong> {context.onyomi?.join(" / ") || "—"}</p><p><strong>Kunyomi</strong> {context.kunyomi?.join(" / ") || "—"}</p><div className="border-t border-stone-200 pt-3"><p><strong>Word</strong> {context.word}</p><p><strong>Reading</strong> {context.reading}</p><p><strong>Meaning</strong> {context.meaning}</p></div></>}
  </div>;
}

function Select({ value, onChange, options, disabled }: { value: string; onChange: (value: string) => void; options: string[]; disabled?: boolean }) {
  return <select disabled={disabled} className="min-h-11 rounded border border-stone-300 px-3" value={value} onChange={(e) => onChange(e.target.value)}>{options.map((o) => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}</select>;
}

function mergeChapters(current: Chapter[], loaded: Chapter[]) {
  const byId = new Map(current.map((chapter) => [chapter.id, chapter]));
  for (const chapter of loaded) byId.set(chapter.id, chapter);
  return Array.from(byId.values()).sort((a, b) => a.book_id - b.book_id || a.sort_order - b.sort_order || a.chapter_number - b.chapter_number);
}
