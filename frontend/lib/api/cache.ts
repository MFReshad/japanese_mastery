import { request } from "./transport";
import type { Book, Chapter } from "./types";

const TTL = 30_000;
const lookups = new Map<string, { promise: Promise<unknown>; value?: unknown; expires: number }>();
let readGeneration = 0;
const inFlightGets = new Map<string, Promise<unknown>>();

export function api<T>(path: string, init?: RequestInit): Promise<T> {
  const isGet = !init?.method || init.method.toUpperCase() === "GET";
  const pending = isGet ? inFlightGets.get(path) : undefined;
  if (pending) return pending as Promise<T>;
  const generation = readGeneration;
  const pendingRequest = request<T>(path, init).then((result) => {
    if (!isGet && /^\/(books|chapters|vocabulary-sources|kanji-sources|import)(\/|$)/.test(path)) invalidateLookups();
    if (isGet && generation !== readGeneration) return api<T>(path, init);
    return result;
  });
  if (isGet) {
    inFlightGets.set(path, pendingRequest);
    const release = () => { if (inFlightGets.get(path) === pendingRequest) inFlightGets.delete(path); };
    pendingRequest.then(release, release);
  }
  return pendingRequest;
}

function cachedLookup<T>(path: string): Promise<T> {
  const cached = lookups.get(path);
  if (cached && cached.expires > Date.now()) return cached.promise as Promise<T>;
  const entry: { promise: Promise<unknown>; value?: unknown; expires: number } = { expires: Date.now() + TTL, promise: Promise.resolve() };
  entry.promise = api<T>(path).then((value) => { entry.value = value; return value; }).catch((error) => { if (lookups.get(path) === entry) lookups.delete(path); throw error; });
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
export const isBookActive = (book: Book) => book.is_active !== false;
export const getActiveBooks = () => getBooks().then((books) => books.filter(isBookActive));
export const getChapters = () => cachedLookup<Chapter[]>("/chapters");
export const getCachedBooks = () => cachedLookupValue<Book[]>("/books") ?? [];
export const getCachedActiveBooks = () => getCachedBooks().filter(isBookActive);
export const getCachedChapters = () => cachedLookupValue<Chapter[]>("/chapters") ?? [];
export function getCachedChaptersByBook(bookId: number) { return cachedLookupValue<Chapter[]>(`/chapters?book_id=${bookId}`) ?? cachedLookupValue<Chapter[]>("/chapters")?.filter((chapter) => chapter.book_id === bookId) ?? []; }
export function getChaptersByBook(bookId: number) {
  const path = `/chapters?book_id=${bookId}`;
  const cached = cachedLookupValue<Chapter[]>(path);
  if (cached) return Promise.resolve(cached);
  const allChapters = cachedLookupValue<Chapter[]>("/chapters");
  if (allChapters) return Promise.resolve(rememberLookup(path, allChapters.filter((chapter) => chapter.book_id === bookId)));
  return cachedLookup<Chapter[]>(path);
}
export function invalidateLookups() { readGeneration++; lookups.clear(); inFlightGets.clear(); if (typeof window !== "undefined") window.dispatchEvent(new Event("lookups-invalidated")); }
export function subscribeLookups(refresh: () => void) { window.addEventListener("lookups-invalidated", refresh); const timer = window.setInterval(refresh, TTL); return () => { window.removeEventListener("lookups-invalidated", refresh); clearInterval(timer); }; }
