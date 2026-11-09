import type { Chapter } from "@/lib/api";

export function sortChaptersByPart(rows: Chapter[]) {
  return [...rows].sort((a, b) =>
    a.book_id - b.book_id ||
    String(a.part ?? "").localeCompare(String(b.part ?? ""), undefined, { numeric: true }) ||
    a.chapter_number - b.chapter_number ||
    a.sort_order - b.sort_order ||
    a.id - b.id
  );
}
