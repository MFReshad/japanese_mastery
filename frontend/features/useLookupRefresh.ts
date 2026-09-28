"use client";
import { useEffect } from "react";
import { Book, Chapter, getActiveBooks, getChapters, subscribeLookups } from "@/lib/api";

export function useLookupRefresh(setBooks: (books: Book[]) => void, setChapters: (chapters: Chapter[]) => void) {
  useEffect(() => {
    let active = true;
    let generation = 0;
    const refresh = () => {
      const request = ++generation;
      Promise.all([getActiveBooks(), getChapters()]).then(([books, chapters]) => {
        if (active && request === generation) { setBooks(books); setChapters(chapters); }
      }).catch(() => { /* Initial loads own their visible error state; keep last good lookup on refresh. */ });
    };
    const unsubscribe = subscribeLookups(refresh);
    return () => { active = false; unsubscribe(); };
  }, [setBooks, setChapters]);
}
