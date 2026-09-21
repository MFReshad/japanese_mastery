const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const lookups = new Map<string, { expires: number; promise: Promise<unknown> }>();
const inFlightGets = new Map<string, Promise<unknown>>();

export type Book = { id: number; title: string; short_name: string | null; vocabulary_count: number; kanji_count: number; is_demo: boolean };
export type Chapter = { id: number; book_id: number; chapter_number: number; title: string; part: number | string | null; sort_order: number };
export type VocabSource = { id: number; source_id: string | null; vocabulary_id: number; book_id: number; chapter_id: number | null; item_order: number; original_item_order: number | null; manually_added: boolean; manually_reordered: boolean; expression_as_printed: string; reading_as_printed: string; meaning_as_printed: string; notes: string | null; expression: string; reading: string; status: string };
export type KanjiSource = { id: number; source_id: string | null; kanji_id: number; book_id: number; chapter_id: number | null; item_order: number; character: string; meaning_as_printed: string; onyomi: string[]; kunyomi: string[]; examples: {word: string; reading: string; meaning: string; sort_order: number}[]; uncertain: boolean | null; notes: string | null; status: string };
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
  const request = (async () => {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(await res.text());
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  })();
  if (isGet) {
    inFlightGets.set(path, request);
    request.then(() => inFlightGets.delete(path), () => inFlightGets.delete(path));
  }
  return request;
}

function cachedLookup<T>(path: string): Promise<T> {
  const cached = lookups.get(path);
  if (cached && cached.expires > Date.now()) return cached.promise as Promise<T>;
  const promise = api<T>(path).catch((error) => { lookups.delete(path); throw error; });
  lookups.set(path, { expires: Date.now() + 60_000, promise });
  return promise;
}

export const getBooks = () => cachedLookup<Book[]>("/books");
export const getChapters = () => cachedLookup<Chapter[]>("/chapters");
export function invalidateLookups() { lookups.clear(); }
