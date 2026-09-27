import { retryable } from "@/lib/api";
import { saveAnswer } from "./api";
export type PendingAnswer = { session_id: number; question_id: number; result: "correct" | "wrong"; note?: string };
const key = "practice-answer-queue-v1";
let items: PendingAnswer[] = [];
let failed: PendingAnswer[] = [];
let loaded = false;
let running: Promise<void> | null = null;
let warning = "";
const listeners = new Set<() => void>();
function valid(value: unknown): value is PendingAnswer {
  if (!value || typeof value !== "object") return false;
  const v = value as PendingAnswer;
  return Number.isInteger(v.session_id) && v.session_id > 0 && Number.isInteger(v.question_id) && v.question_id > 0
    && ["correct", "wrong"].includes(v.result) && (v.note === undefined || (typeof v.note === "string" && v.note.length <= 2000));
}
function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || "null");
    if (value?.version === 1 && Array.isArray(value.items) && Array.isArray(value.failed)) {
      items = value.items.filter(valid); failed = value.failed.filter(valid);
    } else {
      const legacy = JSON.parse(sessionStorage.getItem("practice-pending-answers") || "[]");
      if (Array.isArray(legacy)) items = legacy.filter(valid);
      sessionStorage.removeItem("practice-pending-answers");
    }
  } catch { warning = "Stored answer queue was invalid. Resume the session to review unsaved questions."; }
}
function notify() {
  try { sessionStorage.setItem(key, JSON.stringify({ version: 1, items, failed })); }
  catch { warning = "Browser storage is unavailable. Keep this tab open until answers finish saving."; }
  listeners.forEach(listener => listener());
}
export function queueState() { load(); return { count: items.length, warning: failed.length ? `${failed.length} answer(s) need review and were not saved. ${warning}` : warning }; }
export function queuedIds() { load(); return new Set([...items, ...failed].map(item => item.question_id)); }
export function subscribeQueue(listener: () => void) { load(); listeners.add(listener); return () => { listeners.delete(listener); }; }
export function enqueue(item: PendingAnswer) {
  load();
  if (!valid(item)) throw new Error("Invalid answer");
  if (!items.some(value => value.question_id === item.question_id)) items.push(item);
  notify(); void drainQueue();
}
export function drainQueue(): Promise<void> {
  load();
  if (running) return running;
  running = (async () => {
    while (items.length) {
      const item = items[0];
      let finished = false;
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          await saveAnswer(item);
          finished = true; warning = ""; break;
        } catch (error) {
          if (!retryable(error)) {
            failed.push(item); warning = `Answer rejected: ${String(error)}`; finished = true; break;
          }
          warning = "Answers are waiting for a connection. Retry when available.";
          notify();
          if (attempt < 3) await new Promise(resolve => setTimeout(resolve, 500 * 2 ** attempt));
        }
      }
      if (!finished) break;
      items.shift(); notify();
    }
  })().finally(() => { running = null; });
  return running;
}
