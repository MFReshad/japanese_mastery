"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import ChapterVocabularyManager from "@/components/ChapterVocabularyManager";
import { Book, Chapter, getBooks, getChapters } from "@/lib/api";
import { ManageHeader } from "./shared";
export default function VocabularyScreen() { const params = useSearchParams(); const [books, setBooks] = useState<Book[]>([]); const [chapters, setChapters] = useState<Chapter[]>([]); const [ready, setReady] = useState(false); useEffect(() => { Promise.all([getBooks(), getChapters()]).then(([nextBooks, nextChapters]) => { setBooks(nextBooks); setChapters(nextChapters); setReady(true); }); }, []); if (!ready) return <p>Loading vocabulary…</p>; const requestedBook = params.get("book") || localStorage.getItem("manage-book") || ""; const requestedChapter = params.get("chapter") || localStorage.getItem("manage-vocabulary-chapter") || ""; return <div><ManageHeader title="Vocabulary" description="Choose a book and chapter to edit the exact order used for study. Drag rows or use the move buttons, then save the order."/><ChapterVocabularyManager books={books} chapters={chapters} initialBookId={requestedBook} initialChapterId={requestedChapter}/></div>; }
