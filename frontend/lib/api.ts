const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
  get retryable() { return this.status === 408 || this.status === 429 || this.status >= 500; }
}
export function retryable(error: unknown) { return !(error instanceof ApiError) || error.retryable; }
const TTL = 30_000;
const lookups = new Map<string, { promise: Promise<unknown>; value?: unknown; expires: number }>();
let readGeneration = 0;
const inFlightGets = new Map<string, Promise<unknown>>();

export type Book = { id: number; title: string; short_name: string | null; edition?: string | null; jlpt_level?: string | null; description?: string | null; vocabulary_count: number; kanji_count: number; chapter_count: number; is_demo: boolean; is_active: boolean };
export type Chapter = { id: number; book_id: number; chapter_number: number; title: string; part: number | string | null; sort_order: number; vocabulary_count: number; kanji_count: number };
export type VocabSource = { id: number; created_at: string; updated_at: string; source_id: string | null; vocabulary_id: number; book_id: number; chapter_id: number | null; item_order: number; original_item_order: number | null; manually_added: boolean; manually_reordered: boolean; expression_as_printed: string; reading_as_printed: string; meaning_as_printed: string; notes: string | null; source_file?: string | null; source_page?: string | null; source_section?: string | null; expression: string; reading: string; status: string };
export type KanjiSource = { id: number; created_at: string; updated_at: string; source_id: string | null; kanji_id: number; book_id: number; chapter_id: number | null; item_order: number; character: string; meaning_as_printed: string; onyomi: string[]; kunyomi: string[]; examples: {word: string; reading: string; meaning: string; sort_order: number}[]; uncertain: boolean | null; notes: string | null; source_file?: string | null; source_page?: string | null; source_section?: string | null; extraction_batch?: string | null; status: string };
export type Progress = { item_type: string; total: number; new: number; learning: number; weak: number; mastered: number };
export type Coverage = { book_id: number; chapter_id: number; book_title: string; chapter_title: string; chapter_number: number; vocabulary_mastered_percent: number; kanji_mastered_percent: number };
export type Question = { question_id: number; item_type: string; question_type: string; prompt: string };
export type RevealedAnswer = { answer_primary: string; answer_secondary: string | null; context: { kind: "kanji" | "example"; kanji: string; meanings?: string[]; onyomi?: string[]; kunyomi?: string[]; examples?: { word: string; reading: string; meaning: string }[]; word?: string; reading?: string; meaning?: string; target_meaning?: string; target_reading?: string | null } | null };

export type StudyKind = "vocabulary" | "kanji";
export type StudyNextChapter = {
  chapter_id: number; chapter_number: number; chapter_title: string;
  part: number | string | null; first_source_id: string;
};
export type StudyListItem = {
  source_id: string; source_entry_id: number; item_order: number; meaning: string;
  expression?: string; reading?: string; character?: string;
  onyomi?: string[]; kunyomi?: string[]; example_count?: number;
};
export type StudyDetail = {
  source_id: string; source_entry_id: number; book_id: number; book_title: string;
  chapter_id: number | null; chapter_number: number | null; chapter_title: string | null;
  part: number | string | null; item_order: number; meaning_as_printed: string;
  meanings_as_printed: string[]; notes: string | null; source_page: number | string | null;
  previous_source_id: string | null; next_source_id: string | null; position: number; lesson_count: number;
  next_chapter: StudyNextChapter | null;
  expression_as_printed?: string; reading_as_printed?: string; character?: string;
  entry_number_as_printed?: number | null; onyomi_as_printed?: string[]; kunyomi_as_printed?: string[];
  stroke_count_as_printed?: number | null; examples?: {word: string; reading: string; meaning: string}[];
  uncertain?: boolean | null; source_book_page?: number | null;
};

export function api<T>(path: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method.toUpperCase() === "GET";
  const pending = isGet ? inFlightGets.get(path) : undefined;
  if (pending) return pending as Promise<T>;
  const generation = readGeneration;
  const request = (async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    if (!isGet && /^\/(books|chapters|vocabulary-sources|kanji-sources|import)(\/|$)/.test(path)) invalidateLookups();
    if (res.status === 204) return undefined as T;
    const result = await res.json() as T;
    if (isGet && generation !== readGeneration) return api<T>(path, init);
    return result;
    } finally { clearTimeout(timeout); }
  })();
  if (isGet) {
    inFlightGets.set(path, request);
    const release = () => { if (inFlightGets.get(path) === request) inFlightGets.delete(path); };
    request.then(release, release);
  }
  return request;
}

function cachedLookup<T>(path: string): Promise<T> {
  const cached = lookups.get(path);
  if (cached && cached.expires > Date.now()) return cached.promise as Promise<T>;
  const entry: { promise: Promise<unknown>; value?: unknown; expires: number } = {
    expires: Date.now() + TTL,
    promise: api<T>(path)
      .then((value) => {
        entry.value = value;
        return value;
      })
      .catch((error) => {
        if (lookups.get(path) === entry) lookups.delete(path);
        throw error;
      }),
  };
  lookups.set(path, entry);
  return entry.promise as Promise<T>;
}

function cachedLookupValue<T>(path: string): T | undefined {
  const entry = lookups.get(path);
  return entry && entry.expires > Date.now() ? entry.value as T : undefined;
}

function rememberLookup<T>(path: string, value: T): T {
  lookups.set(path, { value, expires: Date.now() + TTL, promise: Promise.resolve(value) });
  return value;
}

export const getBooks = () => cachedLookup<Book[]>("/books");
export const getChapters = () => cachedLookup<Chapter[]>("/chapters");
export const getCachedBooks = () => cachedLookupValue<Book[]>("/books") ?? [];
export const getCachedChapters = () => cachedLookupValue<Chapter[]>("/chapters") ?? [];
export function getCachedChaptersByBook(bookId: number) {
  return cachedLookupValue<Chapter[]>(`/chapters?book_id=${bookId}`)
    ?? cachedLookupValue<Chapter[]>("/chapters")?.filter((chapter) => chapter.book_id === bookId)
    ?? [];
}
export function getChaptersByBook(bookId: number) {
  const path = `/chapters?book_id=${bookId}`;
  const cached = cachedLookupValue<Chapter[]>(path);
  if (cached) return Promise.resolve(cached);
  const allChapters = cachedLookupValue<Chapter[]>("/chapters");
  if (allChapters) return Promise.resolve(rememberLookup(path, allChapters.filter((chapter) => chapter.book_id === bookId)));
  return cachedLookup<Chapter[]>(path);
}
export function invalidateLookups() {
  readGeneration++; lookups.clear(); inFlightGets.clear();
  if (typeof window !== "undefined") window.dispatchEvent(new Event("lookups-invalidated"));
}
export function subscribeLookups(refresh: () => void) {
  window.addEventListener("lookups-invalidated", refresh);
  const timer = window.setInterval(refresh, TTL);
  return () => { window.removeEventListener("lookups-invalidated", refresh); clearInterval(timer); };
}
