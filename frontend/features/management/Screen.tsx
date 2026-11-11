"use client";
import Link from "next/link";
import { BookOpen, BookMarked, Languages, Database, Upload, BarChart3, GitCompareArrows, ListChecks, LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Book, Chapter, getBooks, getChapters } from "@/lib/api";
type Card = { href: string; title: string; description: string; icon: LucideIcon; count: (books: Book[], chapters: Chapter[]) => string };
const cards: Card[] = [
  { href: "/manage/books", title: "Books", description: "Manage book metadata and availability.", icon: BookOpen, count: (books) => `${books.length} ${books.length === 1 ? "book" : "books"}` },
  { href: "/manage/chapters", title: "Chapters", description: "Organize lessons within each book.", icon: BookMarked, count: (_, chapters) => `${chapters.length} ${chapters.length === 1 ? "chapter" : "chapters"}` },
  { href: "/manage/vocabulary", title: "Vocabulary", description: "Edit chapter vocabulary, fill gaps, and control study order.", icon: Languages, count: (books) => `${books.reduce((sum, book) => sum + book.vocabulary_count, 0).toLocaleString()} entries` },
  { href: "/manage/kanji", title: "Kanji", description: "Review readings, meanings, examples, and uncertain entries.", icon: Database, count: (books) => `${books.reduce((sum, book) => sum + book.kanji_count, 0).toLocaleString()} entries` },
  { href: "/manage/compare", title: "Compare books", description: "Match vocabulary or kanji across books and see where each item appears.", icon: GitCompareArrows, count: (books) => `${books.length} books available` },
  { href: "/manage/review", title: "Review marks", description: "Find conflicting knowledge and practice states, then update many items together.", icon: ListChecks, count: () => "Filter and bulk update" },
  { href: "/manage/imports", title: "Imports", description: "Preview source files, resolve conflicts, and commit imports.", icon: Upload, count: () => "Preview before committing" },
  { href: "/progress", title: "Practice / Progress", description: "Review mastery and coverage across your study data.", icon: BarChart3, count: () => "View learning progress" },
];
export default function ManagePage() { const [data, setData] = useState<{ books: Book[]; chapters: Chapter[] }>({ books: [], chapters: [] }); useEffect(() => { Promise.all([getBooks(), getChapters()]).then(([books, chapters]) => setData({ books, chapters })); }, []); return <div><header className="mb-8"><h1 className="text-3xl font-semibold tracking-tight">Data Management</h1><p className="mt-2 max-w-2xl text-stone-600">Choose an area to manage. Everyday editing and import tools are kept in focused workspaces.</p></header><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{cards.map(({ href, title, description, icon: Icon, count }) => <Link key={href} href={href} className="group flex min-h-52 flex-col rounded-2xl border border-stone-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-moss hover:shadow-md"><div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-moss/10 text-moss"><Icon size={23} /></div><h2 className="text-xl font-semibold group-hover:text-moss">{title}</h2><p className="mt-2 flex-1 text-sm leading-6 text-stone-600">{description}</p><p className="mt-5 text-sm font-semibold text-ink">{count(data.books, data.chapters)}</p></Link>)}</div></div>; }
