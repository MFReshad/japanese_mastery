import { api, Question, RevealedAnswer } from "@/lib/api";
import type { PendingAnswer } from "./answerQueue";

export type Session = { session_id: number; questions: Question[] };
export type ResumedSession = { version: 1; session_id: number; questions: (Question & {answered: boolean; revealed: boolean})[] };
export type StartInput = { practice_type: string; mode: string; book_ids: number[]; chapter_ids: number[]; source_entry_ids: number[]; question_count: number | null };
export const startPractice = (input: StartInput) => api<Session>("/practice/start", {method: "POST", body: JSON.stringify(input)});
export const resumePractice = (id: number) => api<ResumedSession>(`/practice/sessions/${id}`);
export const revealQuestion = (sessionId: number, questionId: number) => api<RevealedAnswer>(`/practice/questions/${questionId}/reveal`, {method: "POST", body: JSON.stringify({session_id: sessionId})});
export const saveAnswer = (input: PendingAnswer) => api<{status: string; attempts: number; mastery_score: number; answered_at: string}>("/practice/answer", {method: "POST", body: JSON.stringify(input)});
